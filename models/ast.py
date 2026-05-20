"""
AST 분석 결과를 담는 데이터 모델.

서비스 계층에서 추출하고, UI에서 표시할 때 사용한다.
"""
from dataclasses import dataclass, field
from typing import Literal, Optional


# ============================================================
# 타입 별칭
# ============================================================
Stereotype = Literal[
    "controller",   # @Controller, @RestController
    "service",      # @Service
    "repository",   # @Repository, JpaRepository 상속
    "entity",       # @Entity
    "dto",          # 패키지명 기반
    "config",       # @Configuration
    "component",    # @Component
    "exception",    # ...Exception 상속
    "test",         # @Test, ApplicationTests
    "unknown",      # 판별 실패
]

ClassKind = Literal["class", "interface", "enum", "record"]

AccessModifier = Literal["public", "protected", "private", "package"]


# ============================================================
# 메서드
# ============================================================
@dataclass
class JavaParameter:
    name: str
    type: str


@dataclass
class JavaMethod:
    class_name: str
    name: str
    return_type: str
    parameters: list[JavaParameter] = field(default_factory=list)
    access: AccessModifier = "package"
    annotations: list[str] = field(default_factory=list)


# ============================================================
# 클래스
# ============================================================
@dataclass
class JavaClass:
    file_path: str
    name: str
    package: str
    kind: ClassKind
    stereotype: Stereotype = "unknown"
    annotations: list[str] = field(default_factory=list)
    extends: Optional[str] = None
    implements: list[str] = field(default_factory=list)
    methods: list[JavaMethod] = field(default_factory=list)


# ============================================================
# 호출 관계 (Call Graph)
# ============================================================
@dataclass
class CallEdge:
    """메서드 A → 메서드 B 호출 1건"""
    caller_class: str        # 호출하는 쪽 클래스
    caller_method: str       # 호출하는 쪽 메서드
    callee_class: str        # 호출되는 쪽 클래스 (추론 실패 시 변수명 그대로)
    callee_method: str       # 호출되는 쪽 메서드
    is_resolved: bool        # callee_class를 실제 클래스로 매핑했는지 여부


# ============================================================
# 분석 결과 전체
# ============================================================
@dataclass
class ParseError:
    file_path: str
    error: str


@dataclass
class AstAnalysisResult:
    classes: list[JavaClass] = field(default_factory=list)
    call_edges: list[CallEdge] = field(default_factory=list)
    errors: list[ParseError] = field(default_factory=list)

    @property
    def methods(self) -> list[JavaMethod]:
        return [m for c in self.classes for m in c.methods]