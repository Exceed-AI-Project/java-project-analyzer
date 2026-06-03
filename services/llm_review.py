"""
임베딩 맥락 기반 LLM 코드 리뷰
규칙으로 못 잡는 판단(네이밍/응집도/비즈니스 로직 누락/잠재 버그)을
관련 코드 청크를 검색해 맥락으로 넣고 LLM 에게 맡긴다.

규칙(ast_analyzer)과 보완 관계: 규칙은 결정론적/확실한 것, 이쪽은 퍼지한 판단.
"""
from __future__ import annotations
import json
import numpy as np

from services import embedding as emb
from services import llm as _llm

_REVIEW_PROMPT = (
    "You are a senior Java/Spring reviewer. Using the provided code context, "
    "identify JUDGMENT-LEVEL issues that static rules miss: unclear naming, weak cohesion, "
    "likely business-logic gaps, subtle bugs, missing validation. "
    "Be conservative — only report what you're fairly confident about. "
    "Output ONLY a JSON array; each item: "
    '{"severity":"high|medium|low","category":"...","where":"file or class","message":"...","suggestion":"..."}'
)


def _strip(t: str) -> str:
    """LLM 응답에서 ```...``` 코드 펜스를 떼고 JSON 본문만 반환."""
    t = t.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


def review(project_root: str, api_key: str, focus: str = "",
           k: int = 6) -> tuple[list[dict], str]:
    """focus: 검색 질의(빈값이면 일반 리뷰). 반환: (이슈 리스트, 노트)"""
    loaded = emb.load_index(project_root)
    if loaded is None:
        return [], "인덱스 없음 — 먼저 임베딩 인덱스를 생성하세요."
    index, chunks = loaded

    embedder = emb.openai_embedder(api_key)
    query = focus or "code quality, naming, cohesion, business logic gaps, potential bugs"
    qvec = embedder([query])[0]
    hits = emb.search(index, chunks, qvec, k=k)

    context = "\n\n".join(f"// {c.file}:{c.start_line}\n{c.text}" for c in hits)
    try:
        raw = _llm.chat(api_key, [
            {"role": "system", "content": _REVIEW_PROMPT},
            {"role": "user", "content": f"질의: {query}\n\n# 코드 맥락\n{context}\n\nJSON 배열만 출력."},
        ])
        issues = json.loads(_strip(raw))
        if not isinstance(issues, list):
            return [], "LLM 이 배열이 아닌 응답 반환"
    except Exception as e:
        return [], f"LLM 리뷰 실패: {e}"

    return issues, f"{len(hits)}개 청크 맥락으로 {len(issues)}건 리뷰"
