"""
services/refactor_service.py — 규칙 기반 코드 품질 지표 분석

리팩토링 4가지 관점:
    1. 이 코드가 뭐 하는 애인지 모를 때 → 모호한 메소드명 탐지
    2. 데드코드                         → 아무도 호출 안 하는 메소드 탐지 (메소드 레벨)
    3. 모듈 통합                         → God Class / Tiny Class + 의존 클래스 목록
    4. 로직 개선                         → 파라미터 초과 메소드 + 실제 시그니처
"""
import json
from pathlib import Path
from dataclasses import dataclass, field

# ============================================================
# 임계값 설정
# ============================================================
MAX_METHODS          = 7   # 클래스 메소드 수 상한 (초과 → God Class)
MIN_METHODS          = 2   # 클래스 메소드 수 하한 (미만 → Tiny Class)
MAX_DEPENDENCIES     = 5   # 의존하는 클래스 수 경고 기준
MAX_PARAMS           = 4   # 메소드 파라미터 수 경고 기준
MIN_METHOD_NAME_LEN  = 3   # 메소드 이름 최소 길이 (미만 → 모호한 이름)

_CACHE_DIR = Path(__file__).parent.parent / "ast_results"


# ============================================================
# 데이터 클래스
# ============================================================
@dataclass
class MethodIssue:
    """로직 개선 - 파라미터 초과"""
    method_name: str
    param_count: int
    parameters: list[str]       # "name: type" 형태 문자열 목록
    message: str


@dataclass
class DeadMethod:
    """데드코드 - 아무도 호출하지 않는 메소드"""
    method_name: str
    return_type: str
    parameters: list[str]       # "name: type" 형태 문자열 목록


@dataclass
class UnclearNameIssue:
    """이 코드가 뭐 하는 애인지 모를 때 - 모호한 메소드명"""
    method_name: str
    message: str
    suggestion: str


@dataclass
class ClassQuality:
    class_name: str
    stereotype: str

    # 모듈 통합
    method_count: int
    dependency_count: int
    dep_classes: list[str] = field(default_factory=list)
    callers: list[str]     = field(default_factory=list)

    # 로직 개선 - 파라미터 초과
    method_issues: list[MethodIssue] = field(default_factory=list)

    # 데드코드 - 호출되지 않는 메소드 목록
    dead_methods: list[DeadMethod] = field(default_factory=list)

    # 코드 가독성 - 모호한 메소드명
    unclear_names: list[UnclearNameIssue] = field(default_factory=list)

    # ── 경고 여부 ──────────────────────────────────────────

    @property
    def has_too_many_methods(self) -> bool:
        return self.method_count > MAX_METHODS

    @property
    def is_tiny_class(self) -> bool:
        return self.method_count < MIN_METHODS

    @property
    def has_too_many_dependencies(self) -> bool:
        return self.dependency_count > MAX_DEPENDENCIES

    @property
    def has_method_issues(self) -> bool:
        return len(self.method_issues) > 0

    @property
    def has_dead_methods(self) -> bool:
        return len(self.dead_methods) > 0

    @property
    def has_unclear_names(self) -> bool:
        return len(self.unclear_names) > 0

    @property
    def is_healthy(self) -> bool:
        return (
                not self.has_too_many_methods
                and not self.is_tiny_class
                and not self.has_too_many_dependencies
                and not self.has_method_issues
                and not self.has_dead_methods
                and not self.has_unclear_names
        )


# ============================================================
# AST JSON 로드
# ============================================================
def _load_ast(project_name: str) -> dict:
    path = _CACHE_DIR / f"{project_name}.json"
    if not path.exists():
        return {"classes": [], "call_edges": [], "errors": []}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_class_names(project_name: str) -> list[str]:
    data = _load_ast(project_name)
    return sorted({c["name"] for c in data.get("classes", [])})


# ============================================================
# 파라미터 포맷 헬퍼
# ============================================================
def _fmt_params(params: list) -> list[str]:
    """parameters 필드를 'name: type' 문자열 목록으로 변환"""
    result = []
    for p in params:
        if isinstance(p, dict):
            name = p.get("name", "?")
            ptype = p.get("type", "?")
            result.append(f"{name}: {ptype}")
        else:
            result.append(str(p))
    return result


# ============================================================
# 모호한 메소드명 힌트
# ============================================================
def _make_suggestion(name: str) -> str:
    if len(name) == 1:
        return "단일 문자 이름은 의미를 전달하지 못해요. 동사+명사 형태로 바꿔보세요 (예: processNote, fetchUser)"
    return "너무 짧은 이름이에요. 이 메소드가 무엇을 하는지 나타내는 단어를 추가해보세요"


# ============================================================
# 품질 지표 분석
# ============================================================
def analyze_class_quality(
        project_name: str,
        class_name: str,
        referenced_methods: dict[str, set[str]] | None = None,
        caller_map: dict[str, list[str]] | None = None,
) -> ClassQuality | None:
    """
    특정 클래스의 품질 지표 분석
    referenced_methods: {class_name: {호출된 메소드명 집합}} — 데드메소드 탐지용
    caller_map: {class_name: [호출하는 클래스 목록]}
    """
    data    = _load_ast(project_name)
    classes = data.get("classes", [])
    edges   = data.get("call_edges", [])

    target = next((c for c in classes if c["name"] == class_name), None)
    if target is None:
        return None

    methods = target.get("methods", [])

    # ── 모듈 통합: 메소드 수 + 의존 클래스 목록 ──────────
    method_count = len(methods)
    dep_classes = sorted({
        e["callee_class"]
        for e in edges
        if e["caller_class"] == class_name and e["callee_class"] != class_name
    })
    dependency_count = len(dep_classes)

    # ── 호출하는 클래스 목록 ──────────────────────────────
    if caller_map is None:
        caller_map = {}
        for e in edges:
            if e["caller_class"] != e["callee_class"]:
                caller_map.setdefault(e["callee_class"], [])
                caller_map[e["callee_class"]].append(e["caller_class"])
    callers = sorted(set(caller_map.get(class_name, [])))

    # ── 데드코드: 호출되지 않는 메소드 탐지 ──────────────
    if referenced_methods is None:
        referenced_methods = {}
        for e in edges:
            referenced_methods.setdefault(e["callee_class"], set())
            if e.get("callee_method"):
                referenced_methods[e["callee_class"]].add(e["callee_method"])

    called_in_this_class = referenced_methods.get(class_name, set())
    dead_methods = []
    for m in methods:
        mname = m["name"]
        # 생성자, main, getter/setter 는 제외
        if mname in ("main",) or mname.startswith(("get", "set", "is")):
            continue
        if mname not in called_in_this_class:
            dead_methods.append(DeadMethod(
                method_name=mname,
                return_type=m.get("return_type", "void"),
                parameters=_fmt_params(m.get("parameters", [])),
            ))

    # ── 로직 개선: 파라미터 초과 ──────────────────────────
    method_issues = []
    for m in methods:
        params = m.get("parameters", [])
        if len(params) > MAX_PARAMS:
            method_issues.append(MethodIssue(
                method_name=m["name"],
                param_count=len(params),
                parameters=_fmt_params(params),
                message=f"파라미터가 {len(params)}개로 너무 많아요 (권장: {MAX_PARAMS}개 이하)",
            ))

    # ── 코드 가독성: 모호한 메소드명 ─────────────────────
    unclear_names = []
    for m in methods:
        name = m["name"]
        if len(name) < MIN_METHOD_NAME_LEN:
            unclear_names.append(UnclearNameIssue(
                method_name=name,
                message=f"메소드명 '{name}'이 너무 짧아서 역할을 파악하기 어려워요",
                suggestion=_make_suggestion(name),
            ))

    return ClassQuality(
        class_name=class_name,
        stereotype=target.get("stereotype", "unknown"),
        method_count=method_count,
        dependency_count=dependency_count,
        dep_classes=dep_classes,
        callers=callers,
        method_issues=method_issues,
        dead_methods=dead_methods,
        unclear_names=unclear_names,
    )


def get_project_summary(project_name: str) -> list[ClassQuality]:
    data  = _load_ast(project_name)
    edges = data.get("call_edges", [])

    # 메소드 레벨 데드코드 판단용
    referenced_methods: dict[str, set[str]] = {}
    for e in edges:
        referenced_methods.setdefault(e["callee_class"], set())
        if e.get("callee_method"):
            referenced_methods[e["callee_class"]].add(e["callee_method"])

    # 호출자 맵
    caller_map: dict[str, list[str]] = {}
    for e in edges:
        if e["caller_class"] != e["callee_class"]:
            caller_map.setdefault(e["callee_class"], [])
            caller_map[e["callee_class"]].append(e["caller_class"])

    names   = get_class_names(project_name)
    results = []
    for name in names:
        q = analyze_class_quality(project_name, name, referenced_methods, caller_map)
        if q:
            results.append(q)
    return results