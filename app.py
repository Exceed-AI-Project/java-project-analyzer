"""
Java Refactor Assistant
"""
import streamlit as st

from ui.home import render_home
from ui.analysis import render_analysis
from ui.refactor import render_refactor
from ui.rag import render_rag
from ui.simulator import render_simulator
from ui.css.sidebar import SIDEBAR_CSS

st.set_page_config(
    page_title="Java Refactor Assistant",
    page_icon="☕",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(SIDEBAR_CSS, unsafe_allow_html=True)


# ── 메뉴 정의 ──────────────────────────────────────
_MENU_ITEMS = [
    "🏠 홈",
    "🔍 AST 분석",
    "🛠️ 리팩토링 제안",
    "💬 RAG 질의응답",
    "🚀 API 시뮬레이터",
]

# ── 세션 상태 초기화 ────────────────────────────────
if "selected_project" not in st.session_state:
    st.session_state.selected_project = None
if "menu" not in st.session_state:
    st.session_state.menu = "🏠 홈"
if "sim_responses" not in st.session_state:
    st.session_state.sim_responses = {}
if "rag_ready" not in st.session_state:
    st.session_state.rag_ready = False
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "rag_prefill" not in st.session_state:
    st.session_state.rag_prefill = ""

if st.session_state.menu not in _MENU_ITEMS:
    st.session_state.menu = "🏠 홈"

# ── 사이드바 ────────────────────────────────────────
with st.sidebar:
    st.title("☕ Java Refactor Assistant")
    st.caption("AST 분석 · 리팩토링 · API 시뮬레이션")
    st.divider()

    for _item in _MENU_ITEMS:
        _active = st.session_state.menu == _item
        if st.button(
            _item,
            key=f"nav_{_item}",
            use_container_width=True,
            type="primary" if _active else "secondary",
        ):
            st.session_state.menu = _item
            st.rerun()

    st.divider()
    st.caption("선택된 프로젝트")
    if st.session_state.selected_project:
        st.success(f"📂 {st.session_state.selected_project}")
        if st.button("선택 해제", use_container_width=True):
            st.session_state.selected_project = None
            st.rerun()
    else:
        st.info("프로젝트를 선택해주세요")

# ── 라우팅 ──────────────────────────────────────────
PAGE_RENDERERS = {
    "🏠 홈":            render_home,
    "🔍 AST 분석":      render_analysis,
    "🛠️ 리팩토링 제안":  render_refactor,
    "💬 RAG 질의응답":   render_rag,
    "🚀 API 시뮬레이터": render_simulator,
}

PAGE_RENDERERS[st.session_state.menu]()
