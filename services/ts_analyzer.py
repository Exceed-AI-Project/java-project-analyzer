"""
tree-sitter 기반 Java 파서  (Java 17+ 지원: record / sealed / text block 등)
javalang 과 동일한 ProjectModel 을 산출해 하위 모듈(시뮬레이터/루프/탐지기)은 그대로 동작.

핵심:
- record 의 컴포넌트를 '필드'로 매핑 → 모던 Spring DTO(record) 의 제약을 읽을 수 있음
- 에러 허용 파서라 신문법 일부를 못 읽어도 파일 전체가 죽지 않음
"""
from __future__ import annotations
from pathlib import Path

from tree_sitter import Language, Parser
import tree_sitter_java as tsjava

from models.analysis import (
    ProjectModel, ClassInfo, FieldInfo, MethodInfo, ParamInfo,
)
from services.ast_analyzer import SKIP_DIRS  # 동일 스킵 규칙 재사용

_JAVA = Language(tsjava.language())
_PARSER = Parser(_JAVA)


def _txt(node) -> str:
    return node.text.decode("utf-8", "replace") if node is not None else ""


def _simple_name(name: str) -> str:
    """org.springframework...Transactional → Transactional"""
    return name.split(".")[-1].strip()


def _find_modifiers(node):
    for c in node.children:
        if c.type == "modifiers":
            return c
    return None


def _collect_annotations(node) -> dict[str, dict]:
    out: dict[str, dict] = {}
    mods = _find_modifiers(node)
    if mods is None:
        return out
    for c in mods.children:
        if c.type == "marker_annotation":       # @Override
            name = _simple_name(_txt(c.child_by_field_name("name")))
            out[name] = {}
        elif c.type == "annotation":             # @Column(nullable=false), @RequestMapping("/x")
            name = _simple_name(_txt(c.child_by_field_name("name")))
            out[name] = _ann_args(c.child_by_field_name("arguments"))
    return out


def _ann_args(arglist) -> dict:
    params: dict = {}
    if arglist is None:
        return params
    for c in arglist.named_children:
        if c.type == "element_value_pair":
            key = _txt(c.child_by_field_name("key"))
            val = _txt(c.child_by_field_name("value")).strip('"')
            params[key] = val
        else:
            params["_value"] = _txt(c).strip('"')
    return params


def _modifier_keywords(node) -> set[str]:
    mods = _find_modifiers(node)
    if mods is None:
        return set()
    kws = {"public", "private", "protected", "static", "final", "abstract", "default"}
    return {c.type for c in mods.children if c.type in kws}


def _field(node) -> list[FieldInfo]:
    ftype = _txt(node.child_by_field_name("type"))
    anns = _collect_annotations(node)
    mods = _modifier_keywords(node)
    line = node.start_point[0] + 1
    out = []
    for c in node.named_children:
        if c.type == "variable_declarator":
            out.append(FieldInfo(
                name=_txt(c.child_by_field_name("name")),
                type=ftype, annotations=anns, modifiers=mods, line=line,
            ))
    return out


def _params(formal_params) -> list[ParamInfo]:
    out = []
    if formal_params is None:
        return out
    for c in formal_params.named_children:
        if c.type in ("formal_parameter", "spread_parameter"):
            out.append(ParamInfo(
                name=_txt(c.child_by_field_name("name")),
                type=_txt(c.child_by_field_name("type")),
                annotations=_collect_annotations(c),
            ))
    return out


def _invokes(body) -> list[str]:
    if body is None:
        return []
    names = []
    stack = [body]
    while stack:
        n = stack.pop()
        if n.type == "method_invocation":
            nm = n.child_by_field_name("name")
            if nm is not None:
                names.append(_txt(nm))
        stack.extend(n.children)
    return names


def _risky_catches(body) -> list[str]:
    if body is None:
        return []
    out = []
    stack = [body]
    while stack:
        n = stack.pop()
        if n.type == "catch_clause":
            ctype = ""
            blk_empty = True
            for c in n.children:
                if c.type == "catch_formal_parameter":
                    ctype = _txt(c)
                if c.type == "block":
                    blk_empty = len(c.named_children) == 0
            if blk_empty:
                out.append("empty")
            elif "Exception" in ctype or "Throwable" in ctype:
                out.append("broad")
        stack.extend(n.children)
    return out


def _method(node) -> MethodInfo:
    body = node.child_by_field_name("body")
    return MethodInfo(
        name=_txt(node.child_by_field_name("name")),
        return_type=_txt(node.child_by_field_name("type")) or "void",
        params=_params(node.child_by_field_name("parameters")),
        annotations=_collect_annotations(node),
        modifiers=_modifier_keywords(node),
        invokes=_invokes(body),
        risky_catches=_risky_catches(body),
        line=node.start_point[0] + 1,
    )


def _parse_type_decl(node, package: str, rel: str) -> ClassInfo:
    kind = {
        "class_declaration": "class",
        "interface_declaration": "interface",
        "enum_declaration": "enum",
        "record_declaration": "class",   # record 도 클래스로 취급
    }[node.type]

    ci = ClassInfo(
        name=_txt(node.child_by_field_name("name")),
        kind=kind, package=package, file_path=rel,
        annotations=_collect_annotations(node),
    )

    # extends / implements
    sc = node.child_by_field_name("superclass")
    if sc is not None:
        ci.extends = _txt(sc).replace("extends", "").strip()
    ifaces = node.child_by_field_name("interfaces")
    if ifaces is not None:
        ci.implements = [t.strip() for t in
                         _txt(ifaces).replace("implements", "").split(",") if t.strip()]

    # record 컴포넌트 → 필드로
    if node.type == "record_declaration":
        rec_params = node.child_by_field_name("parameters")
        for p in _params(rec_params):
            ci.fields.append(FieldInfo(name=p.name, type=p.type,
                                       annotations=p.annotations,
                                       modifiers={"private", "final"}))

    body = node.child_by_field_name("body")
    if body is not None:
        for c in body.named_children:
            if c.type == "field_declaration":
                ci.fields.extend(_field(c))
            elif c.type in ("method_declaration", "compact_constructor_declaration"):
                if c.type == "method_declaration":
                    ci.methods.append(_method(c))
    return ci


def _iter_java_files(root: Path):
    for path in root.rglob("*.java"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path


def build_model_ts(project_path: str | Path) -> ProjectModel:
    root = Path(project_path)
    model = ProjectModel()
    for path in _iter_java_files(root):
        rel = str(path.relative_to(root))
        try:
            src = path.read_bytes()
            tree = _PARSER.parse(src)
            rootn = tree.root_node
            # 에러 노드가 있어도 파싱된 타입 선언은 최대한 수집 (부분 복구)
            if rootn.has_error:
                model.parse_errors.append((rel, "tree-sitter: 일부 구문 오류(부분 파싱됨)"))
            package = ""
            imports: list[str] = []
            stack = [rootn]
            type_nodes = []
            while stack:
                n = stack.pop()
                if n.type == "package_declaration":
                    package = _txt(n).replace("package", "").replace(";", "").strip()
                if n.type == "import_declaration":
                    imports.append(_txt(n).replace("import", "").replace("static", "")
                                   .replace(";", "").strip())
                if n.type in ("class_declaration", "interface_declaration",
                              "enum_declaration", "record_declaration"):
                    type_nodes.append(n)
                    continue  # 중첩 클래스는 단순화를 위해 일단 스킵
                stack.extend(n.children)
            for tn in type_nodes:
                ci = _parse_type_decl(tn, package, rel)
                ci.imports = imports
                model.classes.append(ci)
        except Exception as e:
            model.parse_errors.append((rel, f"{type(e).__name__}: {e}"))
    return model
