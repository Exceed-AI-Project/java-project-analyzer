"""
ui/analysis.py — AST 분석 페이지

흐름:
    1. 선택된 프로젝트 확인
    2. 캐시(JSON) 있으면 로드, 없으면 파싱 → 캐시 저장
    3. 클래스/메소드/호출관계 탭으로 표시
"""
import json
from dataclasses import asdict
from pathlib import Path

import streamlit as st

from models.ast import (
    AstAnalysisResult,
    CallEdge,
    JavaClass,
    JavaMethod,
    JavaParameter,
    ParseError,
)
from services.ast_service import parse_java_project
from utils.workspace import WORKSPACE_DIR
from utils.ast_cache import get_cache_path, ensure_cache_dir


# ============================================================
# 캐시 경로
# ============================================================
_CACHE_DIR = Path(__file__).parent.parent / "ast_results"


def _cache_path(project_name: str) -> Path:
    return _CACHE_DIR / f"{project_name}.json"


# ============================================================
# 캐시 I/O (dataclass <-> JSON)
# ============================================================
def _save_cache(project_name: str, result: AstAnalysisResult) -> Path:
    ensure_cache_dir()
    path = get_cache_path(project_name)
    payload = {
        "classes": [asdict(c) for c in result.classes],
        "call_edges": [asdict(e) for e in result.call_edges],
        "errors": [asdict(e) for e in result.errors],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _load_cache(project_name: str) -> AstAnalysisResult | None:
    path = get_cache_path(project_name)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return _dict_to_result(data)
    except (json.JSONDecodeError, OSError, KeyError):
        return None


def _dict_to_result(data: dict) -> AstAnalysisResult:
    """JSON dict → AstAnalysisResult 복원"""
    classes = []
    for c in data.get("classes", []):
        methods = [
            JavaMethod(
                class_name=m["class_name"],
                name=m["name"],
                return_type=m["return_type"],
                parameters=[JavaParameter(**p) for p in m.get("parameters", [])],
                access=m.get("access", "package"),
                annotations=m.get("annotations", []),
            )
            for m in c.get("methods", [])
        ]
        classes.append(JavaClass(
            file_path=c["file_path"],
            name=c["name"],
            package=c["package"],
            kind=c["kind"],
            stereotype=c.get("stereotype", "unknown"),
            annotations=c.get("annotations", []),
            extends=c.get("extends"),
            implements=c.get("implements", []),
            methods=methods,
        ))

    call_edges = [CallEdge(**e) for e in data.get("call_edges", [])]
    errors = [ParseError(**e) for e in data.get("errors", [])]
    return AstAnalysisResult(classes=classes, call_edges=call_edges, errors=errors)


# ============================================================
# 표 데이터 변환
# ============================================================
def _classes_to_rows(classes: list[JavaClass]) -> list[dict]:
    return [
        {
            "파일명": Path(c.file_path).name,
            "클래스명": c.name,
            "패키지": c.package,
            "타입": c.kind,
            "계층": c.stereotype,
            "어노테이션": ", ".join(c.annotations) if c.annotations else "",
            "메소드 수": len(c.methods),
        }
        for c in classes
    ]


def _methods_to_rows(classes: list[JavaClass]) -> list[dict]:
    rows = []
    for c in classes:
        for m in c.methods:
            params = ", ".join(f"{p.type} {p.name}" for p in m.parameters)
            rows.append({
                "클래스": c.name,
                "메소드명": m.name,
                "반환 타입": m.return_type,
                "파라미터": params,
                "접근제한자": m.access,
                "어노테이션": ", ".join(m.annotations) if m.annotations else "",
            })
    return rows


def _calls_to_rows(edges: list[CallEdge]) -> list[dict]:
    return [
        {
            "호출자 클래스": e.caller_class,
            "호출자 메소드": e.caller_method,
            "피호출 클래스": e.callee_class,
            "피호출 메소드": e.callee_method,
            "정확도": "✓" if e.is_resolved else "?",
        }
        for e in edges
    ]


# ============================================================
# 메인 렌더러
# ============================================================
def render_analysis():
    st.title("🔍 AST 분석")

    if not st.session_state.get("selected_project"):
        st.warning("⚠️ 먼저 홈에서 프로젝트를 선택해주세요!")
        return

    project_name = st.session_state.selected_project
    project_path = WORKSPACE_DIR / project_name

    st.markdown(
        f'<span style="background:#1e1e30;color:#7c9ef5;padding:4px 12px;'
        f'border-radius:20px;font-size:0.88rem;font-weight:600;">'
        f'📂 {project_name}</span>',
        unsafe_allow_html=True,
    )
    st.write("")

    # ── 캐시 로드 or 파싱 ────────────────────────────────────
    result = _load_cache(project_name)

    if result is None:
        with st.spinner("☕ Java 파일 분석 중..."):
            result = parse_java_project(project_path)
            saved_path = _save_cache(project_name, result)
        st.success(f"✅ 분석 완료! (캐시 저장: `{saved_path.name}`)")
    else:
        col_info, col_btn = st.columns([5, 1])
        with col_info:
            st.caption(f"📄 캐시된 분석 결과 사용 중 (`{get_cache_path(project_name).name}`)")
        with col_btn:
            if st.button("🔄 재분석", width="stretch"):
                with st.spinner("☕ 재분석 중..."):
                    result = parse_java_project(project_path)
                    _save_cache(project_name, result)
                st.rerun()

    if result.errors:
        with st.expander(f"⚠️ 파싱 실패 파일 {len(result.errors)}개"):
            for e in result.errors:
                st.code(f"{e.file_path}\n→ {e.error}", language="text")

    tab_classes, tab_methods, tab_calls = st.tabs(
        ["📦 클래스 목록", "⚙️ 메소드 목록", "🔗 호출 관계"]
    )

    with tab_classes:
        _render_classes_tab(result.classes)

    with tab_methods:
        _render_methods_tab(result.classes)

    with tab_calls:
        _render_calls_tab(result.call_edges)


# ============================================================
# 탭별 렌더링
# ============================================================
def _render_classes_tab(classes: list[JavaClass]) -> None:
    col_search, col_kind, col_stereo = st.columns([3, 1, 1])
    with col_search:
        keyword = st.text_input("🔍 클래스명 검색", placeholder="예) User", key="cls_search")
    with col_kind:
        kind_filter = st.selectbox(
            "타입", options=["전체", "class", "interface", "enum", "record"], key="cls_kind"
        )
    with col_stereo:
        stereo_options = ["전체"] + sorted({c.stereotype for c in classes})
        stereo_filter = st.selectbox("계층", options=stereo_options, key="cls_stereo")

    filtered = classes
    if keyword:
        filtered = [c for c in filtered if keyword.lower() in c.name.lower()]
    if kind_filter != "전체":
        filtered = [c for c in filtered if c.kind == kind_filter]
    if stereo_filter != "전체":
        filtered = [c for c in filtered if c.stereotype == stereo_filter]

    st.caption(f"총 **{len(filtered)}**개")
    st.dataframe(_classes_to_rows(filtered), width="stretch", hide_index=True)


def _render_methods_tab(classes: list[JavaClass]) -> None:
    col_search, col_cls = st.columns([3, 2])
    with col_search:
        keyword = st.text_input("🔍 메소드명 검색", placeholder="예) find", key="mtd_search")
    with col_cls:
        cls_options = ["전체"] + sorted({c.name for c in classes})
        cls_filter = st.selectbox("클래스 필터", options=cls_options, key="mtd_cls")

    rows = _methods_to_rows(classes)
    if keyword:
        rows = [r for r in rows if keyword.lower() in r["메소드명"].lower()]
    if cls_filter != "전체":
        rows = [r for r in rows if r["클래스"] == cls_filter]

    st.caption(f"총 **{len(rows)}**개")
    st.dataframe(rows, width="stretch", hide_index=True)


def _render_calls_tab(edges: list[CallEdge]) -> None:
    col_search, col_resolved = st.columns([3, 1])
    with col_search:
        keyword = st.text_input(
            "🔍 클래스명 검색 (호출자/피호출 양쪽)",
            placeholder="예) Service",
            key="call_search",
        )
    with col_resolved:
        only_resolved = st.checkbox("✓ 매핑된 것만", value=False, key="call_resolved")

    filtered = edges
    if keyword:
        k = keyword.lower()
        filtered = [
            e for e in filtered
            if k in e.caller_class.lower() or k in e.callee_class.lower()
        ]
    if only_resolved:
        filtered = [e for e in filtered if e.is_resolved]

    total = len(filtered)
    resolved_count = sum(1 for e in filtered if e.is_resolved)
    st.caption(
        f"총 **{total}**개 호출 관계 "
        f"(매핑 성공: {resolved_count}, 매핑 실패: {total - resolved_count})"
    )
    st.dataframe(_calls_to_rows(filtered), width="stretch", hide_index=True)