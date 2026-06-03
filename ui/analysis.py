"""
AST 분석 페이지 — 규칙 기반 탐지(Finding) + 임베딩 기반 AI 보조 리뷰.

규칙 탐지(파서가 무엇이든 동일)와 LLM 리뷰(API 키 필요)를 분리해, 키 없어도
정적 분석은 그대로 사용 가능하다.
"""
import streamlit as st
from services.ast_analyzer import build_model, run_all_detectors
from services.project_manager import scan_projects
from services import report, embedding as emb, llm_review

_SEV = {"high": "🔴", "medium": "🟡", "low": "🟢"}


def _project_path():
    name = st.session_state.selected_project
    for p in scan_projects():
        if p.name == name:
            return p.path
    return None


def render_analysis():
    st.title("🔍 AST 분석")
    if not st.session_state.selected_project:
        st.warning("⚠️ 먼저 홈에서 프로젝트를 선택해주세요!")
        return
    path = _project_path()
    name = st.session_state.selected_project
    st.success(f"선택된 프로젝트: **{name}**")

    # 영속된 결과 자동 로드
    if st.session_state.get("ast_findings") is None:
        saved = report.load_findings(path)
        if saved:
            st.session_state.ast_findings = saved[0]
            st.caption(f"💾 저장된 분석 결과 로드됨 ({saved[1]})")

    if st.button("분석 실행 (규칙 탐지)", type="primary"):
        with st.spinner("파싱 + 규칙 탐지 중..."):
            model = build_model(path)
            findings = run_all_detectors(model)
            report.save_findings(path, findings)   # 자동 영속화
        st.session_state.ast_model = model
        st.session_state.ast_findings = findings

    model = st.session_state.get("ast_model")
    findings = st.session_state.get("ast_findings")
    if findings is None:
        st.info("‘분석 실행’ 을 눌러 시작하세요.")
        return

    if model is not None:
        c = st.columns(3)
        c[0].metric("클래스", len(model.classes))
        c[1].metric("탐지 항목", len(findings))
        c[2].metric("파싱 실패", len(model.parse_errors))
        if model.parse_errors:
            with st.expander(f"⚠️ 파싱 실패 {len(model.parse_errors)}건"):
                for f, err in model.parse_errors:
                    st.caption(f"`{f}` — {err}")

    # 리포트 내보내기
    with st.expander("📄 리포트 내보내기"):
        md = report.to_markdown(name, findings, model)
        st.download_button("Markdown 다운로드", md, file_name=f"{name}_report.md")

    st.subheader("규칙 탐지 결과")
    if not findings:
        st.success("탐지된 결함 없음 👍")
    for f in findings:
        with st.container(border=True):
            st.markdown(f"{_SEV.get(f.severity,'⚪')} **{f.category}** · `{f.location}`")
            st.write(f.message)
            if f.suggestion:
                st.caption(f"💡 {f.suggestion}")

    # ── 임베딩 + AI 보조 리뷰 (규칙으로 못 잡는 판단) ──
    st.divider()
    st.subheader("🤖 AI 보조 리뷰 (임베딩 기반)")
    if not st.session_state.get("llm_ok"):
        st.info("🔒 홈에서 API 키 검증 후 사용 가능.")
        return

    key = st.session_state["openai_key"]
    cc = st.columns(2)
    if cc[0].button("임베딩 인덱스 생성/갱신"):
        with st.spinner("청킹 + 임베딩 중..."):
            chunks = emb.build_chunks(path)
            index, chunks = emb.build_index(chunks, emb.openai_embedder(key))
            emb.save_index(path, index, chunks)
        st.success(f"인덱스 생성 완료 ({len(chunks)} 청크)")

    focus = st.text_input("리뷰 초점(선택)", placeholder="예: 결제 로직, 네이밍, 검증 누락")
    if cc[1].button("AI 리뷰 실행", type="primary"):
        with st.spinner("관련 코드 검색 + LLM 리뷰 중..."):
            issues, note = llm_review.review(path, key, focus)
        st.caption(note)
        for it in issues:
            with st.container(border=True):
                sev = it.get("severity", "low")
                st.markdown(f"{_SEV.get(sev,'⚪')} **{it.get('category','REVIEW')}** · `{it.get('where','')}`")
                st.write(it.get("message", ""))
                if it.get("suggestion"):
                    st.caption(f"💡 {it['suggestion']}")
