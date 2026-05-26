"""
ui/refactor.py — 리팩토링 제안 페이지

흐름:
    1. 프로젝트 전체 품질 요약 표시
    2. 문제 클래스 선택
    3. 선택한 클래스 상세 품질 지표 (4가지 관점, 실제 데이터 포함)
    4. RAG 기반 AI 리팩토링 제안
"""
import streamlit as st

from services.refactor_service import (
    analyze_class_quality,
    get_project_summary,
    ClassQuality,
    MAX_DEPENDENCIES,
)



# ============================================================
# 전체 프로젝트 품질 요약
# ============================================================
def _render_project_summary(project_name: str) -> str | None:
    st.subheader("📋 전체 프로젝트 품질 요약")

    with st.spinner("전체 클래스 분석 중..."):
        summary = get_project_summary(project_name)

    if not summary:
        st.warning("AST 분석 결과가 없습니다. 먼저 AST 분석을 실행해주세요.")
        return None

    problem_classes = [q for q in summary if not q.is_healthy]
    healthy_classes = [q for q in summary if q.is_healthy]

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("전체 클래스", len(summary))
    with col2:
        st.metric("⚠️ 문제 클래스", len(problem_classes), delta_color="inverse")
    with col3:
        st.metric("✅ 정상 클래스", len(healthy_classes))

    st.divider()

    if problem_classes:
        st.markdown("#### ⚠️ 리팩토링 필요 클래스")
        rows = []
        for q in problem_classes:
            issues = []
            if q.has_too_many_methods:
                issues.append(f"God Class ({q.method_count}개)")
            if q.is_tiny_class:
                issues.append(f"Tiny Class ({q.method_count}개)")
            if q.has_too_many_dependencies:
                issues.append(f"의존성 {q.dependency_count}개")
            if q.has_method_issues:
                issues.append(f"파라미터 초과 {len(q.method_issues)}개")
            if q.has_unclear_names:
                issues.append(f"모호한 이름 {len(q.unclear_names)}개")
            if q.has_dead_methods:
                issues.append(f"데드메소드 {len(q.dead_methods)}개")
            rows.append({
                "클래스명": q.class_name,
                "계층": q.stereotype,
                "메소드 수": q.method_count,
                "의존 클래스": q.dependency_count,
                "문제 항목": ", ".join(issues),
            })
        st.dataframe(rows, hide_index=True, use_container_width=True)
    else:
        st.success("✅ 모든 클래스가 정상입니다!")

    st.divider()

    st.markdown("#### 🔎 상세 분석할 클래스 선택")
    problem_names = [q.class_name for q in problem_classes]
    healthy_names = [q.class_name for q in healthy_classes]
    all_names     = problem_names + healthy_names

    selected = st.selectbox(
        "클래스 선택 (⚠️ = 문제 있음)",
        options=all_names,
        format_func=lambda x: f"⚠️ {x}" if x in problem_names else f"✅ {x}",
        key="refactor_class",
    )
    return selected


# ============================================================
# 의존성 그래프 (graphviz)
# ============================================================
def _render_dependency_graph(class_name: str, dep_classes: list[str], callers: list[str]) -> None:
    """선택 클래스 중심의 의존성 방향 그래프"""
    lines = ["digraph G {", '  rankdir=LR;', '  node [shape=box, style=filled];']

    # 중심 노드
    lines.append(f'  "{class_name}" [fillcolor="#4a90d9", fontcolor=white, penwidth=2];')

    # 이 클래스가 의존하는 클래스들 (→ 방향)
    for dep in dep_classes:
        lines.append(f'  "{dep}" [fillcolor="#f0f0f0"];')
        lines.append(f'  "{class_name}" -> "{dep}" [color="#e05c5c", label="의존"];')

    # 이 클래스를 호출하는 클래스들 (← 방향)
    for caller in callers:
        if caller not in dep_classes:  # 중복 방지
            lines.append(f'  "{caller}" [fillcolor="#d4edda"];')
        lines.append(f'  "{caller}" -> "{class_name}" [color="#28a745", label="호출"];')

    lines.append("}")
    dot_src = "\n".join(lines)
    st.graphviz_chart(dot_src)


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
        st.warning("⚠️ 아래 항목에서 리팩토링이 필요합니다.")

    # ── 1. 코드 가독성 ────────────────────────────────────────
    st.markdown("##### 🔍 코드 가독성")
    if quality.has_unclear_names:
        st.error(f"🚨 모호한 메소드명 {len(quality.unclear_names)}개 발견")
        for issue in quality.unclear_names:
            with st.expander(f"`{issue.method_name}` — 이름이 너무 짧아요"):
                st.markdown(f"**문제**: {issue.message}")
                st.markdown(f"**개선 힌트**: {issue.suggestion}")
                st.code(
                    f"// 변경 전\nvoid {issue.method_name}() {{ ... }}\n\n"
                    f"// 변경 후 예시\nvoid process{class_name}() {{ ... }}",
                    language="java",
                )
    else:
        st.success("✅ 메소드명이 명확합니다.")

    st.divider()

    # ── 2. 데드코드 ───────────────────────────────────────────
    st.markdown("##### 🗑️ 데드코드")
    if quality.has_dead_methods:
        st.warning(f"⚠️ **호출되지 않는 메소드** {len(quality.dead_methods)}개 발견")
        st.caption("getter/setter/main은 제외됩니다. 외부에서 호출되는 경우는 예외일 수 있어요.")
        for dm in quality.dead_methods:
            params_str = ", ".join(dm.parameters) if dm.parameters else ""
            with st.expander(f"`{dm.method_name}` — 호출 없음"):
                st.code(
                    f"// 아무도 호출하지 않는 메소드\n{dm.return_type} {dm.method_name}({params_str}) {{ ... }}",
                    language="java",
                )
                st.markdown("**개선 방법**: 실제로 사용되지 않는다면 삭제를 고려해보세요.")
    else:
        st.success("✅ 호출되지 않는 메소드가 없습니다.")
        if quality.callers:
            with st.expander(f"📋 이 클래스를 호출하는 클래스 ({len(quality.callers)}개)"):
                for caller in quality.callers:
                    st.markdown(f"- `{caller}`")

    st.divider()

    # ── 3. 모듈 통합 ──────────────────────────────────────────
    st.markdown("##### 🧩 모듈 통합")

    col1, col2 = st.columns(2)
    with col1:
        label = "God Class" if quality.has_too_many_methods else ("Tiny Class" if quality.is_tiny_class else "정상")
        st.metric("메소드 수", quality.method_count, delta=label,
                  delta_color="inverse" if (quality.has_too_many_methods or quality.is_tiny_class) else "normal")
    with col2:
        dep_label = f"권장 {MAX_DEPENDENCIES}개 이하" if quality.has_too_many_dependencies else "정상"
        st.metric("의존 클래스 수", quality.dependency_count, delta=dep_label,
                  delta_color="inverse" if quality.has_too_many_dependencies else "normal")

    if quality.has_too_many_methods:
        st.error(
            f"🚨 **God Class 위험**: 메소드가 {quality.method_count}개예요. "
            "책임별로 여러 클래스로 분리하는 것을 권장합니다."
        )
    if quality.is_tiny_class:
        st.warning(
            f"⚠️ **Tiny Class**: 메소드가 {quality.method_count}개뿐이에요. "
            "다른 클래스와 통합하는 것을 고려해보세요."
        )
    if quality.has_too_many_dependencies:
        st.error(
            f"🚨 **높은 결합도**: 의존 클래스가 {quality.dependency_count}개예요. "
            f"아래 목록 중 불필요한 의존을 줄여보세요."
        )

    # 의존성 목록 + 그래프
    if quality.dep_classes or quality.callers:
        with st.expander("🔗 의존성 상세 보기 (그래프 포함)"):
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("**이 클래스가 의존하는 클래스** (→)")
                if quality.dep_classes:
                    for dep in quality.dep_classes:
                        st.markdown(f"- `{dep}`")
                else:
                    st.caption("없음")
            with col_b:
                st.markdown("**이 클래스를 호출하는 클래스** (←)")
                if quality.callers:
                    for caller in quality.callers:
                        st.markdown(f"- `{caller}`")
                else:
                    st.caption("없음")

            st.markdown("---")
            st.markdown("**의존성 그래프**")
            st.caption("🔴 화살표: 이 클래스가 의존  |  🟢 화살표: 이 클래스를 호출")
            _render_dependency_graph(class_name, quality.dep_classes, quality.callers)

    st.divider()

    # ── 4. 로직 개선 ──────────────────────────────────────────
    st.markdown("##### ⚙️ 로직 개선")
    if quality.has_method_issues:
        st.warning(f"⚠️ 파라미터 초과 메소드 {len(quality.method_issues)}개")
        for issue in quality.method_issues:
            with st.expander(f"`{issue.method_name}` — 파라미터 {issue.param_count}개"):
                st.markdown(f"**문제**: {issue.message}")

                # 실제 시그니처 표시
                params_str = ", ".join(issue.parameters) if issue.parameters else "..."
                st.code(
                    f"// 현재 시그니처\nvoid {issue.method_name}({params_str}) {{ ... }}",
                    language="java",
                )

                st.markdown("**개선 방법**")
                st.markdown(
                    "파라미터를 하나의 객체(DTO/Parameter Object)로 묶는 것을 권장합니다."
                )
                # 개선 예시
                dto_name = f"{issue.method_name.capitalize()}Params"
                st.code(
                    f"// 개선 예시: 파라미터 객체로 묶기\n"
                    f"class {dto_name} {{\n"
                    + "".join(f"    String {p};\n" for p in issue.parameters[:4])
                    + f"}}\n\nvoid {issue.method_name}({dto_name} params) {{ ... }}",
                    language="java",
                    )
    else:
        st.success("✅ 모든 메소드의 파라미터 수가 적절합니다.")
        # 파라미터 정상인 경우에도 메소드 목록 보여주기
        with st.expander("📋 전체 메소드 목록 보기"):
            data = __import__("json")
            from pathlib import Path
            ast_path = Path(__file__).parent.parent / "ast_results" / f"{project_name}.json"
            if ast_path.exists():
                import json
                with open(ast_path, encoding="utf-8") as f:
                    ast_data = json.load(f)
                target = next(
                    (c for c in ast_data.get("classes", []) if c["name"] == class_name), None
                )
                if target:
                    for m in target.get("methods", []):
                        params = m.get("parameters", [])
                        param_names = [
                            p.get("name", str(p)) if isinstance(p, dict) else str(p)
                            for p in params
                        ]
                        params_str = ", ".join(param_names) if param_names else ""
                        st.code(f"void {m['name']}({params_str})", language="java")



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

    selected_class = _render_project_summary(project_name)
    if not selected_class:
        return

    st.divider()

    _render_quality_metrics(project_name, selected_class)