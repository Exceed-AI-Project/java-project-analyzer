"""
프로젝트 관리 유틸리티
- workspace 디렉토리 내 Java 프로젝트 스캔
- Git clone으로 새 프로젝트 추가
- 분석 캐시 메타데이터 관리
"""
import json
import shutil
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


# ============================================================
# 경로 상수
# ============================================================
WORKSPACE_DIR = Path(__file__).parent.parent / "workspace"
ANALYSIS_DIRNAME = ".analysis"
METADATA_FILENAME = "metadata.json"


# ============================================================
# 데이터 클래스
# ============================================================
@dataclass
class ProjectInfo:
    """프로젝트 정보"""
    name: str                          # 폴더명
    path: str                          # 절대 경로
    build_tool: str                    # maven / gradle / unknown
    git_url: Optional[str]             # clone 시 사용한 URL
    cloned_at: str                     # ISO 형식 일시
    analyzed: bool                     # 분석 완료 여부
    analyzed_at: Optional[str]         # 마지막 분석 일시
    file_count: int                    # .java 파일 개수


# ============================================================
# Workspace 초기화
# ============================================================
def ensure_workspace() -> Path:
    """workspace 디렉토리가 없으면 생성"""
    WORKSPACE_DIR.mkdir(exist_ok=True)
    return WORKSPACE_DIR


# ============================================================
# 프로젝트 감지
# ============================================================
def detect_build_tool(project_path: Path) -> str:
    """빌드 도구 종류 판별"""
    if (project_path / "pom.xml").exists():
        return "maven"
    if (project_path / "build.gradle").exists() or \
       (project_path / "build.gradle.kts").exists():
        return "gradle"
    return "unknown"


def is_java_project(project_path: Path) -> bool:
    """Java 프로젝트 여부 판별 (빌드 파일 존재 또는 .java 파일 존재)"""
    if detect_build_tool(project_path) != "unknown":
        return True
    # 빌드 파일 없어도 .java 파일이 있으면 Java 프로젝트로 인정
    java_files = list(project_path.rglob("*.java"))
    return len(java_files) > 0


def count_java_files(project_path: Path) -> int:
    """프로젝트 내 .java 파일 개수"""
    return len(list(project_path.rglob("*.java")))


# ============================================================
# 메타데이터 관리
# ============================================================
def get_metadata_path(project_path: Path) -> Path:
    """메타데이터 파일 경로"""
    return project_path / ANALYSIS_DIRNAME / METADATA_FILENAME


def load_metadata(project_path: Path) -> Optional[dict]:
    """메타데이터 로드 (없으면 None)"""
    meta_path = get_metadata_path(project_path)
    if not meta_path.exists():
        return None
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def save_metadata(project_path: Path, metadata: dict) -> None:
    """메타데이터 저장"""
    analysis_dir = project_path / ANALYSIS_DIRNAME
    analysis_dir.mkdir(exist_ok=True)
    meta_path = analysis_dir / METADATA_FILENAME
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)


# ============================================================
# 프로젝트 스캔
# ============================================================
def scan_projects() -> list[ProjectInfo]:
    """workspace 내 모든 Java 프로젝트 스캔"""
    ensure_workspace()
    projects: list[ProjectInfo] = []

    for entry in WORKSPACE_DIR.iterdir():
        if not entry.is_dir():
            continue
        if entry.name.startswith("."):
            continue
        if not is_java_project(entry):
            continue

        metadata = load_metadata(entry) or {}

        projects.append(ProjectInfo(
            name=entry.name,
            path=str(entry.absolute()),
            build_tool=detect_build_tool(entry),
            git_url=metadata.get("git_url"),
            cloned_at=metadata.get("cloned_at", "unknown"),
            analyzed=metadata.get("analyzed", False),
            analyzed_at=metadata.get("analyzed_at"),
            file_count=count_java_files(entry),
        ))

    # 최근 clone 순 정렬
    projects.sort(key=lambda p: p.cloned_at, reverse=True)
    return projects


# ============================================================
# Git Clone
# ============================================================
def parse_repo_name(git_url: str) -> str:
    """Git URL에서 저장소 이름 추출
    예: https://github.com/K-yoon03/ResumeAgent.git → ResumeAgent
    """
    name = git_url.rstrip("/").split("/")[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return name


def clone_project(git_url: str) -> tuple[bool, str, Optional[ProjectInfo]]:
    """Git 저장소를 workspace에 clone

    Returns:
        (성공 여부, 메시지, ProjectInfo or None)
    """
    ensure_workspace()
    repo_name = parse_repo_name(git_url)

    if not repo_name:
        return False, "Git URL에서 저장소 이름을 추출할 수 없어요", None

    target_path = WORKSPACE_DIR / repo_name

    if target_path.exists():
        return False, f"이미 '{repo_name}' 프로젝트가 존재해요", None

    try:
        result = subprocess.run(
            ["git", "clone", git_url, str(target_path)],
            capture_output=True,
            text=True,
            timeout=300,  # 5분 타임아웃
        )

        if result.returncode != 0:
            return False, f"Clone 실패: {result.stderr.strip()}", None

    except FileNotFoundError:
        return False, "Git이 설치되어 있지 않아요. https://git-scm.com 에서 설치해주세요", None
    except subprocess.TimeoutExpired:
        # 타임아웃 시 부분 다운로드 정리
        if target_path.exists():
            shutil.rmtree(target_path, ignore_errors=True)
        return False, "Clone 타임아웃 (5분 초과)", None
    except Exception as e:
        return False, f"Clone 중 오류: {e}", None

    if not is_java_project(target_path):
        # Java 프로젝트가 아니면 삭제하고 거부
        shutil.rmtree(target_path, ignore_errors=True)
        return False, "Java 프로젝트가 아니에요 (pom.xml/build.gradle/.java 파일 없음)", None

    # 메타데이터 저장
    metadata = {
        "git_url": git_url,
        "cloned_at": datetime.now().isoformat(timespec="seconds"),
        "analyzed": False,
        "analyzed_at": None,
    }
    save_metadata(target_path, metadata)

    project_info = ProjectInfo(
        name=repo_name,
        path=str(target_path.absolute()),
        build_tool=detect_build_tool(target_path),
        git_url=git_url,
        cloned_at=metadata["cloned_at"],
        analyzed=False,
        analyzed_at=None,
        file_count=count_java_files(target_path),
    )

    return True, f"'{repo_name}' clone 완료!", project_info


# ============================================================
# 프로젝트 삭제
# ============================================================
def delete_project(project_name: str) -> tuple[bool, str]:
    """프로젝트 폴더 통째로 삭제"""
    target_path = WORKSPACE_DIR / project_name
    if not target_path.exists():
        return False, "프로젝트가 존재하지 않아요"

    try:
        # Windows에서 .git 폴더 권한 문제 대응
        shutil.rmtree(target_path, ignore_errors=False, onerror=_handle_remove_readonly)
        return True, f"'{project_name}' 삭제 완료"
    except Exception as e:
        return False, f"삭제 실패: {e}"


def _handle_remove_readonly(func, path, exc_info):
    """Windows에서 읽기 전용 파일(.git 내부) 삭제 시 권한 변경"""
    import os
    import stat
    os.chmod(path, stat.S_IWRITE)
    func(path)