import json
import time
import streamlit as st
from model.dummy_data import _DUMMY_ENDPOINTS, _DUMMY_SIM_RESPONSES, _METHOD_ICON, _SIM_DEFAULT_BODY


def render_simulator():
    st.title("🚀 API 시뮬레이터")
    if not st.session_state.selected_project:
        st.warning("⚠️ 먼저 홈에서 프로젝트를 선택해주세요!")
        return
    st.success(
        f"선택된 프로젝트: **{st.session_state.selected_project}** "
        f"— 감지된 엔드포인트 **{len(_DUMMY_ENDPOINTS)}**개"
    )

    # TODO: javalang AST 파싱 연결 — _DUMMY_ENDPOINTS 를 실제 파싱 결과로 교체
    for i, ep in enumerate(_DUMMY_ENDPOINTS):
        resp_key = f"sim_{i}"
        icon  = _METHOD_ICON.get(ep["메소드"], "⚪")
        label = f"{icon} **{ep['메소드']}** `{ep['경로']}`"

        with st.expander(label, expanded=False):
            st.caption(
                f"컨트롤러: `{ep['컨트롤러']}.{ep['핸들러']}`"
                f"  ·  파라미터: {ep['파라미터'] or '없음'}"
            )

            needs_body = ep["메소드"] in ("POST", "PUT", "PATCH")

            if needs_body:
                body_text = st.text_area(
                    "Request Body (JSON)",
                    value=_SIM_DEFAULT_BODY,
                    height=110,
                    key=f"body_{i}",
                )
            else:
                body_text = ""
                st.caption("이 메소드는 Request Body가 필요하지 않습니다.")

            if st.button("▶ 전송", key=f"send_{i}", type="primary"):
                if needs_body and body_text.strip():
                    try:
                        json.loads(body_text)
                    except json.JSONDecodeError as e:
                        st.error(f"JSON 파싱 오류: {e}")
                        st.session_state.sim_responses[resp_key] = None
                    else:
                        with st.spinner("요청 전송 중..."):
                            time.sleep(0.4)
                            # TODO: requests 실제 호출 연결
                        st.session_state.sim_responses[resp_key] = _DUMMY_SIM_RESPONSES.get(
                            ep["메소드"], {"status": 200, "body": {}}
                        )
                else:
                    with st.spinner("요청 전송 중..."):
                        time.sleep(0.4)
                        # TODO: requests 실제 호출 연결
                    st.session_state.sim_responses[resp_key] = _DUMMY_SIM_RESPONSES.get(
                        ep["메소드"], {"status": 200, "body": {}}
                    )

            cached = st.session_state.sim_responses.get(resp_key)
            if cached is not None:
                status_code = cached["status"]
                body        = cached["body"]

                if status_code < 300:
                    st.success(f"HTTP {status_code}")
                elif status_code < 400:
                    st.warning(f"HTTP {status_code}")
                else:
                    st.error(f"HTTP {status_code}")

                if body is not None:
                    st.json(body)
                else:
                    st.caption("(응답 바디 없음 — 204 No Content)")
