import streamlit as st
from services.project_manager import scan_projects
from services.project_scanner import clone_project
from ui import project_card


# ============================================================
# 홈 페이지
# ============================================================
def render_home():
    st.title("Java Refactor Assistant")
    st.write("Java 프로젝트를 분석하고, 리팩토링 제안을 받고, API를 시뮬레이션하세요.")

    st.divider()

    # ─────── 새 프로젝트 추가 ───────
    with st.expander("➕ 새 프로젝트 추가 (Git Clone)", expanded=False):
        git_url = st.text_input(
            "Git Repository URL",
            placeholder="https://github.com/username/java-project.git",
            help="공개 저장소 URL을 입력하세요. Private 저장소는 추후 지원 예정",
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
        st.info(
            "아직 등록된 프로젝트가 없어요.  \n"
            "위의 **➕ 새 프로젝트 추가** 에서 Git URL로 추가해보세요!"
        )
    else:
        # 통계 표시
        analyzed_count = sum(1 for p in projects if p.analyzed)
        stat_cols = st.columns(3)
        stat_cols[0].metric("전체 프로젝트", len(projects))
        stat_cols[1].metric("분석 완료", analyzed_count)
        stat_cols[2].metric("미분석", len(projects) - analyzed_count)

        st.write("")  # 여백

        for project in projects:
            project_card.render_project_card(project)