"""
AST 분석 엔진
javalang 으로 프로젝트의 .java 파일을 파싱해 구조 모델(ProjectModel)을 만들고,
규칙 기반 결함(Finding)을 탐지한다.

※ javalang 은 '파서'일 뿐 심볼/타입 리졸버가 아니다.
   따라서 콜그래프/타입 매칭은 이름 기반 휴리스틱으로 처리하며, 한계가 있음을 전제로 한다.
   (정밀도가 더 필요하면 추후 JavaParser/Spoon 기반 JVM 사이드카로 교체)
"""
from __future__ import annotations
from pathlib import Path

import javalang
from javalang import tree as jtree

from models.analysis import (
    ProjectModel, ClassInfo, FieldInfo, MethodInfo, ParamInfo, Finding,
)

# 분석 대상에서 제외할 디렉토리 (scanner 와 일관)
SKIP_DIRS = {
    "target", "build", "out", "bin", "dist", "node_modules",
    ".gradle", ".m2", ".idea", ".vscode", ".git", ".analysis", "__pycache__",
}

# 프레임워크가 '호출'하므로 데드코드로 보면 안 되는 진입점 어노테이션
FRAMEWORK_ENTRY_ANNS = {
    "Override", "Bean", "PostConstruct", "PreDestroy", "EventListener",
    "Scheduled", "PostMapping", "GetMapping", "PutMapping", "DeleteMapping",
    "PatchMapping", "RequestMapping", "ExceptionHandler", "InitBinder",
    "ModelAttribute", "Test", "BeforeEach", "AfterEach", "Query",
}

# 제약 어노테이션 → 필수값으로 간주
NOT_NULL_ANNS = {"NotNull", "NotBlank", "NotEmpty"}


# ============================================================
# 어노테이션 파라미터 추출 헬퍼
# ============================================================
def _literal_value(node) -> str | None:
    """javalang 값 노드에서 문자열 표현을 최대한 뽑아낸다."""
    if node is None:
        return None
    if isinstance(node, jtree.Literal):
        return str(node.value).strip('"')
    if isinstance(node, jtree.MemberReference):
        return node.member
    if hasattr(node, "value") and isinstance(node.value, str):
        return node.value.strip('"')
    return None


def _ann_params(annotation) -> dict:
    """@Column(nullable = false), @RequestMapping("/x") 등에서 파라미터 dict 추출.
    위치 인자는 "_value" 키로 들어간다.
    """
    params: dict = {}
    elem = getattr(annotation, "element", None)
    if elem is None:
        return params
    pairs = elem if isinstance(elem, list) else [elem]
    for p in pairs:
        if isinstance(p, jtree.ElementValuePair):
            params[p.name] = _literal_value(p.value)
        else:
            params["_value"] = _literal_value(p)
    return params


def _collect_annotations(node) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for ann in (getattr(node, "annotations", None) or []):
        out[ann.name] = _ann_params(ann)
    return out


def _type_name(type_node) -> str:
    if type_node is None:
        return "void"
    name = getattr(type_node, "name", None) or type_node.__class__.__name__
    args = getattr(type_node, "arguments", None)
    if args:
        inner = []
        for a in args:
            t = getattr(a, "type", None)
            inner.append(getattr(t, "name", "?") if t else "?")
        return f"{name}<{', '.join(inner)}>"
    return name


# ============================================================
# 파일 1개 파싱
# ============================================================
def _parse_class(decl, package: str, file_path: str) -> ClassInfo:
    kind = (
        "interface" if isinstance(decl, jtree.InterfaceDeclaration)
        else "enum" if isinstance(decl, jtree.EnumDeclaration)
        else "class"
    )
    ci = ClassInfo(
        name=decl.name,
        kind=kind,
        package=package,
        file_path=file_path,
        annotations=_collect_annotations(decl),
        extends=_type_name(decl.extends) if getattr(decl, "extends", None) else None,
        implements=[_type_name(i) for i in (getattr(decl, "implements", None) or [])],
    )

    for fdecl in (getattr(decl, "fields", None) or []):
        ftype = _type_name(fdecl.type)
        fanns = _collect_annotations(fdecl)
        fmods = set(fdecl.modifiers or [])
        for var in fdecl.declarators:
            ci.fields.append(FieldInfo(
                name=var.name, type=ftype, annotations=fanns,
                modifiers=fmods, line=(fdecl.position.line if fdecl.position else 0),
            ))

    for m in (getattr(decl, "methods", None) or []):
        params = [
            ParamInfo(name=p.name, type=_type_name(p.type),
                      annotations=_collect_annotations(p))
            for p in m.parameters
        ]
        invokes = []
        if m.body:
            try:
                for _, inv in m.filter(jtree.MethodInvocation):
                    invokes.append(inv.member)
            except Exception:
                pass
        ci.methods.append(MethodInfo(
            name=m.name,
            return_type=_type_name(m.return_type),
            params=params,
            annotations=_collect_annotations(m),
            modifiers=set(m.modifiers or []),
            invokes=invokes,
            line=(m.position.line if m.position else 0),
        ))
    return ci


def _iter_java_files(root: Path):
    for path in root.rglob("*.java"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path


# ============================================================
# 프로젝트 전체 모델 빌드
# ============================================================
def build_model(project_path: str | Path, parser: str = "auto") -> ProjectModel:
    """parser: 'auto' = 사이드카(jar 있으면) → tree-sitter → javalang 순 폴백.
               'javaparser' = 강제 사이드카(심볼 리졸브). 'treesitter' / 'javalang' = 강제.
    """
    if parser in ("auto", "javaparser"):
        try:
            from services.javaparser_sidecar import build_model_javaparser, available
            if parser == "javaparser" or available()[0]:
                return build_model_javaparser(project_path)
        except Exception:
            if parser == "javaparser":
                raise
    if parser in ("auto", "treesitter"):
        try:
            from services.ts_analyzer import build_model_ts
            return build_model_ts(project_path)
        except Exception:
            if parser == "treesitter":
                raise
            # tree-sitter 미설치 등 → javalang 폴백
    return _build_model_javalang(project_path)


def _build_model_javalang(project_path: str | Path) -> ProjectModel:
    root = Path(project_path)
    model = ProjectModel()

    for path in _iter_java_files(root):
        rel = str(path.relative_to(root))
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            tree = javalang.parse.parse(source)
        except Exception as e:
            # javalang 0.13 은 record/sealed 등 Java 17 신문법 일부를 못 읽는다 → 에러로 기록
            model.parse_errors.append((rel, f"{type(e).__name__}: {e}"))
            continue

        package = tree.package.name if tree.package else ""
        imports = [(imp.path + ".*") if imp.wildcard else imp.path
                   for imp in (tree.imports or [])]
        for decl in tree.types:
            if isinstance(decl, (jtree.ClassDeclaration, jtree.InterfaceDeclaration,
                                 jtree.EnumDeclaration)):
                ci = _parse_class(decl, package, rel)
                ci.imports = imports
                model.classes.append(ci)
    return model


# ============================================================
# 규칙 기반 탐지기
# ============================================================
def _loc(ci: ClassInfo, m: MethodInfo | None = None) -> str:
    base = f"{ci.file_path} > {ci.name}"
    return f"{base} > {m.name}()" if m else base


def detect_pk_issues(model: ProjectModel) -> list[Finding]:
    """@Entity 인데 @Id 필드가 없음 (PK 누락)"""
    out = []
    for ci in model.of_stereotype("entity"):
        has_id = any("Id" in f.annotations for f in ci.fields)
        if not has_id:
            out.append(Finding(
                "high", "PK_MISSING", _loc(ci),
                "@Entity 인데 @Id 필드가 없음. JPA 매핑 시 부팅 실패하거나 영속성 동작이 깨짐.",
                "기본키 필드에 @Id 를 추가하고, 자동 생성이면 @GeneratedValue 도 함께 지정.",
            ))
        # @Id 인데 @GeneratedValue 없음 → 생성 API 에서 PK 직접 넣어줘야 함 (시뮬레이터가 활용)
        for f in ci.fields:
            if "Id" in f.annotations and "GeneratedValue" not in f.annotations:
                out.append(Finding(
                    "low", "PK_MANUAL", _loc(ci),
                    f"필드 '{f.name}' 는 @Id 지만 @GeneratedValue 가 없어 수동 할당이 필요.",
                    "자동 생성이 의도라면 @GeneratedValue(strategy=...) 추가 검토.",
                ))
    return out


def detect_transactional_misuse(model: ProjectModel) -> list[Finding]:
    """@Transactional 오남용:
       - Controller 에 직접 부착
       - private 메서드에 부착 (프록시 AOP 미적용 → 트랜잭션 안 걸림)
    """
    out = []
    for ci in model.classes:
        on_controller = ci.stereotype == "controller"
        for m in ci.methods:
            if "Transactional" not in m.annotations:
                continue
            if on_controller:
                out.append(Finding(
                    "medium", "TRANSACTIONAL", _loc(ci, m),
                    "Controller 메서드에 @Transactional. 트랜잭션 경계는 Service 레이어가 적절.",
                    "트랜잭션 로직을 Service 메서드로 내리고 Controller 는 위임만.",
                ))
            if "private" in m.modifiers:
                out.append(Finding(
                    "high", "TRANSACTIONAL", _loc(ci, m),
                    "private 메서드의 @Transactional 은 Spring 프록시로 적용되지 않음 (무효).",
                    "public 으로 바꾸거나, 자기호출(self-invocation) 구조를 별도 빈으로 분리.",
                ))
    return out


def detect_dead_code(model: ProjectModel) -> list[Finding]:
    """미사용 메서드 후보.
       프레임워크 진입점/오버라이드/매핑 어노테이션은 제외해 오탐을 줄인다.
       ※ 이름 기반 휴리스틱이라 '후보'로만 제시 (확정 아님).
    """
    out = []
    # 프로젝트 전체에서 호출된 메서드명 집합
    called: set[str] = set()
    for ci in model.classes:
        for m in ci.methods:
            called.update(m.invokes)

    for ci in model.classes:
        if ci.kind == "interface":
            continue
        for m in ci.methods:
            if m.name in ("main", "toString", "equals", "hashCode"):
                continue
            if "public" not in m.modifiers and "protected" not in m.modifiers:
                # private/패키지 메서드도 후보지만, 진입점 어노테이션 있으면 제외
                pass
            if any(a in FRAMEWORK_ENTRY_ANNS for a in m.annotations):
                continue
            if m.name in called:
                continue
            out.append(Finding(
                "low", "DEAD_CODE", _loc(ci, m),
                "프로젝트 내 어디서도 호출되지 않는 메서드 후보 (리플렉션/외부호출 가능성은 별도 확인 필요).",
                "실제 미사용이면 제거, 외부 API/리플렉션 호출이면 무시.",
            ))
    return out


def run_all_detectors(model: ProjectModel) -> list[Finding]:
    findings: list[Finding] = []
    findings += detect_pk_issues(model)
    findings += detect_transactional_misuse(model)
    # 데드코드: 사이드카 심볼 리졸브가 있으면 정밀 판정, 없으면 이름기반
    has_res = any(m.resolved_calls for ci in model.classes for m in ci.methods)
    if has_res:
        from services.javaparser_sidecar import precise_dead_code
        findings += precise_dead_code(model)
    else:
        findings += detect_dead_code(model)
    findings += detect_field_injection(model)
    findings += detect_n_plus_one(model)
    findings += detect_controller_holds_repository(model)
    findings += detect_service_write_without_tx(model)
    findings += detect_entity_in_api(model)
    findings += detect_god_class(model)
    findings += detect_too_many_params(model)
    findings += detect_public_mutable_field(model)
    findings += detect_setter_injection(model)
    findings += detect_wildcard_import(model)
    findings += detect_risky_catch(model)
    try:
        from services.depgraph import graph_findings   # 순환 의존성/고아 클래스
        findings += graph_findings(model)
    except Exception:
        pass
    # 심각도 정렬
    order = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda f: order.get(f.severity, 9))
    return findings


# ============================================================
# 확장 탐지기 카탈로그
# ============================================================
_INJECT_ANNS = {"Autowired", "Inject", "Resource"}
_WRITE_CALLS = {"save", "saveAll", "saveAndFlush", "delete", "deleteById",
                "deleteAll", "persist", "merge", "update", "remove"}


def detect_field_injection(model: ProjectModel) -> list[Finding]:
    out = []
    for ci in model.classes:
        for f in ci.fields:
            if any(a in _INJECT_ANNS for a in f.annotations):
                out.append(Finding(
                    "medium", "FIELD_INJECTION", f"{ci.file_path} > {ci.name}",
                    f"필드 주입(@{next(a for a in f.annotations if a in _INJECT_ANNS)}) "
                    f"'{f.name}'. 테스트/불변성/순환참조 측면에서 생성자 주입이 권장됨.",
                    "해당 의존성을 생성자 주입(final 필드 + 생성자)으로 전환.",
                ))
    return out


def detect_n_plus_one(model: ProjectModel) -> list[Finding]:
    """EAGER 연관관계 → N+1 위험. (ManyToOne/OneToOne 은 기본 EAGER)"""
    out = []
    for ci in model.of_stereotype("entity"):
        for f in ci.fields:
            for rel in ("ManyToOne", "OneToOne", "OneToMany", "ManyToMany"):
                if rel not in f.annotations:
                    continue
                fetch = (f.annotations[rel].get("fetch") or "").upper()
                default_eager = rel in ("ManyToOne", "OneToOne")
                is_eager = "EAGER" in fetch or (default_eager and "LAZY" not in fetch)
                if is_eager:
                    out.append(Finding(
                        "medium", "N_PLUS_ONE", f"{ci.file_path} > {ci.name}",
                        f"@{rel} '{f.name}' 가 EAGER 로딩(명시 또는 기본값) → 조회 시 N+1 쿼리 위험.",
                        "fetch=FetchType.LAZY 로 변경하고 필요한 곳에서 fetch join/@EntityGraph 사용.",
                    ))
    return out


def detect_controller_holds_repository(model: ProjectModel) -> list[Finding]:
    """Controller 가 Repository 를 직접 의존 → Service 레이어 우회."""
    out = []
    repo_names = {c.name for c in model.of_stereotype("repository")}
    for ci in model.of_stereotype("controller"):
        for f in ci.fields:
            t = f.type.split("<")[0].strip()
            if t in repo_names:
                out.append(Finding(
                    "medium", "LAYERING", f"{ci.file_path} > {ci.name}",
                    f"Controller 가 Repository '{t}' 를 직접 주입받음 → Service 레이어 우회.",
                    "Repository 접근을 Service 로 옮기고 Controller 는 Service 만 의존.",
                ))
    return out


def detect_service_write_without_tx(model: ProjectModel) -> list[Finding]:
    """Service 의 쓰기 메서드인데 @Transactional 없음."""
    out = []
    for ci in model.of_stereotype("service"):
        class_tx = "Transactional" in ci.annotations
        for m in ci.methods:
            if class_tx or "Transactional" in m.annotations:
                continue
            if any(call in _WRITE_CALLS for call in m.invokes):
                out.append(Finding(
                    "medium", "MISSING_TX", _loc(ci, m),
                    "쓰기성 호출(save/delete 등)이 있는 Service 메서드에 @Transactional 없음.",
                    "메서드 또는 클래스에 @Transactional 추가 (조회 전용은 readOnly=true).",
                ))
    return out


def detect_entity_in_api(model: ProjectModel) -> list[Finding]:
    """Controller 엔드포인트가 @Entity 를 그대로 반환 → 직렬화/지연로딩/노출 문제."""
    out = []
    entity_names = {c.name for c in model.of_stereotype("entity")}
    mapping = {"GetMapping", "PostMapping", "PutMapping", "DeleteMapping",
               "PatchMapping", "RequestMapping"}
    for ci in model.of_stereotype("controller"):
        for m in ci.methods:
            if not any(a in mapping for a in m.annotations):
                continue
            ret = m.return_type.split("<")[-1].strip(">").strip()  # ResponseEntity<User> 의 User
            if ret in entity_names:
                out.append(Finding(
                    "low", "ENTITY_IN_API", _loc(ci, m),
                    f"엔드포인트가 엔티티 '{ret}' 를 직접 반환 → 내부 스키마 노출/지연로딩 직렬화 문제.",
                    "응답 전용 DTO 로 변환해 반환.",
                ))
    return out


# ============================================================
# 카탈로그 2차: 코드 스멜
# ============================================================
_GOD_METHODS, _GOD_FIELDS, _MAX_PARAMS = 20, 15, 5


def detect_god_class(model: ProjectModel) -> list[Finding]:
    out = []
    for ci in model.classes:
        if ci.kind == "interface":
            continue
        if len(ci.methods) > _GOD_METHODS or len(ci.fields) > _GOD_FIELDS:
            out.append(Finding(
                "medium", "GOD_CLASS", f"{ci.file_path} > {ci.name}",
                f"메서드 {len(ci.methods)}개 / 필드 {len(ci.fields)}개 — 책임 과다(God class) 의심.",
                "단일 책임 기준으로 분리(여러 클래스/컴포넌트로 추출).",
            ))
    return out


def detect_too_many_params(model: ProjectModel) -> list[Finding]:
    out = []
    for ci in model.classes:
        for m in ci.methods:
            if len(m.params) > _MAX_PARAMS:
                out.append(Finding(
                    "low", "TOO_MANY_PARAMS", _loc(ci, m),
                    f"파라미터 {len(m.params)}개 — 너무 많음.",
                    "파라미터 객체(Parameter Object)나 빌더로 묶기.",
                ))
    return out


def detect_public_mutable_field(model: ProjectModel) -> list[Finding]:
    out = []
    for ci in model.classes:
        if ci.kind != "class":
            continue
        for f in ci.fields:
            if "public" in f.modifiers and "final" not in f.modifiers and "static" not in f.modifiers:
                out.append(Finding(
                    "low", "PUBLIC_FIELD", f"{ci.file_path} > {ci.name}",
                    f"public 가변 필드 '{f.name}' — 캡슐화 위반.",
                    "private 로 바꾸고 필요한 접근만 메서드로 노출.",
                ))
    return out


def detect_setter_injection(model: ProjectModel) -> list[Finding]:
    out = []
    for ci in model.classes:
        for m in ci.methods:
            if m.name.startswith("set") and any(a in _INJECT_ANNS for a in m.annotations):
                out.append(Finding(
                    "medium", "SETTER_INJECTION", _loc(ci, m),
                    "setter 주입 — 객체가 불완전 상태로 생성될 수 있음.",
                    "생성자 주입으로 전환.",
                ))
    return out


def detect_wildcard_import(model: ProjectModel) -> list[Finding]:
    out = []
    seen = set()
    for ci in model.classes:
        if ci.file_path in seen:
            continue
        seen.add(ci.file_path)
        for imp in ci.imports:
            if imp.endswith(".*"):
                out.append(Finding(
                    "low", "WILDCARD_IMPORT", ci.file_path,
                    f"와일드카드 import '{imp}' — 이름 충돌/가독성 저하.",
                    "사용하는 타입만 명시적으로 import.",
                ))
    return out


def detect_risky_catch(model: ProjectModel) -> list[Finding]:
    out = []
    for ci in model.classes:
        for m in ci.methods:
            if "empty" in m.risky_catches:
                out.append(Finding(
                    "medium", "EMPTY_CATCH", _loc(ci, m),
                    "빈 catch 블록 — 예외를 삼킴(silent failure).",
                    "최소한 로깅하거나 적절히 처리/전파.",
                ))
            if "broad" in m.risky_catches:
                out.append(Finding(
                    "low", "BROAD_CATCH", _loc(ci, m),
                    "Exception/Throwable 광범위 catch — 의도치 않은 예외까지 가림.",
                    "구체적 예외 타입으로 좁히기.",
                ))
    return out
