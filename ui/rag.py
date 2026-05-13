import streamlit as st
import streamlit.components.v1 as components

from ui.css.rag import RAG_CSS
from model.dummy_data import _DUMMY_CLASSES, _DUMMY_METHODS, _DUMMY_ENDPOINTS

_SUGGESTED_QUESTIONS = [
    "UserService 의존성을 가진 클래스는?",
    "OrderController의 역할을 설명해줘",
    "리팩토링이 필요한 클래스가 있나요?",
    "가장 복잡한 메소드는?",
]

_HTTP_COLORS = {
    "GET":    "#4caf50",
    "POST":   "#2196f3",
    "PUT":    "#ff9800",
    "DELETE": "#f44336",
    "PATCH":  "#9c27b0",
}

_TYPE_COLORS = {
    "Class":     "#4e9af1",
    "Interface": "#7c9ef5",
}


def _type_badge(label: str, color: str) -> str:
    return (
        f'<span style="background:{color};color:#fff;font-size:0.72rem;'
        f'padding:1px 8px;border-radius:10px;white-space:nowrap;">{label}</span>'
    )


def _render_info_panel() -> None:
    # ── 카드 1: 클래스 ───────────────────────────────
    with st.container(border=True):
        st.markdown(f"**📦 클래스 {len(_DUMMY_CLASSES)}개**")
        first, rest = _DUMMY_CLASSES[:5], _DUMMY_CLASSES[5:]
        for c in first:
            color = _TYPE_COLORS.get(c["타입"], "#888")
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;'
                f'align-items:center;margin-bottom:3px;">'
                f'<span style="font-size:0.83rem;">{c["클래스명"]}</span>'
                f'{_type_badge(c["타입"], color)}</div>',
                unsafe_allow_html=True,
            )
        if rest:
            with st.expander(f"+ {len(rest)}개 더보기"):
                for c in rest:
                    color = _TYPE_COLORS.get(c["타입"], "#888")
                    st.markdown(
                        f'<div style="display:flex;justify-content:space-between;'
                        f'align-items:center;margin-bottom:3px;">'
                        f'<span style="font-size:0.83rem;">{c["클래스명"]}</span>'
                        f'{_type_badge(c["타입"], color)}</div>',
                        unsafe_allow_html=True,
                    )

    # ── 카드 2: 메소드 ───────────────────────────────
    with st.container(border=True):
        st.markdown(f"**⚙️ 메소드 {len(_DUMMY_METHODS)}개**")
        first_m, rest_m = _DUMMY_METHODS[:5], _DUMMY_METHODS[5:]
        for m in first_m:
            st.markdown(
                f'<div style="margin-bottom:3px;">'
                f'<span style="font-size:0.83rem;font-weight:600;">{m["메소드명"]}</span>'
                f'<span style="color:rgba(200,210,240,0.45);font-size:0.78rem;'
                f'margin-left:6px;">{m["클래스"]}</span></div>',
                unsafe_allow_html=True,
            )
        if rest_m:
            with st.expander(f"+ {len(rest_m)}개 더보기"):
                for m in rest_m:
                    st.markdown(
                        f'<div style="margin-bottom:3px;">'
                        f'<span style="font-size:0.83rem;font-weight:600;">{m["메소드명"]}</span>'
                        f'<span style="color:rgba(200,210,240,0.45);font-size:0.78rem;'
                        f'margin-left:6px;">{m["클래스"]}</span></div>',
                        unsafe_allow_html=True,
                    )

    # ── 카드 3: API 엔드포인트 ───────────────────────
    with st.container(border=True):
        st.markdown(f"**🚀 API 엔드포인트 {len(_DUMMY_ENDPOINTS)}개**")
        first_e, rest_e = _DUMMY_ENDPOINTS[:4], _DUMMY_ENDPOINTS[4:]
        for e in first_e:
            color = _HTTP_COLORS.get(e["메소드"], "#888")
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">'
                f'<span style="background:{color};color:#fff;font-size:0.70rem;'
                f'padding:1px 7px;border-radius:4px;font-weight:700;'
                f'min-width:46px;text-align:center;">{e["메소드"]}</span>'
                f'<span style="font-size:0.82rem;color:#c8d0e8;">{e["경로"]}</span></div>',
                unsafe_allow_html=True,
            )
        if rest_e:
            with st.expander(f"+ {len(rest_e)}개 더보기"):
                for e in rest_e:
                    color = _HTTP_COLORS.get(e["메소드"], "#888")
                    st.markdown(
                        f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">'
                        f'<span style="background:{color};color:#fff;font-size:0.70rem;'
                        f'padding:1px 7px;border-radius:4px;font-weight:700;'
                        f'min-width:46px;text-align:center;">{e["메소드"]}</span>'
                        f'<span style="font-size:0.82rem;color:#c8d0e8;">{e["경로"]}</span></div>',
                        unsafe_allow_html=True,
                    )

    # ── 카드 4: 추천 질문 ────────────────────────────
    with st.container(border=True):
        st.markdown("**💡 추천 질문**")
        for q in _SUGGESTED_QUESTIONS:
            if st.button(q, use_container_width=True, key=f"suggest_{q}"):
                st.session_state.rag_prefill = q
                st.rerun()  # 전체 rerun — fragment 밖이므로 full rerun으로 prefill 전달


def build_chat_html(history: list) -> str:
    messages_html = ""
    for msg in history:
        if msg["role"] == "user":
            messages_html += f"""
            <div class="msg user">
              <div class="bubble user">{msg["content"]}</div>
              <div class="avatar">나</div>
            </div>"""
        else:
            messages_html += f"""
            <div class="msg bot">
              <div class="avatar">AI</div>
              <div class="bubble bot">{msg["content"]}</div>
            </div>"""

    return f"""
    <style>
      body {{ margin:0; background:#fafafa; font-family:sans-serif; }}
      .chat {{ padding:12px; display:flex; flex-direction:column; gap:10px; }}
      .msg {{ display:flex; gap:8px; align-items:flex-start; }}
      .msg.user {{ flex-direction:row-reverse; }}
      .avatar {{ width:28px; height:28px; border-radius:50%; background:#e0e0e0;
                 display:flex; align-items:center; justify-content:center;
                 font-size:11px; font-weight:600; flex-shrink:0; color:#555; }}
      .bubble {{ max-width:80%; padding:9px 13px; border-radius:10px;
                 font-size:13px; line-height:1.6; }}
      .bubble.bot {{ background:#fff; border:1px solid #e0e0e0;
                     border-radius:3px 10px 10px 10px; color:#333; }}
      .bubble.user {{ background:#e8f0fe; border-radius:10px 3px 10px 10px; color:#333; }}
    </style>
    <div class="chat" id="chat">{messages_html}</div>
    <script>
      // 새 메시지가 추가됐을 때만 아래로 스크롤
      // 사용자가 위로 스크롤한 경우엔 강제 이동 안 함
      const chat = document.getElementById('chat');
      const prevCount = sessionStorage.getItem('msgCount') || 0;
      const currCount = {len(history)};
      if (currCount > parseInt(prevCount)) {{
        window.scrollTo(0, document.body.scrollHeight);
        sessionStorage.setItem('msgCount', currCount);
      }}
    </script>
    """


@st.fragment
def _chat_fragment() -> None:
    # prefill 처리 — 추천 질문 클릭 후 full rerun 시 여기서 수신
    prefill = st.session_state.get("rag_prefill", "")
    if prefill:
        st.session_state.rag_prefill = ""
        if st.session_state.get("rag_ready"):
            st.session_state.chat_history.append({"role": "user", "content": prefill})
            # TODO: LangChain + 벡터스토어 연결 — 아래 더미 응답을 실제 RAG 체인으로 교체
            answer = f'"{prefill}" 에 대한 답변입니다. (더미 응답 — RAG 체인 연결 후 교체)'
            st.session_state.chat_history.append({"role": "assistant", "content": answer})
        st.rerun(scope="fragment")

    # 채팅 메시지 — components.html iframe (자체 스크롤)
    components.html(
        build_chat_html(st.session_state.get("chat_history", [])),
        height=480,
        scrolling=True,
    )

    # 입력 폼
    with st.form("rag_form", clear_on_submit=True):
        cols = st.columns([9, 1])
        with cols[0]:
            user_input = st.text_input(
                "",
                placeholder="프로젝트 코드에 대해 질문하세요...",
                label_visibility="collapsed",
                disabled=not st.session_state.get("rag_ready"),
            )
        with cols[1]:
            submitted = st.form_submit_button("↑", use_container_width=True)

    if submitted and user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        # TODO: LangChain + 벡터스토어 연결 — 아래 더미 응답을 실제 RAG 체인으로 교체
        answer = f'"{user_input}" 에 대한 답변입니다. (더미 응답 — RAG 체인 연결 후 교체)'
        st.session_state.chat_history.append({"role": "assistant", "content": answer})
        st.rerun(scope="fragment")

    # 대화 초기화 버튼
    if st.session_state.get("chat_history"):
        if st.button("🗑️ 대화 초기화", use_container_width=False):
            st.session_state.chat_history = []
            st.rerun(scope="fragment")


def render_rag():
    st.markdown(RAG_CSS, unsafe_allow_html=True)

    st.title("💬 RAG 질의응답")

    if not st.session_state.get("selected_project"):
        st.warning("⚠️ 먼저 홈에서 프로젝트를 선택해주세요!")
        st.stop()

    st.markdown(
        f'<span style="background:#1e1e30;color:#7c9ef5;padding:4px 12px;'
        f'border-radius:20px;font-size:0.88rem;font-weight:600;">'
        f'📂 {st.session_state.selected_project}</span>',
        unsafe_allow_html=True,
    )
    st.write("")

    # 인덱스 상태 표시 — columns 밖에 배치
    if st.session_state.get("rag_ready"):
        st.success("✅ 인덱스 빌드 완료 — 질문을 입력하세요.")
    else:
        col_warn, col_btn = st.columns([3, 1])
        with col_warn:
            st.warning("⚠️ 인덱스가 빌드되지 않았습니다.")
        with col_btn:
            if st.button("🔨 빌드", use_container_width=True):
                # TODO: LangChain + 벡터스토어 연결 — 실제 임베딩 및 인덱스 빌드로 교체
                st.session_state.rag_ready = True
                st.rerun()

    col_chat, col_info = st.columns([3, 1.2])

    with col_chat:
        _chat_fragment()

    with col_info:
        with st.container(height=590):
            _render_info_panel()
