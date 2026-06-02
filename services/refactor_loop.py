"""
리팩토링 루프 오케스트레이터
  오류 발견(Finding) → 리팩토링 제안(diff) → 사용자 확인 → 코드 재구성(apply) → 검증

- 탐지기(ast_analyzer)가 낸 Finding 을 LLM 수정 요청으로 변환
- query_refactor.propose_change 로 통합 diff 생성 (자동 적용 X)
- 사용자가 적용하면 모델을 다시 빌드해 같은 결함이 사라졌는지 검증
"""
from __future__ import annotations
from pathlib import Path

from models.analysis import ProjectModel, Finding
from services.ast_analyzer import build_model, run_all_detectors
from services.query_refactor import propose_change, apply_proposal, RefactorProposal
from services.verify import compile_project


# ============================================================
# Finding 파싱 헬퍼
# ============================================================
def parse_location(location: str) -> tuple[str, str, str]:
    """'file > Class > method()' → (rel_file, class_name, method)"""
    parts = [p.strip() for p in location.split(">")]
    rel_file = parts[0] if parts else ""
    cls = parts[1] if len(parts) > 1 else ""
    method = parts[2].rstrip("()") if len(parts) > 2 else ""
    return rel_file, cls, method


# ============================================================
# Finding → LLM 수정 요청
# ============================================================
def finding_to_query(finding: Finding) -> str:
    rel, cls, method = parse_location(finding.location)
    target = f"클래스 {cls}" + (f" 의 {method}() 메서드" if method else "")
    return (
        f"다음 결함을 수정해줘.\n"
        f"- 대상: {target}\n"
        f"- 문제: {finding.message}\n"
        f"- 수정 방향: {finding.suggestion or '적절히 리팩토링'}\n"
        f"동작은 보존하고, 해당 결함만 정확히 해소할 것."
    )


def propose_fix(finding: Finding, project_root: str, model: ProjectModel,
                api_key: str) -> RefactorProposal:
    rel, _, _ = parse_location(finding.location)
    file_path = str(Path(project_root) / rel)
    query = finding_to_query(finding)
    return propose_change(query, file_path, model, api_key)


# ============================================================
# 적용 + 검증
# ============================================================
def apply_and_verify(finding: Finding, proposal: RefactorProposal,
                     project_root: str) -> tuple[bool, str, ProjectModel, list[Finding]]:
    """제안 적용 → 컴파일 검증 → 결함 해소 재탐지.
    컴파일이 깨지면(LLM 이 망가뜨림) 원본으로 자동 원복.
    반환: (정상종료여부, 메시지, 새 모델, 새 findings)
    """
    written, wmsg = apply_proposal(proposal)
    if not written:
        m = build_model(project_root)
        return False, wmsg, m, run_all_detectors(m)

    # 1) 컴파일 검증
    compiled, clog = compile_project(project_root)
    if compiled is False:
        # 빌드 깨짐 → 안전하게 원복
        try:
            Path(proposal.file_path).write_text(proposal.original, encoding="utf-8")
            revert = "원본으로 자동 원복함"
        except Exception as e:
            revert = f"원복 실패: {e}"
        m = build_model(project_root)
        return False, f"❌ 컴파일 실패 → {revert}\n{clog}", m, run_all_detectors(m)

    # 2) 재탐지 + 결함 해소 확인
    new_model = build_model(project_root)
    new_findings = run_all_detectors(new_model)
    _, cls, _ = parse_location(finding.location)
    still_there = any(
        f.category == finding.category and parse_location(f.location)[1] == cls
        for f in new_findings
    )
    compile_note = "컴파일 OK" if compiled else "컴파일 검증 생략"
    if still_there:
        status = f"⚠️ 동일 유형({finding.category}) 결함이 {cls} 에 아직 남음 (재검토 필요)"
    else:
        status = f"✅ {finding.category} 결함 해소 확인"
    return True, f"{wmsg} · {compile_note} · {status}", new_model, new_findings


# ============================================================
# 시뮬레이터 Violation → Finding 어댑터 (위반도 같은 루프로)
# ============================================================
def violation_to_finding(violation, endpoint, model: ProjectModel) -> Finding:
    """API 시뮬레이터의 Violation 을 리팩토링 루프가 다룰 Finding 으로 변환.
    위치는 해당 엔드포인트의 컨트롤러 핸들러로 잡는다.
    """
    ctrl = model.by_name.get(endpoint.controller)
    file_path = ctrl.file_path if ctrl else endpoint.controller
    return Finding(
        severity=violation.severity,
        category=f"SIM_{violation.rule}",
        location=f"{file_path} > {endpoint.controller} > {endpoint.method}()",
        message=f"[{endpoint.http_method} {endpoint.path}] {violation.message}",
        suggestion="요청 검증/DTO 제약 또는 핸들러 시그니처를 조정해 해당 위반을 해소.",
    )


# ============================================================
# 배치 모드: 여러 결함을 한 번에 제안 → 일괄 적용 → 1회 컴파일 (all-or-nothing)
# ============================================================
def batch_propose(findings: list[Finding], project_root: str, model: ProjectModel,
                  api_key: str, limit: int = 10) -> list[tuple[Finding, RefactorProposal]]:
    out = []
    for f in findings[:limit]:
        out.append((f, propose_fix(f, project_root, model, api_key)))
    return out


def batch_apply(items: list[tuple[Finding, RefactorProposal]],
                project_root: str) -> tuple[bool, str, ProjectModel, list[Finding]]:
    """승인된 (finding, proposal) 들을 일괄 적용 → 1회 컴파일.
    컴파일 실패 시 변경 파일 전체 원복(all-or-nothing).
    """
    originals: dict[str, str] = {}
    applied = 0
    for finding, prop in items:
        if not prop.ok or not prop.diff:
            continue
        if prop.file_path not in originals:
            originals[prop.file_path] = prop.original
        try:
            Path(prop.file_path).write_text(prop.proposed, encoding="utf-8")
            applied += 1
        except Exception:
            pass

    if applied == 0:
        m = build_model(project_root)
        return False, "적용할 변경이 없음", m, run_all_detectors(m)

    compiled, clog = compile_project(project_root)
    if compiled is False:
        for fp, orig in originals.items():
            try:
                Path(fp).write_text(orig, encoding="utf-8")
            except Exception:
                pass
        m = build_model(project_root)
        return False, f"❌ 배치 컴파일 실패 → {len(originals)}개 파일 전체 원복\n{clog}", m, run_all_detectors(m)

    new_model = build_model(project_root)
    new_findings = run_all_detectors(new_model)
    note = "컴파일 OK" if compiled else "컴파일 검증 생략"
    return True, f"✅ {applied}건 적용 · {note} · 잔여 결함 {len(new_findings)}건", new_model, new_findings
