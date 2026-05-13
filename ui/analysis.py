import streamlit as st

from ui.css.analysis import ANALYSIS_CSS
from model.dummy_data import _DUMMY_CLASSES, _DUMMY_METHODS, _DUMMY_CALL_GRAPH


def render_analysis():
    st.markdown(ANALYSIS_CSS, unsafe_allow_html=True)

    st.title("🔍 AST 분석")

    if not st.session_state.get("selected_project"):
        st.warning("⚠️ 먼저 홈에서 프로젝트를 선택해주세요!")
        st.stop()

    st.markdown(
        f'<span style="background:#1e1e30;color:#7c9ef5;padding:4px 12px;'
        f'border-radius:20px;font-size:0.88rem;font-weight:600;">'
        f'📂 {st.session_state.selected_project}</span>',
        unsafe_allow_html=True,
    )
    st.write("")

    # TODO: javalang AST 파싱 연결 — 아래 더미 데이터를 실제 파싱 결과로 교체
    classes    = _DUMMY_CLASSES
    methods    = _DUMMY_METHODS
    call_graph = _DUMMY_CALL_GRAPH

    tab_classes, tab_methods, tab_calls = st.tabs(
        ["📦 클래스 목록", "⚙️ 메소드 목록", "🔗 호출 관계"]
    )

    with tab_classes:
        col_search, col_filter = st.columns([3, 1])
        with col_search:
            cls_search = st.text_input(
                "🔍 클래스명 검색", placeholder="예) User", key="cls_search"
            )
        with col_filter:
            cls_type = st.selectbox(
                "타입 필터", options=["전체", "Class", "Interface"], key="cls_type_filter"
            )

        result = classes
        if cls_search:
            result = [c for c in result if cls_search.lower() in c["클래스명"].lower()]
        if cls_type != "전체":
            result = [c for c in result if c["타입"] == cls_type]

        st.caption(f"총 **{len(result)}**개")
        st.dataframe(result, use_container_width=True, hide_index=True)

    with tab_methods:
        col_search2, col_cls = st.columns([3, 2])
        with col_search2:
            mtd_search = st.text_input(
                "🔍 메소드명 검색", placeholder="예) find", key="mtd_search"
            )
        with col_cls:
            cls_options = ["전체"] + sorted({m["클래스"] for m in methods})
            mtd_cls = st.selectbox("클래스 필터", options=cls_options, key="mtd_cls_filter")

        result_m = methods
        if mtd_search:
            result_m = [m for m in result_m if mtd_search.lower() in m["메소드명"].lower()]
        if mtd_cls != "전체":
            result_m = [m for m in result_m if m["클래스"] == mtd_cls]

        st.caption(f"총 **{len(result_m)}**개")
        st.dataframe(result_m, use_container_width=True, hide_index=True)

    with tab_calls:
        call_search = st.text_input(
            "🔍 클래스명 검색", placeholder="예) Service", key="call_search"
        )

        result_c = call_graph
        if call_search:
            result_c = [
                r for r in result_c
                if call_search.lower() in r["호출자 클래스"].lower()
                or call_search.lower() in r["피호출 클래스"].lower()
            ]

        st.caption(f"총 **{len(result_c)}**개 호출 관계")
        st.dataframe(result_c, use_container_width=True, hide_index=True)
