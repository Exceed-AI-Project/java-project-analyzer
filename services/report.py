"""
분석 결과 영속화 + 리포트
- 결함(Finding)을 .analysis/findings.json 에 저장/로드 (새로고침해도 유지)
- Markdown 리포트 생성 (다운로드/논문·데모용)
"""
from __future__ import annotations
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from collections import Counter, defaultdict

from models.analysis import Finding, ProjectModel

ANALYSIS_DIR = ".analysis"
_FINDINGS_FILE = "findings.json"


def save_findings(project_root: str, findings: list[Finding]) -> str:
    """탐지 결과를 .analysis/findings.json 에 저장하고 저장 경로 반환."""
    d = Path(project_root) / ANALYSIS_DIR
    d.mkdir(exist_ok=True)
    payload = {
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "findings": [asdict(f) for f in findings],
    }
    (d / _FINDINGS_FILE).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(d / _FINDINGS_FILE)


def load_findings(project_root: str) -> tuple[list[Finding], str] | None:
    """저장된 탐지 결과를 (findings, 저장시각) 으로 복원. 없으면 None."""
    p = Path(project_root) / ANALYSIS_DIR / _FINDINGS_FILE
    if not p.exists():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    return [Finding(**f) for f in data["findings"]], data.get("saved_at", "")


def to_markdown(project_name: str, findings: list[Finding],
                model: ProjectModel | None = None) -> str:
    """탐지 결과를 다운로드용 Markdown 리포트로 변환."""
    sev_order = {"high": 0, "medium": 1, "low": 2}
    sev_count = Counter(f.severity for f in findings)
    cat_count = Counter(f.category for f in findings)

    lines = [
        f"# 코드 분석 리포트 — {project_name}",
        f"_생성: {datetime.now().isoformat(timespec='seconds')}_",
        "",
        "## 요약",
        f"- 총 결함: **{len(findings)}**  "
        f"(🔴 high {sev_count.get('high',0)} · 🟡 medium {sev_count.get('medium',0)} · 🟢 low {sev_count.get('low',0)})",
    ]
    if model is not None:
        lines.append(f"- 분석 클래스: {len(model.classes)} · 파싱 실패: {len(model.parse_errors)}")
    lines.append("")
    lines.append("### 카테고리별")
    for cat, n in cat_count.most_common():
        lines.append(f"- `{cat}`: {n}")
    lines.append("")

    lines.append("## 상세")
    by_cat = defaultdict(list)
    for f in findings:
        by_cat[f.category].append(f)
    sev_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}
    for cat in sorted(by_cat, key=lambda c: min(sev_order.get(x.severity, 9) for x in by_cat[c])):
        lines.append(f"### {cat}")
        for f in sorted(by_cat[cat], key=lambda x: sev_order.get(x.severity, 9)):
            lines.append(f"- {sev_icon.get(f.severity,'⚪')} **{f.location}**")
            lines.append(f"  - {f.message}")
            if f.suggestion:
                lines.append(f"  - 💡 {f.suggestion}")
        lines.append("")
    return "\n".join(lines)
