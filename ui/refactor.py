import streamlit as st
from services.ast_analyzer import build_model, run_all_detectors
from services.refactor_loop import propose_fix, apply_and_verify, parse_location, batch_propose, batch_apply
from services.project_manager import scan_projects

_SEV = {"high": "🔴", "medium": "🟡", "low": "🟢"}


def _project_path():
    name = st.session_state.selected_project
    for p in scan_projects():
        if p.name == name:
            return p.path
    return None


def render_refactor():
    st.title("🛠️ 리팩토링 제안")
    if not st.session_state.selected_project:
        st.warning("⚠️ 먼저 홈에서 프로젝트를 선택해주세요!")
        return
    st.success(f"선택된 프로젝트: **{st.session_state.selected_project}**")
    st.caption("오류 발견 → 리팩토링 제안 → 확인 → 코드 재구성 → 검증")

    root = _project_path()

    # 1) 오류 발견
    model = st.session_state.get("ast_model")
    findings = st.session_state.get("ast_findings")
    if model is None or findings is None or st.button("오류 재탐지"):
        with st.spinner("탐지 중..."):
            model = build_model(root)
            findings = run_all_detectors(model)
        st.session_state.ast_model = model
        st.session_state.ast_findings = findings

    # 시뮬레이터에서 보낸 위반(Violation→Finding) 수용
    injected = st.session_state.get("injected_finding")
    if injected:
        findings = [injected] + [f for f in findings]
        st.info(f"🛠 시뮬레이터에서 전달된 위반 1건이 목록 맨 위에 추가됨: {injected.category}")

    # 의존성 맵에서 클릭해 들어온 클래스 포커스
    focus = st.session_state.get("focus_class")
    if focus:
        cols = st.columns([4, 1])
        cols[0].info(f"🎯 '{focus}' 클래스 포커스 (의존성 맵에서 선택)")
        if cols[1].button("포커스 해제", use_container_width=True):
            st.session_state.focus_class = None
            st.rerun()
        scoped = [f for f in findings
                  if (f.location.split(">")[1].strip() if ">" in f.location else "") == focus]
        if not scoped:
            st.warning(f"'{focus}' 에 감지된 결함이 없어요. 자유 수정은 질의 페이지에서 가능합니다.")
            if st.button("💬 질의 페이지로 이 클래스 보내기"):
                st.session_state.query_focus_class = focus
                st.session_state.menu = "💬 RAG 질의응답"
                st.rerun()
            return
        findings = scoped

    if not findings:
        st.success("탐지된 결함 없음 👍")
        return

    if not st.session_state.get("llm_ok"):
        st.error("🔒 리팩토링 제안은 홈에서 API 키 검증 후 사용 가능 (탐지 결과는 위에서 확인 가능).")

    # 2) 결함 선택
    labels = [f"{_SEV.get(f.severity,'⚪')} [{f.category}] {f.location}" for f in findings]
    idx = st.selectbox("수정할 결함 선택", range(len(findings)), format_func=lambda i: labels[i])
    target = findings[idx]
    with st.container(border=True):
        st.write(f"**문제** · {target.message}")
        if target.suggestion:
            st.caption(f"💡 {target.suggestion}")

    # 3) 리팩토링 제안 (diff)
    if st.session_state.get("llm_ok") and st.button("리팩토링 제안 생성", type="primary"):
        with st.spinner("LLM 이 수정안(diff) 생성 중..."):
            prop = propose_fix(target, root, model, st.session_state["openai_key"])
        st.session_state.loop_proposal = prop
        st.session_state.loop_finding_idx = idx

    _render_batch(findings, root, model)

    prop = st.session_state.get("loop_proposal")
    if prop and st.session_state.get("loop_finding_idx") == idx:
        if not prop.ok:
            st.error(prop.note)
        elif not prop.diff:
            st.info(prop.note or "변경 없음")
        else:
            st.subheader("제안된 변경 (diff)")
            st.code(prop.diff, language="diff")
            # 4) 사용자 확인 → 5) 코드 재구성 + 검증
            st.warning("검토 후 적용하세요. 적용 시 원본 파일이 수정되고 재탐지로 검증합니다.")
            if st.button("✅ 확인 — 코드 재구성 적용", type="secondary"):
                with st.spinner("적용 → 컴파일 검증 → 재탐지 중..."):
                    ok, msg, new_model, new_findings = apply_and_verify(target, prop, root)
                st.session_state.ast_model = new_model
                st.session_state.ast_findings = new_findings
                st.session_state.loop_proposal = None
                st.session_state.injected_finding = None  # 처리 완료
                if ok:
                    st.success(msg.split("\n")[0])
                else:
                    st.error(msg.split("\n")[0])
                if "\n" in msg:
                    st.code(msg.split("\n", 1)[1])
                st.rerun()


def _render_batch(findings, root, model):
    with st.expander("📦 배치 모드 — 여러 결함 일괄 처리"):
        if not st.session_state.get("llm_ok"):
            st.info("🔒 API 키 검증 후 사용 가능.")
            return
        n = st.number_input("상위 N개 결함 일괄 제안", 1, 20, 5)
        if st.button("일괄 제안 생성"):
            with st.spinner(f"{n}건 제안 생성 중..."):
                st.session_state.batch_items = batch_propose(
                    findings, root, model, st.session_state["openai_key"], limit=int(n))
        items = st.session_state.get("batch_items")
        if not items:
            return
        valid = [(f, p) for f, p in items if p.ok and p.diff]
        st.caption(f"diff 생성된 제안: {len(valid)} / {len(items)}")
        for f, p in valid:
            with st.expander(f"{f.category} · {f.location}"):
                st.code(p.diff, language="diff")
        st.warning("전체 적용은 all-or-nothing: 일괄 적용 후 1회 컴파일, 실패 시 변경 전체 원복.")
        if st.button("✅ 전체 적용 (컴파일 검증)", type="primary"):
            with st.spinner("일괄 적용 + 컴파일 + 재탐지..."):
                ok, msg, nm, nf = batch_apply(valid, root)
            st.session_state.ast_model = nm
            st.session_state.ast_findings = nf
            st.session_state.batch_items = None
            (st.success if ok else st.error)(msg.split(chr(10))[0])
            if chr(10) in msg:
                st.code(msg.split(chr(10), 1)[1])
