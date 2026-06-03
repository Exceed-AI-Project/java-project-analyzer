"""
workspace 디렉토리에 clone 된 Java 프로젝트들의 목록/삭제 관리.

UI(홈 화면)와 워크스페이스(파일 시스템) 사이의 어댑터로,
project_scanner 의 분석 결과를 ProjectInfo 리스트로 모아 UI 에 전달한다.
"""
from models.project import ProjectInfo
from utils.workspace import ensure_workspace, load_metadata, WORKSPACE_DIR

from services.project_scanner import is_java_project, count_java_files, detect_build_info
import shutil

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
        build_info = detect_build_info(entry)

        projects.append(ProjectInfo(
            name=entry.name,
            path=str(entry.absolute()),
            build_info=build_info,
            git_url=metadata.get("git_url"),
            cloned_at=metadata.get("cloned_at", "unknown"),
            analyzed=metadata.get("analyzed", False),
            analyzed_at=metadata.get("analyzed_at"),
            file_count=count_java_files(entry),
        ))
    projects.sort(key=lambda p: p.cloned_at, reverse=True) # 최근 clone 순 정렬
    return projects


# ============================================================
# 프로젝트 삭제
# ============================================================
def delete_project(project_name: str) -> tuple[bool, str]:
    """프로젝트 폴더 통째로 삭제"""
    target_path = WORKSPACE_DIR / project_name
    if not target_path.exists():
        return False, "프로젝트가 존재하지 않아요"

    try:
        shutil.rmtree(target_path, ignore_errors=False, onexc=_handle_remove_readonly)
        return True, f"'{project_name}' 삭제 완료"
    except Exception as e:
        return False, f"삭제 실패: {e}"


def _handle_remove_readonly(func, path, exc):
    """Windows에서 읽기 전용 파일(.git 내부) 삭제 시 권한 변경"""
    import os, stat
    os.chmod(path, stat.S_IWRITE)
    func(path)