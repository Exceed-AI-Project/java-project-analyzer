"""
services/refactor_service.py — 규칙 기반 코드 품질 지표 분석
"""
import json
from pathlib import Path
from dataclasses import dataclass

# ============================================================
# 임계값 설정
# ============================================================
MAX_METHODS      = 7   # 클래스 메소드 수 경고 기준
MAX_DEPENDENCIES = 5   # 의존하는 클래스 수 경고 기준
MAX_PARAMS       = 4   # 메소드 파라미터 수 경고 기준

_CACHE_DIR = Path(__file__).parent.parent / "ast_results"


# ============================================================
# 데이터 클래스
# ============================================================
@dataclass
class MethodIssue:
    method_name: str
    param_count: int
    message: str


@dataclass
class ClassQuality:
    class_name: str
    stereotype: str
    method_count: int
    dependency_count: int
    method_issues: list[MethodIssue]

    # 경고 여부
    @property
    def has_too_many_methods(self) -> bool:
        return self.method_count > MAX_METHODS

    @property
    def has_too_many_dependencies(self) -> bool:
        return self.dependency_count > MAX_DEPENDENCIES

    @property
    def has_method_issues(self) -> bool:
        return len(self.method_issues) > 0

    @property
    def is_healthy(self) -> bool:
        return (
                not self.has_too_many_methods
                and not self.has_too_many_dependencies
                and not self.has_method_issues
        )


# ============================================================
# AST JSON 로드
# ============================================================
def _load_ast(project_name: str) -> dict:
    path = _CACHE_DIR / f"{project_name}.json"
    if not path.exists():
        return {"classes": [], "call_edges": []}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_class_names(project_name: str) -> list[str]:
    """클래스 이름 목록 반환"""
    data = _load_ast(project_name)
    return sorted({c["name"] for c in data.get("classes", [])})


# ============================================================
# 품질 지표 분석
# ============================================================
def analyze_class_quality(project_name: str, class_name: str) -> ClassQuality | None:
    """특정 클래스의 품질 지표 분석"""
    data = _load_ast(project_name)
    classes = data.get("classes", [])
    edges = data.get("call_edges", [])

    # 클래스 찾기
    target = next((c for c in classes if c["name"] == class_name), None)
    if target is None:
        return None

    # 메소드 수
    methods = target.get("methods", [])
    method_count = len(methods)

    # 의존성 수 (해당 클래스가 호출하는 클래스 수)
    deps = {
        e["callee_class"]
        for e in edges
        if e["caller_class"] == class_name and e["callee_class"] != class_name
    }
    dependency_count = len(deps)

    # 메소드별 파라미터 수 경고
    method_issues = []
    for m in methods:
        param_count = len(m.get("parameters", []))
        if param_count > MAX_PARAMS:
            method_issues.append(MethodIssue(
                method_name=m["name"],
                param_count=param_count,
                message=f"파라미터가 {param_count}개로 너무 많아요 (권장: {MAX_PARAMS}개 이하)",
            ))

    return ClassQuality(
        class_name=class_name,
        stereotype=target.get("stereotype", "unknown"),
        method_count=method_count,
        dependency_count=dependency_count,
        method_issues=method_issues,
    )


def get_project_summary(project_name: str) -> list[ClassQuality]:
    """프로젝트 전체 클래스 품질 요약"""
    names = get_class_names(project_name)
    results = []
    for name in names:
        q = analyze_class_quality(project_name, name)
        if q:
            results.append(q)
    return results