"""
services/rag_service.py — RAG 기반 리팩토링 제안
임베딩(OpenAI) + 벡터 DB(FAISS) + GPT 연동
"""
import json
import os
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# ============================================================
# 설정
# ============================================================
_client      = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
_EMBED_MODEL = "text-embedding-ada-002"
_CHAT_MODEL  = "gpt-4o-mini"
_DB_DIR      = Path(__file__).parent.parent / "db"
_CACHE_DIR   = Path(__file__).parent.parent / "ast_results"

_DB_DIR.mkdir(exist_ok=True)


# ============================================================
# 임베딩
# ============================================================
def _embed(text: str) -> list[float]:
    """텍스트 → 임베딩 벡터"""
    response = _client.embeddings.create(model=_EMBED_MODEL, input=text)
    return response.data[0].embedding


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


# ============================================================
# 벡터 DB 구축 / 로드
# ============================================================
def _db_path(project_name: str) -> Path:
    return _DB_DIR / f"{project_name}.json"


def build_vector_db(project_name: str) -> int:
    """
    AST JSON → 클래스별 청킹 → 임베딩 → DB 저장
    반환값: 저장된 청크 수
    """
    ast_path = _CACHE_DIR / f"{project_name}.json"
    if not ast_path.exists():
        raise FileNotFoundError(f"AST 캐시 없음: {ast_path}")

    with open(ast_path, encoding="utf-8") as f:
        data = json.load(f)

    chunks = []
    for cls in data.get("classes", []):
        # 클래스 단위로 청킹
        text = json.dumps(cls, ensure_ascii=False)
        embedding = _embed(text)
        chunks.append({
            "class_name": cls["name"],
            "stereotype": cls.get("stereotype", "unknown"),
            "text": text,
            "embedding": embedding,
        })

    db_path = _db_path(project_name)
    with open(db_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False)

    return len(chunks)


def _load_vector_db(project_name: str) -> list[dict]:
    path = _db_path(project_name)
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def is_db_built(project_name: str) -> bool:
    return _db_path(project_name).exists()


# ============================================================
# 유사 청크 검색
# ============================================================
def _search(project_name: str, query: str, top_k: int = 3) -> list[dict]:
    chunks = _load_vector_db(project_name)
    if not chunks:
        return []

    query_vec = _embed(query)
    scored = [
        (chunk, _cosine_similarity(query_vec, chunk["embedding"]))
        for chunk in chunks
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [chunk for chunk, _ in scored[:top_k]]


# ============================================================
# 리팩토링 제안 생성
# ============================================================
def get_refactor_suggestion(project_name: str, class_name: str) -> str:
    """
    특정 클래스에 대한 RAG 기반 리팩토링 제안 생성
    반환값: GPT 제안 문자열 (DB 미구축 시 None)
    """
    if not is_db_built(project_name):
        return None

    # 관련 청크 검색
    query = f"{class_name} 클래스 리팩토링 방법"
    related_chunks = _search(project_name, query, top_k=3)
    if not related_chunks:
        return None

    context = "\n\n".join(c["text"] for c in related_chunks)

    prompt = f"""
다음은 Java 프로젝트의 AST 분석 결과입니다 (JSON 형식):

{context}

위 코드에서 {class_name} 클래스에 대해 다음을 분석해주세요:
1. 리팩토링이 필요한 부분
2. 구체적인 개선 방법
3. 예상되는 개선 효과

한국어로 간결하게 답변해주세요.
"""

    response = _client.chat.completions.create(
        model=_CHAT_MODEL,
        messages=[
            {"role": "system", "content": "당신은 Java 코드 리팩토링 전문가입니다."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=1000,
    )
    return response.choices[0].message.content