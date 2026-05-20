import streamlit as st

def render_simulator():
    st.title("🚀 API 시뮬레이터")
    if not st.session_state.selected_project:
        st.warning("⚠️ 먼저 홈에서 프로젝트를 선택해주세요!")
        return
    st.success(f"선택된 프로젝트: **{st.session_state.selected_project}**")
    st.info("API 시뮬레이션 기능은 다음 단계에서 구현 예정입니다.")