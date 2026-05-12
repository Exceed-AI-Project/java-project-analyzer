import streamlit as st
import streamlit.components.v1 as components
from service.graph_service import _build_graph_html


def render_dependency_graph():
    st.title("🕸️ 의존성 그래프")
    if not st.session_state.selected_project:
        st.warning("⚠️ 먼저 홈에서 프로젝트를 선택해주세요!")
        return
    st.success(f"선택된 프로젝트: **{st.session_state.selected_project}**")

    graph_type = st.selectbox(
        "그래프 유형",
        options=["클래스 의존성 그래프", "메소드 호출 그래프", "패키지 의존성 그래프"],
        key="dep_graph_type",
    )

    st.caption(
        "파랑 Controller · 노랑 Service · 초록 Repository · 주황 Model  "
        "│  패키지 그래프는 육각형 노드로 표시됩니다."
    )

    # TODO: NetworkX + Pyvis 연결 — _build_graph_html 을 실제 분석 결과로 교체
    graph_html = _build_graph_html(graph_type=graph_type)
    components.html(graph_html, height=500, scrolling=False)

    st.download_button(
        label="⬇️ 그래프 HTML 다운로드",
        data=graph_html.encode("utf-8"),
        file_name=f"{st.session_state.selected_project}_{graph_type}.html",
        mime="text/html",
        help="의존성 그래프를 standalone HTML 파일로 저장합니다.",
    )
