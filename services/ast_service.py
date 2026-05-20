"""
Java 프로젝트 AST 분석.

tree-sitter로 .java 파일을 파싱해서:
  - 클래스 정보 (이름, 패키지, 어노테이션, 계층, 상속)
  - 메서드 정보 (이름, 시그니처, 어노테이션)
  - 호출 관계 (CallEdge: 누가 누구를 호출하는지)

호출 관계 추출 전략:
  1) 클래스 내 필드 + 생성자 파라미터 + 메서드 지역 변수를 모아
     "변수명 → 타입" 매핑 테이블 생성
  2) 메서드 안의 method_invocation 노드를 순회하면서
     object가 매핑에 있으면 → 해당 타입을 callee_class로 사용 (is_resolved=True)
     없으면 → object 텍스트 그대로 + is_resolved=False
"""
from pathlib import Path
from typing import Optional

import tree_sitter_java
from tree_sitter import Language, Node, Parser, Query, QueryCursor

from models.ast import (
    AstAnalysisResult,
    CallEdge,
    ClassKind,
    JavaClass,
    JavaMethod,
    JavaParameter,
    ParseError,
    Stereotype,
)

from utils.ast_cache import get_cache_path


def delete_cache(project_name: str) -> None:
    path = get_cache_path(project_name)
    if path.exists():
        path.unlink()


# ============================================================
# tree-sitter 초기화 (모듈 로드 시 1회)
# ============================================================
_JAVA = Language(tree_sitter_java.language())
_parser = Parser(_JAVA)

_TYPE_QUERY = Query(_JAVA, """
(class_declaration)     @class
(interface_declaration) @interface
(enum_declaration)      @enum
(record_declaration)    @record
""")


# ============================================================
# 스캔 제외 폴더 (project_scanner와 동일 정책)
# ============================================================
_SKIP_DIRS = {
    "target", "build", "out", "bin", "dist",
    "node_modules", ".gradle", ".m2",
    ".idea", ".vscode", ".settings", ".eclipse",
    ".git", ".analysis", "__pycache__",
}


# ============================================================
# 진입점
# ============================================================
def parse_java_project(project_path: Path) -> AstAnalysisResult:
    """프로젝트 폴더 안의 모든 .java 파일을 파싱해서 결과 반환"""
    result = AstAnalysisResult()

    for java_file in _collect_java_files(project_path):
        try:
            classes, edges = _parse_file(java_file)
            result.classes.extend(classes)
            result.call_edges.extend(edges)
        except Exception as e:
            result.errors.append(ParseError(file_path=str(java_file), error=str(e)))

    return result


def _collect_java_files(root: Path) -> list[Path]:
    files = []
    for path in root.rglob("*.java"):
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        files.append(path)
    return files


# ============================================================
# 파일 1개 파싱
# ============================================================
def _parse_file(java_file: Path) -> tuple[list[JavaClass], list[CallEdge]]:
    source = java_file.read_bytes()
    tree = _parser.parse(source)
    root = tree.root_node

    package = _extract_package(root)

    classes: list[JavaClass] = []
    edges: list[CallEdge] = []

    cursor = QueryCursor(_TYPE_QUERY)
    captures = cursor.captures(root)

    for kind_label, nodes in captures.items():
        kind: ClassKind = kind_label
        for node in nodes:
            cls = _build_class(node, kind, package, java_file)
            if cls is None:
                continue
            classes.append(cls)
            # 호출 관계 추출 (인터페이스는 본문 없으므로 건너뜀)
            if kind != "interface":
                edges.extend(_extract_call_edges(node, cls))

    return classes, edges


def _extract_package(root: Node) -> str:
    for child in root.children:
        if child.type == "package_declaration":
            for sub in child.children:
                if sub.type in ("scoped_identifier", "identifier"):
                    return sub.text.decode("utf-8")
    return ""


# ============================================================
# 클래스 노드 → JavaClass
# ============================================================
def _build_class(node: Node, kind: ClassKind, package: str, file_path: Path) -> Optional[JavaClass]:
    name_node = node.child_by_field_name("name")
    if name_node is None:
        return None
    name = name_node.text.decode("utf-8")

    annotations = _extract_annotations(node)
    extends, implements = _extract_inheritance(node)
    methods = _extract_methods(node, name)
    stereotype = _classify_stereotype(annotations, package, extends, name)

    return JavaClass(
        file_path=str(file_path),
        name=name,
        package=package,
        kind=kind,
        stereotype=stereotype,
        annotations=annotations,
        extends=extends,
        implements=implements,
        methods=methods,
    )


# ============================================================
# 어노테이션 추출
# ============================================================
def _extract_annotations(node: Node) -> list[str]:
    annotations = []
    for child in node.children:
        if child.type == "modifiers":
            for sub in child.children:
                if sub.type in ("marker_annotation", "annotation"):
                    text = sub.text.decode("utf-8")
                    text = " ".join(text.split())
                    annotations.append(text)
    return annotations


# ============================================================
# 상속/구현 추출
# ============================================================
def _extract_inheritance(node: Node) -> tuple[Optional[str], list[str]]:
    extends: Optional[str] = None
    implements: list[str] = []

    for child in node.children:
        if child.type == "superclass":
            extends = _extract_type_text(child)
        elif child.type in ("super_interfaces", "extends_interfaces"):
            for sub in child.children:
                if sub.type == "type_list":
                    for type_node in sub.children:
                        if type_node.type in ("type_identifier", "generic_type", "scoped_type_identifier"):
                            implements.append(type_node.text.decode("utf-8"))

    return extends, implements


def _extract_type_text(parent: Node) -> Optional[str]:
    for child in parent.children:
        if child.type in ("type_identifier", "generic_type", "scoped_type_identifier"):
            return child.text.decode("utf-8")
    return None


# ============================================================
# 메서드 추출
# ============================================================
def _extract_methods(class_node: Node, class_name: str) -> list[JavaMethod]:
    methods: list[JavaMethod] = []
    body = class_node.child_by_field_name("body")
    if body is None:
        return methods

    for child in body.children:
        if child.type == "method_declaration":
            method = _build_method(child, class_name)
            if method is not None:
                methods.append(method)
    return methods


def _build_method(node: Node, class_name: str) -> Optional[JavaMethod]:
    name_node = node.child_by_field_name("name")
    if name_node is None:
        return None
    name = name_node.text.decode("utf-8")

    return_type_node = node.child_by_field_name("type")
    return_type = return_type_node.text.decode("utf-8") if return_type_node else "void"

    params = _extract_parameters(node)
    access = _extract_access(node)
    annotations = _extract_annotations(node)

    return JavaMethod(
        class_name=class_name,
        name=name,
        return_type=return_type,
        parameters=params,
        access=access,
        annotations=annotations,
    )


def _extract_parameters(method_node: Node) -> list[JavaParameter]:
    params: list[JavaParameter] = []
    params_node = method_node.child_by_field_name("parameters")
    if params_node is None:
        return params

    for child in params_node.children:
        if child.type == "formal_parameter":
            type_node = child.child_by_field_name("type")
            name_node = child.child_by_field_name("name")
            if type_node and name_node:
                params.append(JavaParameter(
                    name=name_node.text.decode("utf-8"),
                    type=type_node.text.decode("utf-8"),
                ))
    return params


def _extract_access(node: Node) -> str:
    for child in node.children:
        if child.type == "modifiers":
            for sub in child.children:
                if sub.type in ("public", "protected", "private"):
                    return sub.type
    return "package"


# ============================================================
# 호출 관계 추출
# ============================================================
def _extract_call_edges(class_node: Node, cls: JavaClass) -> list[CallEdge]:
    """클래스 1개의 모든 메서드를 순회하면서 호출 관계 추출"""
    edges: list[CallEdge] = []

    # 클래스 레벨 변수→타입 매핑 (필드)
    field_types = _collect_field_types(class_node)

    body = class_node.child_by_field_name("body")
    if body is None:
        return edges

    # 클래스 내 정의된 메서드 이름들 (object 없는 호출이 self 호출인지 판별용)
    own_method_names = {m.name for m in cls.methods}

    for child in body.children:
        if child.type != "method_declaration":
            continue
        method_name_node = child.child_by_field_name("name")
        if method_name_node is None:
            continue
        caller_method = method_name_node.text.decode("utf-8")

        # 이 메서드 안에서만 유효한 변수→타입 매핑
        local_types = dict(field_types)
        local_types.update(_collect_parameter_types(child))
        local_types.update(_collect_local_var_types(child))

        # method_invocation 모두 찾기
        for invocation in _find_method_invocations(child):
            edge = _build_call_edge(
                invocation, cls.name, caller_method,
                local_types, own_method_names,
            )
            if edge is not None:
                edges.append(edge)

    return edges


def _collect_field_types(class_node: Node) -> dict[str, str]:
    """클래스 필드: private final UserRepository userRepository; → {userRepository: UserRepository}"""
    types: dict[str, str] = {}
    body = class_node.child_by_field_name("body")
    if body is None:
        return types

    for child in body.children:
        if child.type != "field_declaration":
            continue
        type_node = child.child_by_field_name("type")
        if type_node is None:
            continue
        type_text = _simple_type_name(type_node)

        # field_declaration에 declarator 여러 개 가능 (int a, b, c)
        for sub in child.children:
            if sub.type == "variable_declarator":
                name_node = sub.child_by_field_name("name")
                if name_node:
                    types[name_node.text.decode("utf-8")] = type_text
    return types


def _collect_parameter_types(method_node: Node) -> dict[str, str]:
    """메서드 파라미터: (UserRepository userRepository) → {userRepository: UserRepository}"""
    types: dict[str, str] = {}
    params_node = method_node.child_by_field_name("parameters")
    if params_node is None:
        return types
    for child in params_node.children:
        if child.type == "formal_parameter":
            type_node = child.child_by_field_name("type")
            name_node = child.child_by_field_name("name")
            if type_node and name_node:
                types[name_node.text.decode("utf-8")] = _simple_type_name(type_node)
    return types


def _collect_local_var_types(method_node: Node) -> dict[str, str]:
    """메서드 본문의 지역 변수 선언: User user = ...; → {user: User}"""
    types: dict[str, str] = {}
    body = method_node.child_by_field_name("body")
    if body is None:
        return types

    # 재귀로 local_variable_declaration 모두 찾기
    stack = [body]
    while stack:
        node = stack.pop()
        if node.type == "local_variable_declaration":
            type_node = node.child_by_field_name("type")
            if type_node:
                type_text = _simple_type_name(type_node)
                for sub in node.children:
                    if sub.type == "variable_declarator":
                        name_node = sub.child_by_field_name("name")
                        if name_node:
                            types[name_node.text.decode("utf-8")] = type_text
        stack.extend(node.children)
    return types


def _simple_type_name(type_node: Node) -> str:
    """제네릭은 벗기고 핵심 타입명만: List<User> → List, UserRepository → UserRepository"""
    if type_node.type == "generic_type":
        # generic_type → type_identifier + type_arguments
        for child in type_node.children:
            if child.type in ("type_identifier", "scoped_type_identifier"):
                return child.text.decode("utf-8")
    return type_node.text.decode("utf-8")


def _find_method_invocations(node: Node) -> list[Node]:
    """노드 하위의 모든 method_invocation을 깊이우선으로 수집"""
    result = []
    stack = [node]
    while stack:
        n = stack.pop()
        if n.type == "method_invocation":
            result.append(n)
        stack.extend(n.children)
    return result


def _build_call_edge(
    invocation: Node,
    caller_class: str,
    caller_method: str,
    var_types: dict[str, str],
    own_method_names: set[str],
) -> Optional[CallEdge]:
    """method_invocation 노드 1개 → CallEdge"""
    name_node = invocation.child_by_field_name("name")
    if name_node is None:
        return None
    callee_method = name_node.text.decode("utf-8")

    object_node = invocation.child_by_field_name("object")

    # Case 1: object 없음 → 같은 클래스 메서드 호출 (this 생략)
    if object_node is None:
        if callee_method in own_method_names:
            return CallEdge(
                caller_class=caller_class,
                caller_method=caller_method,
                callee_class=caller_class,
                callee_method=callee_method,
                is_resolved=True,
            )
        # 같은 클래스 메서드 아니면 (예: static import) 추적 어려움
        return CallEdge(
            caller_class=caller_class,
            caller_method=caller_method,
            callee_class="(unknown)",
            callee_method=callee_method,
            is_resolved=False,
        )

    # Case 2: object가 identifier (단순 변수) → 매핑 시도
    if object_node.type == "identifier":
        obj_name = object_node.text.decode("utf-8")

        # this.foo() 또는 super.foo()
        if obj_name in ("this", "super"):
            if callee_method in own_method_names:
                return CallEdge(caller_class, caller_method, caller_class, callee_method, True)
            return None  # super 호출은 부모 추적 못 함, 일단 스킵

        # 변수 → 타입 매핑 성공?
        if obj_name in var_types:
            return CallEdge(
                caller_class=caller_class,
                caller_method=caller_method,
                callee_class=var_types[obj_name],
                callee_method=callee_method,
                is_resolved=True,
            )

        # 매핑 실패 → static 호출일 가능성 (예: Collectors.toList())
        # 클래스 이름처럼 보이면 (대문자 시작) is_resolved=True로 취급
        if obj_name and obj_name[0].isupper():
            return CallEdge(
                caller_class=caller_class,
                caller_method=caller_method,
                callee_class=obj_name,
                callee_method=callee_method,
                is_resolved=True,
            )

        # 그 외: 매핑 실패
        return CallEdge(
            caller_class=caller_class,
            caller_method=caller_method,
            callee_class=obj_name,
            callee_method=callee_method,
            is_resolved=False,
        )

    # Case 3: 메서드 체이닝 (x.foo().bar()) → 추적 어려움, 일단 스킵
    # → 너무 많이 생기는 노이즈를 피하기 위해 None 반환
    return None


# ============================================================
# stereotype (계층) 판별
# ============================================================
def _classify_stereotype(
    annotations: list[str],
    package: str,
    extends: Optional[str],
    class_name: str,
) -> Stereotype:
    ann_names = {_ann_name(a) for a in annotations}
    if "RestController" in ann_names or "Controller" in ann_names:
        return "controller"
    if "Service" in ann_names:
        return "service"
    if "Repository" in ann_names:
        return "repository"
    if "Entity" in ann_names:
        return "entity"
    if "Configuration" in ann_names:
        return "config"
    if "Component" in ann_names:
        return "component"

    if extends:
        if "JpaRepository" in extends or "CrudRepository" in extends:
            return "repository"
        if extends.endswith("Exception"):
            return "exception"

    if class_name.endswith("Exception"):
        return "exception"
    if class_name.endswith("Tests") or class_name.endswith("Test"):
        return "test"

    pkg_last = package.rsplit(".", 1)[-1].lower() if package else ""
    if pkg_last in ("controller", "controllers", "web"):
        return "controller"
    if pkg_last in ("service", "services"):
        return "service"
    if pkg_last in ("repository", "repositories", "dao"):
        return "repository"
    if pkg_last in ("entity", "entities", "domain", "model", "models"):
        return "entity"
    if pkg_last in ("dto", "dtos", "request", "response"):
        return "dto"
    if pkg_last in ("config", "configuration"):
        return "config"
    if pkg_last in ("exception", "exceptions", "error"):
        return "exception"

    return "unknown"


def _ann_name(annotation_text: str) -> str:
    s = annotation_text.lstrip("@")
    if "(" in s:
        s = s.split("(", 1)[0]
    return s.strip()