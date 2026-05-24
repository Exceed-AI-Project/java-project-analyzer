"""
Java Refactor Assistant
파이썬 기반 Java 프로젝트 AST 분석 및 리팩토링, API 시뮬레이션 도구
"""
import streamlit as st
from ui import analysis, home, refactor, simulator, rag
from ui.styles.sidebar import SIDEBAR_CSS


# ============================================================
# 페이지 기본 설정
# ============================================================
st.set_page_config(
    page_title="Java Refactor Assistant", 
    page_icon="☕",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(SIDEBAR_CSS, unsafe_allow_html=True) # 마크 다운 형식으로 출력하는 함수를 통해, css 적용(unsafe_allow_html=True 옵션을 통해, HTEML 태그를 escape))

# 메뉴 초기화
_MENU_ITEMS = [
    "🏠 홈",
    "🔍 AST 분석",
    "🛠️ 리팩토링 제안",
    "🚀 API 시뮬레이터",
]


# ============================================================
# 세션 상태 초기화
# ============================================================
if "selected_project" not in st.session_state:
    st.session_state.selected_project = None
if "menu" not in st.session_state:
    st.session_state.menu = "🏠 홈"


# ============================================================
# 사이드바
# ============================================================
with st.sidebar:
    st.title("☕ Java Refactor Assistant")
    st.caption("AST 분석 · 리팩토링 · API 시뮬레이션")
    st.divider()

    # 선택된 사이드 메뉴 강조
    for _item in _MENU_ITEMS:
        _active = st.session_state.menu == _item
        if st.button(
            _item,
            key=f"nav_{_item}",
            width="stretch",
            type="primary" if _active else "secondary"
        ):
            st.session_state.menu = _item
            st.rerun()
    
    st.divider() # 선 추가

    st.caption("선택된 프로젝트")
    if st.session_state.selected_project:
        st.success(f"📂 {st.session_state.selected_project}")
        if st.button("선택 해제", width="stretch"):
            st.session_state.selected_project = None
            st.rerun()
    else:
        st.info("프로젝트를 선택해주세요")


# ============================================================
# 라우팅
# ============================================================
PAGE_RENDERERS = {
    "🏠 홈": home.render_home,
    "🔍 AST 분석": analysis.render_analysis,
    "🛠️ 리팩토링 제안": refactor.render_refactor,
    "🚀 API 시뮬레이터": simulator.render_simulator,
}

PAGE_RENDERERS[st.session_state.menu]()