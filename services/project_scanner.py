"""
Git 저장소 clone, Java 프로젝트 판별, 빌드 모듈(Maven/Gradle) 탐색.
"""

from models.project import ProjectInfo, BuildModule, BuildInfo
from utils.workspace import ensure_workspace, save_metadata, WORKSPACE_DIR

from typing import Optional
from pathlib import Path
import subprocess
from datetime import datetime
import shutil


# ============================================================
# 전역 변수
# ============================================================

# 빌드 파일 우선순위 (위에 있을수록 우선)
BUILD_FILES = {
    "pom.xml": "maven",
    "build.gradle.kts": "gradle",
    "build.gradle": "gradle",
}

# 탐색 시 스킵할 폴더 (속도 + 노이즈 감소)
SKIP_DIRS = {
    "target", "build", "out", "bin", "dist",     # 빌드 결과물
    "node_modules", ".gradle", ".m2",            # 의존성/캐시
    ".idea", ".vscode", ".settings", ".eclipse", # IDE
    ".git", ".analysis", "__pycache__",          # 기타
    "test-fixtures", "fixtures",                 # 테스트 픽스처는 보통 분석 대상 아님
}
# 멀티모듈 깊이 제한: Maven/Gradle 멀티모듈은 보통 2~3단계라 4면 충분, 무한 재귀 방지.
MAX_SCAN_DEPTH = 4

# git clone 은 큰 저장소에서 오래 걸릴 수 있어 5분까지 허용.
GITCLONE_TIMEOUT = 300


# ============================================================
# 빌드 모듈 탐색 (재귀)
# ============================================================
def _find_build_modules(
    current: Path,
    project_root: Path,
    depth: int,
    found: list[BuildModule],
) -> None:
    """현재 디렉토리에서 빌드 파일을 찾고, 없으면 하위로 재귀

    빌드 파일을 찾으면 해당 디렉토리의 하위는 더 안 들어감 (모듈 단위로 인식)
    """
    if depth > MAX_SCAN_DEPTH:
        return

    # OS 간 경로 표기를 통일하기 위해 as_posix() 로 슬래시 형식 사용.
    for build_file, tool in BUILD_FILES.items():
        if (current / build_file).exists():
            relative = current.relative_to(project_root).as_posix()
            if relative == ".":
                relative = "."
            found.append(BuildModule(
                relative_path=relative,
                build_tool=tool,
                build_file=build_file,
                java_file_count=_count_java_in_dir(current),
            ))
            # 같은 폴더의 다른 빌드 파일은 우선순위가 높은 첫 매치만 채택.
            break

    # 하위 디렉토리 탐색
    try:
        for child in current.iterdir():
            if not child.is_dir():
                continue
            if child.name in SKIP_DIRS:
                continue
            if child.name.startswith("."):
                continue
            _find_build_modules(child, project_root, depth + 1, found)
    except (PermissionError, OSError):
        # 권한 문제 등으로 못 읽는 폴더는 그냥 스킵
        pass


def _count_java_in_dir(directory: Path) -> int:
    """특정 디렉토리 내 .java 파일 개수 (SKIP_DIRS 제외)"""
    count = 0
    try:
        for path in directory.rglob("*.java"):
            # SKIP_DIRS 안의 파일은 제외
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            count += 1
    except (PermissionError, OSError):
        pass
    return count


def detect_build_info(project_path: Path) -> BuildInfo:
    """프로젝트 빌드 정보 종합 분석 (멀티모듈 지원)"""
    modules: list[BuildModule] = []
    _find_build_modules(project_path, project_path, depth=0, found=modules)

    if not modules:
        return BuildInfo(primary_tool="unknown", is_multi_module=False, modules=[])

    # 주 빌드 도구 결정
    tools = {m.build_tool for m in modules}
    if len(tools) == 1:
        primary = next(iter(tools))
    else:
        # maven/gradle 혼합인 경우
        primary = "mixed"

    # 모듈을 상대 경로 기준 정렬 (루트가 항상 첫번째로 오도록)
    modules.sort(key=lambda m: (m.relative_path != ".", m.relative_path))

    return BuildInfo(
        primary_tool=primary,
        is_multi_module=len(modules) > 1,
        modules=modules,
    )


# ============================================================
# Java 프로젝트 판별
# ============================================================
def is_java_project(project_path: Path) -> bool:
    """Java 프로젝트 여부 판별

    1) 빌드 파일이 어딘가 있거나
    2) .java 파일이 어딘가 있으면 Java 프로젝트로 간주
    """
    build_info = detect_build_info(project_path)
    if build_info.primary_tool != "unknown":
        return True
    # 빌드 파일 없어도 .java 파일이 있으면 인정
    return _count_java_in_dir(project_path) > 0


def count_java_files(project_path: Path) -> int:
    """프로젝트 내 .java 파일 총 개수 (SKIP_DIRS 제외)"""
    return _count_java_in_dir(project_path)

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
            timeout=GITCLONE_TIMEOUT,  # 5분 타임아웃
        )

        if result.returncode != 0:
            return False, f"Clone 실패: {result.stderr.strip()}", None
    except FileNotFoundError:
        return False, "Git이 설치되어 있지 않아요. https://git-scm.com 에서 설치해주세요", None
    except subprocess.TimeoutExpired:
        # 부분 clone 된 폴더가 남으면 다음 시도가 "이미 존재" 로 막히므로 정리.
        if target_path.exists():
            shutil.rmtree(target_path, ignore_errors=True)
        return False, "Clone 타임아웃 (5분 초과)", None
    except Exception as e:
        return False, f"Clone 중 오류: {e}", None

    if not is_java_project(target_path):
        shutil.rmtree(target_path, ignore_errors=True)
        return False, "Java 프로젝트가 아니에요 (빌드 파일/.java 파일 없음)", None

    # 메타데이터 저장
    metadata = {
        "git_url": git_url,
        "cloned_at": datetime.now().isoformat(timespec="seconds"),
        "analyzed": False,
        "analyzed_at": None,
    }
    save_metadata(target_path, metadata)

    build_info = detect_build_info(target_path)

    project_info = ProjectInfo(
        name=repo_name,
        path=str(target_path.absolute()),
        build_info=build_info,
        git_url=git_url,
        cloned_at=metadata["cloned_at"],
        analyzed=False,
        analyzed_at=None,
        file_count=count_java_files(target_path),
    )

    return True, f"'{repo_name}' clone 완료!", project_info
