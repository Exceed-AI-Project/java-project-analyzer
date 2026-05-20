from pathlib import Path

AST_CACHE_DIR = Path(__file__).parent.parent / "ast_results"


def ensure_cache_dir() -> Path:
    AST_CACHE_DIR.mkdir(exist_ok=True)
    return AST_CACHE_DIR


def get_cache_path(project_name: str) -> Path:
    return AST_CACHE_DIR / f"{project_name}.json"


def delete_cache(project_name: str) -> None:
    path = get_cache_path(project_name)
    if path.exists():
        path.unlink()