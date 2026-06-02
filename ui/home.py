import streamlit as st
from services.project_manager import scan_projects
from services.project_scanner import clone_project
from services.llm import validate_key
from ui import project_card


# ============================================================
# 홈 페이지
# ============================================================
def render_home():
    st.title("Java Refactor Assistant")
    st.write("Java 프로젝트를 분석하고, 리팩토링 제안을 받고, API를 시뮬레이션하세요.")

    st.divider()

    # ─────── OpenAI API 키 (LLM 기능 게이트) ───────
    with st.expander("🔑 OpenAI API 키 설정", expanded=not st.session_state.get("llm_ok")):
        st.caption("키를 넣고 '확인'을 누르면 테스트 요청을 보내 검증합니다. "
                   "검증되면 LLM 기반 기능(페이로드 자동생성·질의 리팩토링)이 열립니다.")
        col_key, col_btn = st.columns([4, 1])
        with col_key:
            key_in = st.text_input(
                "API Key", type="password",
                value=st.session_state.get("openai_key", ""),
                placeholder="sk-...", label_visibility="collapsed",
            )
        with col_btn:
            check = st.button("확인", use_container_width=True, disabled=not key_in)

        if check:
            with st.spinner("API 키로 테스트 요청 전송 중..."):
                ok, msg = validate_key(key_in.strip())
            st.session_state.llm_ok = ok
            st.session_state.openai_key = key_in.strip() if ok else ""
            (st.success if ok else st.error)(msg)

        if st.session_state.get("llm_ok"):
            st.success("LLM 기능 활성화됨 ✓")
        else:
            st.info("키 미검증 — 정적 분석/시뮬레이션은 그대로 사용 가능 (LLM 기능만 잠김)")

    # ─────── 새 프로젝트 추가 ───────
    with st.expander("➕ 새 프로젝트 추가 (Git Clone)", expanded=False):
        git_url = st.text_input(
            "Git Repository URL",
            placeholder="https://github.com/username/java-project.git",
            help="공개 저장소 URL. Private 저장소는 추후 지원 예정",
        )
        if st.button("Clone 시작", type="primary", disabled=not git_url):
            with st.spinner(f"`{git_url}` 에서 clone 중..."):
                success, msg, info = clone_project(git_url.strip())
            if success:
                st.success(msg)
                st.session_state.selected_project = info.name
                st.rerun()
            else:
                st.error(msg)

    st.divider()

    # ─────── 프로젝트 목록 ───────
    st.subheader("📋 내 프로젝트")
    projects = scan_projects()
    if not projects:
        st.info("아직 등록된 프로젝트가 없어요.  \n"
                "위의 **➕ 새 프로젝트 추가** 에서 Git URL로 추가해보세요!")
    else:
        analyzed_count = sum(1 for p in projects if p.analyzed)
        c = st.columns(3)
        c[0].metric("전체 프로젝트", len(projects))
        c[1].metric("분석 완료", analyzed_count)
        c[2].metric("미분석", len(projects) - analyzed_count)
        st.write("")
        for project in projects:
            project_card.render_project_card(project)
