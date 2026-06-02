"""
질의 기반 코드 변경
자연어 질의 + AST 컨텍스트를 LLM 에 넣어 '통합 diff'로 받는다.
핵심 원칙: 자동 적용 금지. diff 를 만들어 사람이 검토 후 명시적 apply.
API 키는 세션에서 받은 검증된 키를 인자로 전달받는다.
"""
from __future__ import annotations
import difflib
from dataclasses import dataclass
from pathlib import Path

from models.analysis import ProjectModel, ClassInfo
from services import llm


@dataclass
class RefactorProposal:
    ok: bool
    file_path: str
    original: str
    proposed: str
    diff: str
    note: str = ""


def _class_context(ci: ClassInfo) -> str:
    lines = [f"class {ci.name} (stereotype={ci.stereotype}, pkg={ci.package})"]
    if ci.annotations:
        lines.append("  annotations: " + ", ".join("@" + a for a in ci.annotations))
    for f in ci.fields:
        anns = "".join("@" + a + " " for a in f.annotations)
        lines.append(f"  field: {anns}{f.type} {f.name}")
    for m in ci.methods:
        anns = "".join("@" + a + " " for a in m.annotations)
        ps = ", ".join(f"{p.type} {p.name}" for p in m.params)
        lines.append(f"  method: {anns}{m.return_type} {m.name}({ps})")
    return "\n".join(lines)


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip("\n")


def propose_change(query: str, file_path: str, model: ProjectModel,
                   api_key: str) -> RefactorProposal:
    try:
        original = Path(file_path).read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return RefactorProposal(False, file_path, "", "", "", f"파일 읽기 실패: {e}")

    if not api_key:
        return RefactorProposal(False, file_path, original, "", "", "LLM 비활성: 검증된 API 키 없음")

    rel = file_path.replace("\\", "/")
    ci = next((c for c in model.classes if rel.endswith(c.file_path.replace("\\", "/"))), None)
    ctx = _class_context(ci) if ci else "(구조 정보 없음)"

    system = ("You are a senior Java/Spring Boot refactoring assistant. "
              "Apply the requested change. Preserve behavior unless asked otherwise. "
              "Return ONLY the full modified Java file. No markdown, no explanation.")
    user = (f"# 요청\n{query}\n\n# 구조 컨텍스트(AST)\n{ctx}\n\n"
            f"# 원본 파일\n{original}\n\n위 요청을 반영한 전체 파일 내용만 출력.")

    try:
        proposed = _strip_fences(llm.chat(api_key, [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]))
    except Exception as e:
        return RefactorProposal(False, file_path, original, "", "", f"LLM 호출 실패: {e}")

    diff = "".join(difflib.unified_diff(
        original.splitlines(keepends=True), proposed.splitlines(keepends=True),
        fromfile=f"a/{ci.file_path if ci else file_path}",
        tofile=f"b/{ci.file_path if ci else file_path}",
    ))
    if not diff.strip():
        return RefactorProposal(True, file_path, original, proposed, "", "변경 없음.")
    return RefactorProposal(True, file_path, original, proposed, diff)


def apply_proposal(proposal: RefactorProposal) -> tuple[bool, str]:
    if not proposal.ok or not proposal.proposed:
        return False, "적용할 제안이 없음"
    try:
        Path(proposal.file_path).write_text(proposal.proposed, encoding="utf-8")
        return True, "적용 완료 (원본 파일 수정됨)"
    except Exception as e:
        return False, f"적용 실패: {e}"
