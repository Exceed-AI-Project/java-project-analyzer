"""
ui/refactor.py — 리팩토링 제안 페이지

흐름:
    1. 선택된 프로젝트 확인
    2. 클래스 선택
    3. 규칙 기반 품질 지표 표시
    4. RAG 기반 AI 리팩토링 제안
"""
import streamlit as st

from services.refactor_service import (
    analyze_class_quality,
    get_class_names,
    get_project_summary,
)
from services.rag_service import (
    build_vector_db,
    get_refactor_suggestion,
    is_db_built,
)


# ============================================================
# 품질 지표 렌더링
# ============================================================
def _render_quality_metrics(project_name: str, class_name: str) -> None:
    quality = analyze_class_quality(project_name, class_name)
    if quality is None:
        st.error("클래스 분석 결과를 불러올 수 없습니다.")
        return

    st.subheader("📊 품질 지표")

    # 전체 상태
    if quality.is_healthy:
        st.success("✅ 이 클래스는 전반적으로 양호합니다!")
    else:
        st.warning("⚠️ 리팩토링이 필요한 부분이 있습니다.")

    col1, col2, col3 = st.columns(3)

    # 메소드 수
    with col1:
        method_color = "inverse" if quality.has_too_many_methods else "normal"
        st.metric(
            label="메소드 수",
            value=quality.method_count,
            delta="권장 7개 이하" if quality.has_too_many_methods else "정상",
            delta_color=method_color,
        )

    # 의존성 수
    with col2:
        dep_color = "inverse" if quality.has_too_many_dependencies else "normal"
        st.metric(
            label="의존 클래스 수",
            value=quality.dependency_count,
            delta="권장 5개 이하" if quality.has_too_many_dependencies else "정상",
            delta_color=dep_color,
        )

    # 파라미터 이슈 수
    with col3:
        issue_color = "inverse" if quality.has_method_issues else "normal"
        st.metric(
            label="파라미터 이슈",
            value=f"{len(quality.method_issues)}개 메소드",
            delta="파라미터 초과" if quality.has_method_issues else "정상",
            delta_color=issue_color,
        )

    # 상세 경고
    if quality.has_too_many_methods:
        st.error(
            f"🚨 **God Class 위험**: 메소드가 {quality.method_count}개로 너무 많아요. "
            "책임을 분리해 여러 클래스로 나누는 것을 권장합니다."
        )

    if quality.has_too_many_dependencies:
        st.error(
            f"🚨 **높은 결합도**: 의존하는 클래스가 {quality.dependency_count}개로 너무 많아요. "
            "의존성을 줄여 결합도를 낮추는 것을 권장합니다."
        )

    if quality.has_method_issues:
        st.warning("⚠️ **파라미터 초과 메소드**")
        for issue in quality.method_issues:
            st.markdown(f"- `{issue.method_name}`: {issue.message}")


# ============================================================
# RAG 제안 렌더링
# ============================================================
def _render_rag_suggestion(project_name: str, class_name: str) -> None:
    st.subheader("💡 AI 리팩토링 제안")

    # 벡터 DB 구축 여부 확인
    if not is_db_built(project_name):
        st.info("🔧 AI 제안을 받으려면 먼저 벡터 DB를 구축해야 합니다.")
        if st.button("🗄️ 벡터 DB 구축", type="primary"):
            with st.spinner("임베딩 중... 잠시 기다려주세요"):
                try:
                    count = build_vector_db(project_name)
                    st.success(f"✅ 벡터 DB 구축 완료! ({count}개 클래스 임베딩)")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ 벡터 DB 구축 실패: {e}")
        return

    # 제안 생성
    col_btn, col_rebuild = st.columns([3, 1])
    with col_btn:
        generate = st.button("🤖 AI 리팩토링 제안 받기", type="primary")
    with col_rebuild:
        if st.button("🔄 DB 재구축"):
            with st.spinner("임베딩 중..."):
                try:
                    count = build_vector_db(project_name)
                    st.success(f"✅ 재구축 완료! ({count}개)")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ 실패: {e}")

    if generate:
        with st.spinner(f"🤖 {class_name} 분석 중..."):
            try:
                suggestion = get_refactor_suggestion(project_name, class_name)
                if suggestion:
                    st.markdown(suggestion)
                else:
                    st.warning("제안을 생성하지 못했습니다.")
            except Exception as e:
                st.error(f"❌ AI 제안 생성 실패: {e}")
    else:
        st.caption("버튼을 눌러 AI 리팩토링 제안을 받아보세요.")


# ============================================================
# 메인 렌더러
# ============================================================
def render_refactor():
    st.title("🛠️ 리팩토링 제안")

    # 프로젝트 선택 확인
    if not st.session_state.get("selected_project"):
        st.warning("⚠️ 먼저 홈에서 프로젝트를 선택해주세요!")
        return

    project_name = st.session_state.selected_project
    st.markdown(
        f'<span style="background:#1e1e30;color:#7c9ef5;padding:4px 12px;'
        f'border-radius:20px;font-size:0.88rem;font-weight:600;">'
        f'📂 {project_name}</span>',
        unsafe_allow_html=True,
    )
    st.write("")

    # 클래스 선택
    class_names = get_class_names(project_name)
    if not class_names:
        st.warning("AST 분석 결과가 없습니다. 먼저 AST 분석을 실행해주세요.")
        return

    selected_class = st.selectbox(
        "🔎 분석할 클래스 선택",
        options=class_names,
        key="refactor_class",
    )

    st.divider()

    # 품질 지표
    _render_quality_metrics(project_name, selected_class)

    st.divider()

    # AI 리팩토링 제안
    _render_rag_suggestion(project_name, selected_class)