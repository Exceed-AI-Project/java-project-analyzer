"""
컴파일 검증
적용된 리팩토링이 실제로 컴파일되는지 프로젝트 자체 빌드 도구로 확인.
gradlew/mvnw(래퍼) 우선 → 시스템 gradle/mvn → 없으면 검증 생략(스킵).
"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

_TIMEOUT = 600  # 빌드는 의존성 다운로드까지 포함될 수 있어 넉넉히


def _exists(p: Path) -> bool:
    return p.exists()


def _build_command(root: Path) -> tuple[list[str] | None, str]:
    """프로젝트에 맞는 컴파일 명령 (argv 리스트, 도구명) 반환. 없으면 (None, 사유)."""
    is_win = sys.platform.startswith("win")
    # 래퍼(gradlew/mvnw)가 있으면 프로젝트 지정 버전이 보장되므로 시스템 도구보다 우선 사용.
    gw = root / ("gradlew.bat" if is_win else "gradlew")
    if _exists(gw):
        return ([str(gw), "compileJava", "-q", "--console=plain"], "gradlew")
    mw = root / ("mvnw.cmd" if is_win else "mvnw")
    if _exists(mw):
        return ([str(mw), "-q", "compile"], "mvnw")
    # 시스템 gradle / mvn 으로 폴백.
    import shutil
    if (root / "build.gradle").exists() or (root / "build.gradle.kts").exists():
        if shutil.which("gradle"):
            return (["gradle", "compileJava", "-q", "--console=plain"], "gradle")
    if (root / "pom.xml").exists():
        if shutil.which("mvn"):
            return (["mvn", "-q", "compile"], "mvn")
    return None, "빌드 도구 없음"


def compile_project(project_root: str) -> tuple[bool | None, str]:
    """반환: (성공여부, 로그).  None = 빌드도구 없어 검증 스킵."""
    root = Path(project_root)
    cmd, tool = _build_command(root)
    if cmd is None:
        return None, f"컴파일 검증 스킵 ({tool}) — gradlew/mvnw 가 있으면 자동 검증됩니다."
    try:
        proc = subprocess.run(
            cmd, cwd=str(root), capture_output=True, text=True, timeout=_TIMEOUT,
        )
    except FileNotFoundError:
        return None, f"{tool} 실행 불가 (PATH 확인)"
    except subprocess.TimeoutExpired:
        return False, f"{tool} 컴파일 타임아웃({_TIMEOUT}s)"

    log = (proc.stdout or "") + (proc.stderr or "")
    ok = proc.returncode == 0
    # 로그가 길면 에러 부분 위주로 잘라 반환
    tail = "\n".join(log.strip().splitlines()[-40:])
    return ok, f"[{tool}] {'성공' if ok else '실패'}\n{tail}"
