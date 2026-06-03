"""
workspace 경로 상수와 프로젝트별 메타데이터(.analysis/metadata.json) I/O.

메타데이터에는 git_url, cloned_at, 분석 여부 등이 들어가며 새로고침/재시작 후에도
프로젝트 상태를 복원하기 위해 파일로 영속한다.
"""
from pathlib import Path
from typing import Optional
import json

# ============================================================
# 경로 상수
# ============================================================
WORKSPACE_DIR = Path(__file__).parent.parent / "workspace"
ANALYSIS_DIRNAME = ".analysis"
METADATA_FILENAME = "metadata.json"

# ============================================================
# Workspace 초기화
# ============================================================
def ensure_workspace() -> Path:
    """workspace 디렉토리가 없으면 생성"""
    WORKSPACE_DIR.mkdir(exist_ok=True)
    return WORKSPACE_DIR

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
