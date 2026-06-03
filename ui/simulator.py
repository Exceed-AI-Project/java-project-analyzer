"""
API 시뮬레이터 페이지 — Spring 앱을 띄우지 않고 정적 추적으로 요청 파이프라인 검증.

엔드포인트 선택 → (선택) LLM 페이로드 생성 → 가상 요청 → 제약 위반/호출 경로 출력.
검출된 위반은 리팩토링 페이지로 직접 전송 가능.
"""
import streamlit as st
import json
from services.ast_analyzer import build_model
from services.api_simulator import (
    extract_endpoints, resolve_schema, simulate_request, trace_call_path,
    generate_payload,
)
from services.refactor_loop import violation_to_finding
from services.project_manager import scan_projects

_SEV = {"high": "🔴", "medium": "🟡", "low": "🟢"}


def _project_path():
    name = st.session_state.selected_project
    for p in scan_projects():
        if p.name == name:
            return p.path
    return None


def render_simulator():
    st.title("🚀 API 시뮬레이터")
    if not st.session_state.selected_project:
        st.warning("⚠️ 먼저 홈에서 프로젝트를 선택해주세요!")
        return

    st.success(f"선택된 프로젝트: **{st.session_state.selected_project}**")
    st.caption("앱을 띄우지 않고 정적 경로 추적으로 '이 요청 들어오면 어디서 깨지는지'를 미리 본다.")

    model = st.session_state.get("ast_model")
    if model is None or st.button("엔드포인트 스캔"):
        with st.spinner("AST 파싱 + 엔드포인트 추출 중..."):
            model = build_model(_project_path())
            st.session_state.ast_model = model

    endpoints = extract_endpoints(model)
    if not endpoints:
        st.info("@RestController / @Controller 엔드포인트를 찾지 못했어요.")
        return

    labels = [f"{e.http_method} {e.path}  ({e.controller}.{e.method})" for e in endpoints]
    idx = st.selectbox("엔드포인트 선택", range(len(endpoints)), format_func=lambda i: labels[i])
    ep = endpoints[idx]

    # 호출 경로
    st.subheader("📡 호출 경로 (정적 추적)")
    path = trace_call_path(ep, model)
    st.code(" → ".join(path) if path else "(추적 불가)")

    required = resolve_schema(ep.request_body_type, model)
    st.subheader("🧪 가상 요청 페이로드")
    if ep.request_body_type:
        st.caption(f"바디 타입: `{ep.request_body_type}` · 필수 필드: "
                   + (", ".join(f"{r.name}({r.reason})" for r in required) or "없음"))
    else:
        st.caption("이 엔드포인트는 @RequestBody 가 없습니다 (path/param 위주).")

    # ─── LLM 페이로드 자동 생성 (키 검증된 경우만) ───
    llm_ok = st.session_state.get("llm_ok")
    if ep.request_body_type:
        if llm_ok:
            lc1, lc2 = st.columns([3, 1])
            mode = lc1.radio("LLM 생성 모드", ["valid", "edge"], horizontal=True,
                             format_func=lambda m: "정상 데이터" if m == "valid" else "엣지(위반 유도)")
            if lc2.button("🤖 LLM 페이로드 생성", use_container_width=True):
                with st.spinner("LLM 이 DTO 제약 보고 JSON 생성 중..."):
                    payload, note = generate_payload(ep, model, st.session_state["openai_key"], mode)
                if payload is None:
                    st.error(note)
                else:
                    st.session_state.sim_payload = json.dumps(payload, ensure_ascii=False, indent=2)
                    st.caption(note)
        else:
            st.info("🔒 LLM 페이로드 자동생성은 홈에서 API 키 검증 후 열립니다. 아래에 직접 입력은 가능.")

    default = st.session_state.get("sim_payload") or json.dumps(
        {r.name: "" for r in required}, ensure_ascii=False, indent=2)
    raw = st.text_area("JSON 페이로드", value=default, height=180,
                       disabled=not ep.request_body_type)

    if st.button("가상 요청 시뮬레이션", type="primary"):
        try:
            payload = json.loads(raw or "{}")
        except json.JSONDecodeError as e:
            st.error(f"JSON 파싱 오류: {e}")
            return
        st.session_state.sim_result = {"ep": idx, "violations": simulate_request(ep, payload, model)}

    res = st.session_state.get("sim_result")
    if res and res["ep"] == idx:
        st.subheader("결과")
        violations = res["violations"]
        if not violations:
            st.success("제약 위반 없음 — 이 페이로드는 정적 검사 기준 통과 👍")
        for i, v in enumerate(violations):
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                c1.markdown(f"{_SEV.get(v.severity,'⚪')} **{v.rule}** · `{v.field}`")
                c1.write(v.message)
                if c2.button("🛠 리팩토링으로", key=f"send_{i}"):
                    st.session_state.injected_finding = violation_to_finding(v, ep, model)
                    st.toast("리팩토링 제안 페이지로 보냈어요 (사이드바에서 이동)", icon="🛠️")
