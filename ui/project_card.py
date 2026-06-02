import streamlit as st
from models.project import ProjectInfo
from services.project_manager import delete_project
from services.verify import compile_project


# ============================================================
# 프로젝트 카드 렌더링
# ============================================================
def render_project_card(project: ProjectInfo) -> None:
    """프로젝트 카드 한 개를 렌더링"""
    with st.container(border=True):
        col_info, col_action = st.columns([4, 1])

        with col_info:
            status_badge = "✅ 분석됨" if project.analyzed else "⏳ 미분석"
            st.markdown(f"### 📂 {project.name}  `{status_badge}`")

            meta_cols = st.columns(3)
            meta_cols[0].caption(f"**빌드** · {project.build_info.summary}")
            meta_cols[1].caption(f"**Java 파일** · {project.file_count}개")
            meta_cols[2].caption(f"**Clone** · {project.cloned_at[:10]}")

            if project.git_url:
                st.caption(f"🔗 {project.git_url}")

            if project.build_info.is_multi_module:
                with st.expander(f"📦 모듈 {len(project.build_info.modules)}개 보기"):
                    for module in project.build_info.modules:
                        path_label = "🏠 (root)" if module.relative_path == "." \
                                     else f"📁 {module.relative_path}"
                        st.caption(
                            f"{path_label} · {module.build_tool} · "
                            f"`{module.build_file}` · {module.java_file_count}개 파일"
                        )

        with col_action:
            if st.button("선택 →", key=f"select_{project.name}",
                         use_container_width=True, type="primary"):
                st.session_state.selected_project = project.name
                st.session_state.menu = "🔍 AST 분석"
                st.rerun()

            if st.button("🔨 빌드", key=f"build_{project.name}",
                         use_container_width=True):
                with st.spinner(f"`{project.name}` 컴파일 중... (첫 빌드는 의존성 다운로드로 오래 걸릴 수 있어요)"):
                    ok, log = compile_project(project.path)
                st.session_state[f"build_result_{project.name}"] = (ok, log)

            if st.button("🗑️ 삭제", key=f"delete_{project.name}",
                         use_container_width=True):
                success, msg = delete_project(project.name)
                if success:
                    st.toast(msg, icon="✅")
                    if st.session_state.selected_project == project.name:
                        st.session_state.selected_project = None
                    st.session_state.pop(f"build_result_{project.name}", None)
                    st.rerun()
                else:
                    st.error(msg)

        # 빌드 결과 표시 (카드 하단)
        result = st.session_state.get(f"build_result_{project.name}")
        if result is not None:
            ok, log = result
            if ok is True:
                st.success("✅ 빌드 성공 — 컴파일 통과")
            elif ok is False:
                st.error("❌ 빌드 실패")
            else:
                st.info("ℹ️ 빌드 도구 없음 — 컴파일 검증 생략")
            with st.expander("빌드 로그 보기"):
                st.code(log)
