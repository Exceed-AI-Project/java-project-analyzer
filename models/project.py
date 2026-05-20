from dataclasses import dataclass, field, asdict
from typing import Optional
from pathlib import Path

# ============================================================
# 데이터 클래스
# ============================================================
@dataclass
class BuildModule:
    """단일 빌드 모듈 정보"""
    relative_path: str          # 프로젝트 루트 기준 상대 경로 ("." or "modules/api")
    build_tool: str             # maven / gradle
    build_file: str             # pom.xml / build.gradle / build.gradle.kts
    java_file_count: int        # 이 모듈 내 .java 파일 개수


@dataclass
class BuildInfo:
    """프로젝트 전체 빌드 정보 (멀티모듈 포함)"""
    primary_tool: str                          # maven / gradle / mixed / unknown
    is_multi_module: bool                      # 모듈 2개 이상이면 True
    modules: list[BuildModule] = field(default_factory=list)

    @property
    def summary(self) -> str:
        """UI 표시용 요약 문자열"""
        if self.primary_tool == "unknown":
            return "unknown"
        if self.is_multi_module:
            return f"{self.primary_tool} (멀티모듈 {len(self.modules)}개)"
        return self.primary_tool


@dataclass
class ProjectInfo:
    """프로젝트 정보"""
    name: str                          # 폴더명
    path: Path                         # 절대 경로
    build_info: BuildInfo              # 빌드 정보 (멀티모듈 포함)
    git_url: Optional[str]             # clone 시 사용한 URL
    cloned_at: str                     # ISO 형식 일시
    analyzed: bool                     # 분석 완료 여부
    analyzed_at: Optional[str]         # 마지막 분석 일시
    file_count: int                    # 전체 .java 파일 개수