"""
코드 임베딩 + FAISS 인덱스
- 파일 단위 청크(겹침 포함) → 임베딩 → FAISS 인덱스
- embedder 는 주입식: 실제는 OpenAI, 테스트는 가짜 임베더
- 인덱스/메타데이터를 .analysis/ 에 저장·로드 (영속화)

규칙으로 못 잡는 판단(네이밍/응집도/비즈니스 누락)은 이 인덱스로 맥락을 검색해 LLM 에 넘긴다.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
import faiss

from services import llm as _llm

ANALYSIS_DIR = ".analysis"
_INDEX_FILE = "code.index"
_META_FILE = "chunks.json"
_CHUNK_CHARS = 1200
_OVERLAP = 200
SKIP_DIRS = {"target", "build", "out", "bin", ".git", "node_modules", "__pycache__"}


@dataclass
class Chunk:
    id: int
    file: str
    start_line: int
    text: str


# ============================================================
# 청킹
# ============================================================
def _chunk_file(rel: str, text: str, start_id: int) -> list[Chunk]:
    """파일 1개를 _CHUNK_CHARS 단위로 잘라 청크 리스트 반환."""
    chunks = []
    lines = text.splitlines(keepends=True)
    buf, buf_start, cid = "", 1, start_id
    line_no = 1
    for ln in lines:
        if len(buf) + len(ln) > _CHUNK_CHARS and buf:
            chunks.append(Chunk(cid, rel, buf_start, buf))
            cid += 1
            # 청크 경계에서 문맥이 끊겨 검색이 미스나는 걸 줄이기 위해 끝부분을 다음 청크 머리에 겹침.
            buf = buf[-_OVERLAP:]
            buf_start = line_no
        buf += ln
        line_no += 1
    if buf.strip():
        chunks.append(Chunk(cid, rel, buf_start, buf))
    return chunks


def build_chunks(project_root: str) -> list[Chunk]:
    """프로젝트의 모든 .java 파일을 청킹한 결과 반환."""
    root = Path(project_root)
    chunks, cid = [], 0
    for path in root.rglob("*.java"):
        if any(p in SKIP_DIRS for p in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        new = _chunk_file(str(path.relative_to(root)), text, cid)
        chunks.extend(new)
        cid += len(new)
    return chunks


# ============================================================
# 임베더 (주입식)
# ============================================================
def openai_embedder(api_key: str, model: str = "text-embedding-3-small"):
    """OpenAI 임베딩 함수 반환. 테스트에서는 동일 시그니처의 가짜 함수로 교체 가능."""
    from openai import OpenAI
    client = OpenAI(api_key=api_key.strip())

    def embed(texts: list[str]) -> np.ndarray:
        resp = client.embeddings.create(model=model, input=texts)
        return np.array([d.embedding for d in resp.data], dtype="float32")
    return embed


# ============================================================
# 인덱스 빌드 / 저장 / 로드 / 검색
# ============================================================
def _normalize(v: np.ndarray) -> np.ndarray:
    faiss.normalize_L2(v)
    return v


def build_index(chunks: list[Chunk], embedder) -> tuple[faiss.Index, list[Chunk]]:
    """청크들을 임베딩해 FAISS 인덱스 구축. L2 정규화 후 내적으로 코사인 유사도를 흉내낸다."""
    vecs = _normalize(embedder([c.text for c in chunks]))
    index = faiss.IndexFlatIP(vecs.shape[1])
    index.add(vecs)
    return index, chunks


def save_index(project_root: str, index: faiss.Index, chunks: list[Chunk]) -> str:
    """인덱스 + 청크 메타를 .analysis/ 아래에 저장."""
    d = Path(project_root) / ANALYSIS_DIR
    d.mkdir(exist_ok=True)
    faiss.write_index(index, str(d / _INDEX_FILE))
    (d / _META_FILE).write_text(
        json.dumps([asdict(c) for c in chunks], ensure_ascii=False), encoding="utf-8")
    return str(d)


def load_index(project_root: str) -> tuple[faiss.Index, list[Chunk]] | None:
    """저장된 인덱스 + 청크 메타 복원. 없으면 None."""
    d = Path(project_root) / ANALYSIS_DIR
    if not (d / _INDEX_FILE).exists() or not (d / _META_FILE).exists():
        return None
    index = faiss.read_index(str(d / _INDEX_FILE))
    meta = json.loads((d / _META_FILE).read_text(encoding="utf-8"))
    return index, [Chunk(**m) for m in meta]


def search(index: faiss.Index, chunks: list[Chunk], query_vec: np.ndarray,
           k: int = 5) -> list[Chunk]:
    """질의 벡터로 상위 k 개 청크 검색."""
    q = _normalize(query_vec.reshape(1, -1).astype("float32"))
    _, idx = index.search(q, min(k, len(chunks)))
    return [chunks[i] for i in idx[0] if i >= 0]
