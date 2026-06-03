"""
LLM 클라이언트 헬퍼 (공용)
- API 키는 홈 화면에서 입력받아 세션에 보관.
- validate_key 로 실제 테스트 요청을 보내 확인되면 통과.
- 키 없거나 검증 실패면 LLM 기능 비활성, 정적 기능만 동작.
"""
from __future__ import annotations

try:
    from openai import OpenAI
    _OPENAI_AVAILABLE = True
except Exception:
    _OPENAI_AVAILABLE = False

DEFAULT_MODEL = "gpt-4o-mini"


def _friendly_error(e: Exception) -> str:
    """OpenAI 예외를 사용자에게 보여줄 짧은 한국어 메시지로 변환."""
    name, msg = type(e).__name__, str(e)
    if "Authentication" in name or "401" in msg:
        return "키가 유효하지 않음 (인증 실패)"
    if "RateLimit" in name or "429" in msg:
        return "사용량 한도 초과 또는 결제 미설정"
    if "Connection" in name or "Timeout" in name:
        return "OpenAI 연결 실패 (네트워크 확인)"
    return f"{name}: {msg}"


def validate_key(api_key: str, model: str = DEFAULT_MODEL) -> tuple[bool, str]:
    """실제 테스트 요청(1토큰)으로 키 동작 확인."""
    if not _OPENAI_AVAILABLE:
        return False, "openai 패키지 미설치"
    if not api_key or not api_key.strip():
        return False, "키가 비어 있음"
    try:
        client = OpenAI(api_key=api_key.strip())
        client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1, temperature=0,
        )
        return True, "API 키 확인됨 ✓"
    except Exception as e:
        return False, _friendly_error(e)


def chat(api_key: str, messages: list[dict], model: str = DEFAULT_MODEL,
         temperature: float = 0) -> str:
    """OpenAI Chat Completions 호출 후 본문 텍스트만 반환."""
    if not _OPENAI_AVAILABLE:
        raise RuntimeError("openai 패키지 미설치")
    client = OpenAI(api_key=api_key.strip())
    resp = client.chat.completions.create(
        model=model, messages=messages, temperature=temperature,
    )
    return resp.choices[0].message.content or ""
