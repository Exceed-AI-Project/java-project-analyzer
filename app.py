"""
Java Refactor Assistant
파이썬 기반 Java 프로젝트 AST 분석 및 리팩토링, API 시뮬레이션 도구
"""
import streamlit as st

from utils.project_manager import (
    scan_projects,
    clone_project,
    delete_project,
    ProjectInfo,
)


# ============================================================
# 페이지 기본 설정
# ============================================================
st.set_page_config(
    page_title="Java Refactor Assistant",
    page_icon="☕",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# 세션 상태 초기화
# ============================================================
if "selected_project" not in st.session_state:
    st.session_state.selected_project = None  # 선택된 프로젝트 이름
if "menu" not in st.session_state:
    st.session_state.menu = "🏠 홈"


# ============================================================
# 사이드바
# ============================================================
with st.sidebar:
    st.title("☕ Java Refactor Assistant")
    st.caption("AST 분석 · 리팩토링 · API 시뮬레이션")

    st.divider()

    st.session_state.menu = st.radio(
        "메뉴",
        options=[
            "🏠 홈",
            "🔍 AST 분석",
            "🛠️ 리팩토링 제안",
            "🚀 API 시뮬레이터",
        ],
        label_visibility="collapsed",
        key="menu_radio",
        index=["🏠 홈", "🔍 AST 분석", "🛠️ 리팩토링 제안", "🚀 API 시뮬레이터"].index(
            st.session_state.menu
        ),
    )

    st.divider()

    st.caption("선택된 프로젝트")
    if st.session_state.selected_project:
        st.success(f"📂 {st.session_state.selected_project}")
        if st.button("선택 해제", use_container_width=True):
            st.session_state.selected_project = None
            st.rerun()
    else:
        st.info("프로젝트를 선택해주세요")


# ============================================================
# 프로젝트 카드 렌더링
# ============================================================
def render_project_card(project: ProjectInfo) -> None:
    """프로젝트 카드 한 개를 렌더링"""
    with st.container(border=True):
        col_info, col_action = st.columns([4, 1])

        with col_info:
            # 제목 + 분석 상태 뱃지
            status_badge = "✅ 분석됨" if project.analyzed else "⏳ 미분석"
            st.markdown(f"### 📂 {project.name}  `{status_badge}`")

            # 메타 정보
            meta_cols = st.columns(3)
            meta_cols[0].caption(f"**빌드** · {project.build_tool}")
            meta_cols[1].caption(f"**Java 파일** · {project.file_count}개")
            meta_cols[2].caption(f"**Clone** · {project.cloned_at[:10]}")

            if project.git_url:
                st.caption(f"🔗 {project.git_url}")

        with col_action:
            if st.button(
                "선택 →",
                key=f"select_{project.name}",
                use_container_width=True,
                type="primary",
            ):
                st.session_state.selected_project = project.name
                st.session_state.menu = "🔍 AST 분석"
                st.rerun()

            if st.button(
                "🗑️ 삭제",
                key=f"delete_{project.name}",
                use_container_width=True,
            ):
                success, msg = delete_project(project.name)
                if success:
                    st.toast(msg, icon="✅")
                    if st.session_state.selected_project == project.name:
                        st.session_state.selected_project = None
                    st.rerun()
                else:
                    st.error(msg)


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
            render_project_card(project)


# ============================================================
# 다른 페이지들 (placeholder)
# ============================================================
def render_analysis():
    st.title("🔍 AST 분석")
    if not st.session_state.selected_project:
        st.warning("⚠️ 먼저 홈에서 프로젝트를 선택해주세요!")
        return
    st.success(f"선택된 프로젝트: **{st.session_state.selected_project}**")
    st.info("AST 분석 기능은 다음 단계에서 구현 예정입니다.")


def render_refactor():
    st.title("🛠️ 리팩토링 제안")
    if not st.session_state.selected_project:
        st.warning("⚠️ 먼저 홈에서 프로젝트를 선택해주세요!")
        return
    st.success(f"선택된 프로젝트: **{st.session_state.selected_project}**")
    st.info("RAG 기반 리팩토링 제안 기능은 다음 단계에서 구현 예정입니다.")


def render_simulator():
    st.title("🚀 API 시뮬레이터")
    if not st.session_state.selected_project:
        st.warning("⚠️ 먼저 홈에서 프로젝트를 선택해주세요!")
        return
    st.success(f"선택된 프로젝트: **{st.session_state.selected_project}**")
    st.info("API 시뮬레이션 기능은 다음 단계에서 구현 예정입니다.")


# ============================================================
# 라우팅
# ============================================================
PAGE_RENDERERS = {
    "🏠 홈": render_home,
    "🔍 AST 분석": render_analysis,
    "🛠️ 리팩토링 제안": render_refactor,
    "🚀 API 시뮬레이터": render_simulator,
}

PAGE_RENDERERS[st.session_state.menu]()