"""
Java Refactor Assistant
"""
import streamlit as st

from pages_.home import render_home
from pages_.analysis import render_analysis
from pages_.refactor import render_refactor
from pages_.dependency_graph import render_dependency_graph
from pages_.simulator import render_simulator

st.set_page_config(
    page_title="Java Refactor Assistant",
    page_icon="☕",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
/* ── 사이드바 배경 ─────────────────────────────── */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] > div:first-child {
    background-color: #13131f !important;
}

/* ── 버튼 기본 (비활성) + focus/active/focus-visible 일괄 처리 ── */
.stSidebar .stButton > button,
.stSidebar .stButton > button:focus,
.stSidebar .stButton > button:active,
.stSidebar .stButton > button:focus-visible {
    width: 100%;
    background: transparent !important;
    color: #ffffff !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
    text-align: left;
    padding: 11px 16px;
    border-radius: 8px;
    font-size: 0.92rem;
    letter-spacing: 0.01em;
    margin-bottom: 3px;
    outline: none !important;
    box-shadow: none !important;
    transition: background 0.15s;
}

/* ── hover ─────────────────────────────────────── */
.stSidebar .stButton > button:hover {
    background: rgba(255,255,255,0.1) !important;
    color: #ffffff !important;
    border-color: rgba(255,255,255,0.15) !important;
}

/* ── 활성(primary) 버튼 ─────────────────────────── */
.stSidebar .stButton > button[kind="primary"],
.stSidebar .stButton > button[kind="primary"]:focus,
.stSidebar .stButton > button[kind="primary"]:active,
.stSidebar .stButton > button[kind="primary"]:focus-visible {
    background: rgba(255,255,255,0.18) !important;
    color: #ffffff !important;
    font-weight: 600 !important;
    border-color: rgba(255,255,255,0.15) !important;
    outline: none !important;
    box-shadow: none !important;
}

.stSidebar .stButton > button[kind="primary"]:hover {
    background: rgba(255,255,255,0.25) !important;
}
</style>
""", unsafe_allow_html=True)


# ── 메뉴 정의 ──────────────────────────────────────
_MENU_ITEMS = [
    "🏠 홈",
    "🔍 AST 분석",
    "🛠️ 리팩토링 제안",
    "🕸️ 의존성 그래프",
    "🚀 API 시뮬레이터",
]

# ── 세션 상태 초기화 ────────────────────────────────
if "selected_project" not in st.session_state:
    st.session_state.selected_project = None
if "menu" not in st.session_state:
    st.session_state.menu = "🏠 홈"
if "sim_responses" not in st.session_state:
    st.session_state.sim_responses = {}

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
    "🏠 홈":           render_home,
    "🔍 AST 분석":     render_analysis,
    "🛠️ 리팩토링 제안": render_refactor,
    "🕸️ 의존성 그래프": render_dependency_graph,
    "🚀 API 시뮬레이터": render_simulator,
}

PAGE_RENDERERS[st.session_state.menu]()
