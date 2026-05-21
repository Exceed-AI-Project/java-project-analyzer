"""
ui/refactor.py — 리팩토링 제안 페이지

흐름:
    1. 프로젝트 전체 품질 요약 표시
    2. 문제 클래스 선택
    3. 선택한 클래스 상세 품질 지표
    4. RAG 기반 AI 리팩토링 제안
"""
import streamlit as st

from services.refactor_service import (
    analyze_class_quality,
    get_project_summary,
    ClassQuality,
)
from services.rag_service import (
    build_vector_db,
    get_refactor_suggestion,
    is_db_built,
)


# ============================================================
# 전체 프로젝트 품질 요약
# ============================================================
def _render_project_summary(project_name: str) -> str | None:
    """전체 품질 요약 표 + 클래스 선택, 선택한 클래스명 반환"""
    st.subheader("📋 전체 프로젝트 품질 요약")

    with st.spinner("전체 클래스 분석 중..."):
        summary = get_project_summary(project_name)

    if not summary:
        st.warning("AST 분석 결과가 없습니다. 먼저 AST 분석을 실행해주세요.")
        return None

    # 문제 있는 클래스 / 정상 클래스 분리
    problem_classes = [q for q in summary if not q.is_healthy]
    healthy_classes = [q for q in summary if q.is_healthy]

    # 요약 메트릭
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("전체 클래스", len(summary))
    with col2:
        st.metric("⚠️ 문제 클래스", len(problem_classes), delta_color="inverse")
    with col3:
        st.metric("✅ 정상 클래스", len(healthy_classes))

    st.divider()

    # 문제 클래스 표
    if problem_classes:
        st.markdown("#### ⚠️ 리팩토링 필요 클래스")
        rows = []
        for q in problem_classes:
            issues = []
            if q.has_too_many_methods:
                issues.append(f"메소드 {q.method_count}개")
            if q.has_too_many_dependencies:
                issues.append(f"의존성 {q.dependency_count}개")
            if q.has_method_issues:
                issues.append(f"파라미터 초과 {len(q.method_issues)}개")
            rows.append({
                "클래스명": q.class_name,
                "계층": q.stereotype,
                "메소드 수": q.method_count,
                "의존 클래스 수": q.dependency_count,
                "파라미터 이슈": len(q.method_issues),
                "문제 항목": ", ".join(issues),
            })
        st.dataframe(rows, hide_index=True, use_container_width=True)
    else:
        st.success("✅ 모든 클래스가 정상입니다!")

    st.divider()

    # 클래스 선택
    st.markdown("#### 🔎 상세 분석할 클래스 선택")

    # 문제 클래스를 위로
    all_names = [q.class_name for q in problem_classes] + [q.class_name for q in healthy_classes]
    selected = st.selectbox(
        "클래스 선택 (⚠️ 표시 = 문제 있음)",
        options=all_names,
        format_func=lambda x: f"⚠️ {x}" if x in [q.class_name for q in problem_classes] else f"✅ {x}",
        key="refactor_class",
    )
    return selected


# ============================================================
# 클래스 상세 품질 지표
# ============================================================
def _render_quality_metrics(project_name: str, class_name: str) -> None:
    quality = analyze_class_quality(project_name, class_name)
    if quality is None:
        st.error("클래스 분석 결과를 불러올 수 없습니다.")
        return

    st.subheader(f"📊 `{class_name}` 품질 지표")

    if quality.is_healthy:
        st.success("✅ 이 클래스는 전반적으로 양호합니다!")
    else:
        st.warning("⚠️ 리팩토링이 필요한 부분이 있습니다.")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            label="메소드 수",
            value=quality.method_count,
            delta="권장 7개 이하" if quality.has_too_many_methods else "정상",
            delta_color="inverse" if quality.has_too_many_methods else "normal",
        )
    with col2:
        st.metric(
            label="의존 클래스 수",
            value=quality.dependency_count,
            delta="권장 5개 이하" if quality.has_too_many_dependencies else "정상",
            delta_color="inverse" if quality.has_too_many_dependencies else "normal",
        )
    with col3:
        st.metric(
            label="파라미터 이슈",
            value=f"{len(quality.method_issues)}개 메소드",
            delta="파라미터 초과" if quality.has_method_issues else "정상",
            delta_color="inverse" if quality.has_method_issues else "normal",
        )

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

    # 1. 전체 품질 요약 + 클래스 선택
    selected_class = _render_project_summary(project_name)
    if not selected_class:
        return

    st.divider()

    # 2. 선택한 클래스 상세 품질 지표
    _render_quality_metrics(project_name, selected_class)

    st.divider()

    # 3. AI 리팩토링 제안
    _render_rag_suggestion(project_name, selected_class)