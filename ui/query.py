import streamlit as st
from services.ast_analyzer import build_model
from services.query_refactor import propose_change, apply_proposal
from services.project_manager import scan_projects
from pathlib import Path


def _project_path():
    name = st.session_state.selected_project
    for p in scan_projects():
        if p.name == name:
            return p.path
    return None


def render_query():
    st.title("💬 질의 기반 리팩토링")
    if not st.session_state.selected_project:
        st.warning("⚠️ 먼저 홈에서 프로젝트를 선택해주세요!")
        return
    st.success(f"선택된 프로젝트: **{st.session_state.selected_project}**")

    if not st.session_state.get("llm_ok"):
        st.error("🔒 LLM 비활성 — 홈에서 API 키를 검증해주세요.")
        return

    root = Path(_project_path())
    java_files = sorted(str(p.relative_to(root)) for p in root.rglob("*.java")
                        if ".git" not in p.parts)
    rel = st.selectbox("대상 파일", java_files)
    query = st.text_area("어떻게 바꿀까요?",
                         placeholder="예: 이 컨트롤러의 @Transactional 을 서비스 레이어로 옮겨줘", height=100)

    if st.button("리팩토링 제안 생성", type="primary", disabled=not query):
        model = st.session_state.get("ast_model") or build_model(str(root))
        st.session_state.ast_model = model
        with st.spinner("LLM 이 변경안(diff) 생성 중..."):
            prop = propose_change(query, str(root / rel), model, st.session_state["openai_key"])
        st.session_state.refactor_proposal = prop

    prop = st.session_state.get("refactor_proposal")
    if prop and prop.ok:
        if not prop.diff:
            st.info(prop.note or "변경 없음")
            return
        st.subheader("제안된 변경 (diff)")
        st.code(prop.diff, language="diff")
        st.warning("자동 적용 안 함. 검토 후 아래 버튼으로 명시적 적용.")
        if st.button("이 변경 적용", type="secondary"):
            ok, msg = apply_proposal(prop)
            (st.success if ok else st.error)(msg)
    elif prop and not prop.ok:
        st.error(prop.note)
