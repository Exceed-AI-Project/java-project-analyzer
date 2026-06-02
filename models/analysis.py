"""
AST 분석 공통 데이터 모델
ast_analyzer 가 채우고, api_simulator / query_refactor / UI 가 소비한다.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


# ============================================================
# 코드 구조 모델
# ============================================================
@dataclass
class FieldInfo:
    name: str
    type: str                                   # 예: "String", "Long", "List<Order>"
    annotations: dict[str, dict] = field(default_factory=dict)  # ann_name -> {param: value}
    modifiers: set[str] = field(default_factory=set)
    line: int = 0


@dataclass
class ParamInfo:
    name: str
    type: str
    annotations: dict[str, dict] = field(default_factory=dict)


@dataclass
class MethodInfo:
    name: str
    return_type: str
    params: list[ParamInfo] = field(default_factory=list)
    annotations: dict[str, dict] = field(default_factory=dict)
    modifiers: set[str] = field(default_factory=set)
    invokes: list[str] = field(default_factory=list)   # body 안에서 호출한 메서드명들
    resolved_calls: list[str] = field(default_factory=list)  # 심볼 리졸브된 "Owner.method" (사이드카 전용)
    risky_catches: list[str] = field(default_factory=list)  # 'empty' / 'broad'
    line: int = 0


@dataclass
class ClassInfo:
    name: str
    kind: str                                   # class / interface / enum
    package: str
    file_path: str
    annotations: dict[str, dict] = field(default_factory=dict)
    extends: Optional[str] = None
    implements: list[str] = field(default_factory=list)
    fields: list[FieldInfo] = field(default_factory=list)
    methods: list[MethodInfo] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)

    @property
    def stereotype(self) -> str:
        """Spring 스테레오타입 추정"""
        anns = self.annotations
        if "Entity" in anns:
            return "entity"
        if "RestController" in anns or "Controller" in anns:
            return "controller"
        if "Service" in anns:
            return "service"
        if "Repository" in anns:
            return "repository"
        if any(a in anns for a in ("Configuration", "Component", "Bean")):
            return "component"
        # 어노테이션 없어도 이름/상속으로 추정
        if self.name.endswith(("Dto", "DTO", "Request", "Response", "Form")):
            return "dto"
        if self.implements and any("Repository" in i for i in self.implements):
            return "repository"
        return "other"


@dataclass
class ProjectModel:
    classes: list[ClassInfo] = field(default_factory=list)
    parse_errors: list[tuple[str, str]] = field(default_factory=list)  # (file, error)

    @property
    def by_name(self) -> dict[str, ClassInfo]:
        return {c.name: c for c in self.classes}

    def of_stereotype(self, stereotype: str) -> list[ClassInfo]:
        return [c for c in self.classes if c.stereotype == stereotype]


# ============================================================
# 분석 결과
# ============================================================
@dataclass
class Finding:
    severity: str        # high / medium / low
    category: str        # PK_MISSING / TRANSACTIONAL / DEAD_CODE / CONSTRAINT / TYPE ...
    location: str        # "파일 > 클래스 > 메서드"
    message: str
    suggestion: str = ""
