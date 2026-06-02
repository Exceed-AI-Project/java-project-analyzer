"""
JavaParser 사이드카 Python 래퍼
사이드카 jar 를 subprocess 로 실행 → JSON → ProjectModel 로 변환.
심볼 리졸브된 resolved_calls 를 활용해 데드코드 정밀도를 높인다.

jar 위치: 환경변수 JP_SIDECAR_JAR, 없으면 sidecar/target/java-analyzer-sidecar.jar
빌드: cd sidecar && mvn -q package  (Maven Central 접근 필요 → 로컬에서)
"""
from __future__ import annotations
import os
import json
import shutil
import subprocess
from pathlib import Path

from models.analysis import (
    ProjectModel, ClassInfo, FieldInfo, MethodInfo, ParamInfo,
)

_DEFAULT_JAR = Path(__file__).parent.parent / "sidecar" / "target" / "java-analyzer-sidecar.jar"
_TIMEOUT = 300


def jar_path() -> Path:
    return Path(os.getenv("JP_SIDECAR_JAR", str(_DEFAULT_JAR)))


def available() -> tuple[bool, str]:
    if shutil.which("java") is None:
        return False, "java 런타임 없음"
    if not jar_path().exists():
        return False, f"사이드카 jar 없음: {jar_path()} (cd sidecar && mvn -q package)"
    return True, "ok"


# ============================================================
# JSON → ProjectModel
# ============================================================
def _to_field(d: dict) -> FieldInfo:
    return FieldInfo(
        name=d["name"], type=d["type"],
        annotations=d.get("annotations", {}),
        modifiers=set(d.get("modifiers", [])),
    )


def _to_method(d: dict) -> MethodInfo:
    return MethodInfo(
        name=d["name"], return_type=d.get("returnType", "void"),
        params=[ParamInfo(p["name"], p["type"], p.get("annotations", {}))
                for p in d.get("params", [])],
        annotations=d.get("annotations", {}),
        modifiers=set(d.get("modifiers", [])),
        invokes=d.get("invokes", []),
        resolved_calls=d.get("resolvedCalls", []),
        risky_catches=d.get("riskyCatches", []),
    )


def _to_class(d: dict) -> ClassInfo:
    ci = ClassInfo(
        name=d["name"], kind=d.get("kind", "class"),
        package=d.get("package", ""), file_path=d.get("file", ""),
        annotations=d.get("annotations", {}),
        imports=d.get("imports", []),
    )
    ci.fields = [_to_field(f) for f in d.get("fields", [])]
    ci.methods = [_to_method(m) for m in d.get("methods", [])]
    return ci


def parse_payload(payload: dict) -> ProjectModel:
    model = ProjectModel()
    model.classes = [_to_class(c) for c in payload.get("classes", [])]
    model.parse_errors = [tuple(e) for e in payload.get("parseErrors", [])]
    return model


def build_model_javaparser(project_path: str | Path) -> ProjectModel:
    ok, why = available()
    if not ok:
        raise RuntimeError(why)
    proc = subprocess.run(
        ["java", "-jar", str(jar_path()), str(project_path)],
        capture_output=True, text=True, timeout=_TIMEOUT,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"사이드카 실행 실패: {proc.stderr.strip()[:300]}")
    return parse_payload(json.loads(proc.stdout))


# ============================================================
# 심볼 리졸브 기반 정밀 데드코드
# (resolved_calls 가 있으면 Owner.method 단위로 정확히 판정 → 동명 메서드 오탐 제거)
# ============================================================
from services.ast_analyzer import FRAMEWORK_ENTRY_ANNS
from models.analysis import Finding


def precise_dead_code(model: ProjectModel) -> list[Finding]:
    called_pairs: set[str] = set()   # "Owner.method"
    has_resolution = False
    for ci in model.classes:
        for m in ci.methods:
            if m.resolved_calls:
                has_resolution = True
            called_pairs.update(m.resolved_calls)

    if not has_resolution:
        # 사이드카 데이터가 아니면 정밀 판정 불가 → 빈 결과 (기존 이름기반 detect_dead_code 사용)
        return []

    out = []
    for ci in model.classes:
        if ci.kind == "interface":
            continue
        for m in ci.methods:
            if m.name in ("main", "toString", "equals", "hashCode"):
                continue
            if any(a in FRAMEWORK_ENTRY_ANNS for a in m.annotations):
                continue
            if f"{ci.name}.{m.name}" in called_pairs:
                continue
            out.append(Finding(
                "low", "DEAD_CODE_PRECISE", f"{ci.file_path} > {ci.name} > {m.name}()",
                "심볼 리졸브 기준 어디서도 호출되지 않는 메서드 (이름기반보다 정확).",
                "실제 미사용이면 제거. 리플렉션/외부호출이면 무시.",
            ))
    return out
