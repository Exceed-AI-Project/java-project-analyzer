"""
의존성 그래프
ProjectModel 의 필드 타입을 클래스 이름과 매칭해 빈 의존성 그래프를 만든다.
- 순환 의존성(cycle): Spring 부팅 실패 위험 → Finding(high)
- 고아 클래스(orphan): 아무도 의존하지 않는 service/repository/component → 데드 후보
- to_dot: st.graphviz_chart 로 렌더링할 DOT 문자열 생성 (스테레오타입 색상, 순환/고아 강조)

분석(build_model)이 끝난 ProjectModel 만 있으면 추가 파싱 없이 즉시 그래프화 가능.
"""
from __future__ import annotations

from models.analysis import ProjectModel, Finding

# 스테레오타입별 색상 (graphviz fillcolor)
_COLOR = {
    "controller": "#4F86C6", "service": "#5BB98C", "repository": "#E8A04C",
    "entity": "#9B6FB0", "dto": "#9AA0A6", "component": "#3FB6B2", "other": "#C9CDD2",
}
_BEANISH = {"controller", "service", "repository", "component"}
_ENTRY = {"controller"}   # HTTP 진입점 → 고아로 보지 않음


# ============================================================
# 그래프 구축
# ============================================================
def build_graph(model: ProjectModel) -> tuple[list[str], list[tuple[str, str]]]:
    """필드 타입 → 소유 클래스 형태의 의존성 그래프 (nodes, edges) 반환."""
    names = {c.name for c in model.classes}
    edges: set[tuple[str, str]] = set()
    for c in model.classes:
        for f in c.fields:
            # 제네릭은 컨테이너 타입(List 등)이라 의존성 의미가 약함 → 떼고 핵심 타입만 매칭.
            t = f.type.split("<")[0].strip()
            if t in names and t != c.name:
                edges.add((c.name, t))
    nodes = sorted(names)
    return nodes, sorted(edges)


# ============================================================
# 순환 의존성 (DFS)
# ============================================================
def find_cycles(edges: list[tuple[str, str]]) -> list[list[str]]:
    """엣지 리스트에서 순환 의존성을 찾아 노드 시퀀스(시작→...→시작)들로 반환."""
    adj: dict[str, list[str]] = {}
    for a, b in edges:
        adj.setdefault(a, []).append(b)

    cycles: list[list[str]] = []
    # 3색 DFS: 회색(탐색 중) 노드를 다시 만나면 백엣지 = 사이클.
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {}
    stack: list[str] = []

    def dfs(u: str):
        color[u] = GRAY
        stack.append(u)
        for v in adj.get(u, []):
            if color.get(v, WHITE) == GRAY:
                if v in stack:
                    cycles.append(stack[stack.index(v):] + [v])
            elif color.get(v, WHITE) == WHITE:
                dfs(v)
        stack.pop()
        color[u] = BLACK

    for n in list(adj.keys()):
        if color.get(n, WHITE) == WHITE:
            dfs(n)
    # 같은 사이클이 시작점만 다르게 여러 번 잡힐 수 있으므로 노드 집합 기준 중복 제거.
    uniq, seen = [], set()
    for cy in cycles:
        key = frozenset(cy)
        if key not in seen:
            seen.add(key)
            uniq.append(cy)
    return uniq


# ============================================================
# 고아(데드) 클래스
# ============================================================
def find_orphans(model: ProjectModel, edges: list[tuple[str, str]]) -> list[str]:
    """들어오는 의존성이 없는 빈(주입 받는 곳이 없는 service/repository/component)을 반환."""
    incoming = {b for _, b in edges}
    orphans = []
    for c in model.classes:
        # controller 는 HTTP 진입점이라 다른 빈에서 주입받지 않는 게 정상 → 고아로 보지 않음.
        if c.stereotype in _BEANISH and c.stereotype not in _ENTRY:
            if c.name not in incoming:
                orphans.append(c.name)
    return orphans


# ============================================================
# 그래프 기반 Finding
# ============================================================
def graph_findings(model: ProjectModel) -> list[Finding]:
    nodes, edges = build_graph(model)
    out: list[Finding] = []
    by_name = model.by_name

    for cy in find_cycles(edges):
        chain = " → ".join(cy)
        head = by_name.get(cy[0])
        out.append(Finding(
            "high", "CIRCULAR_DEP",
            f"{head.file_path if head else cy[0]} > {cy[0]}",
            f"순환 의존성 감지: {chain}. 생성자 주입 시 Spring 부팅 실패 가능.",
            "의존성 방향을 한쪽으로 정리하거나 중간 추상화/이벤트로 분리.",
        ))

    for orphan in find_orphans(model, edges):
        ci = by_name.get(orphan)
        out.append(Finding(
            "low", "ORPHAN_BEAN",
            f"{ci.file_path if ci else orphan} > {orphan}",
            f"'{orphan}' 를 주입받는 곳이 없음 (미사용 빈 후보).",
            "실제 미사용이면 제거. 리플렉션/설정으로만 쓰이면 무시.",
        ))
    return out


# ============================================================
# DOT 생성 (st.graphviz_chart 용)
# ============================================================
def to_dot(model: ProjectModel) -> str:
    nodes, edges = build_graph(model)
    cycles = find_cycles(edges)
    orphans = set(find_orphans(model, edges))
    cycle_nodes = {n for cy in cycles for n in cy}
    cycle_edges = set()
    for cy in cycles:
        for i in range(len(cy) - 1):
            cycle_edges.add((cy[i], cy[i + 1]))

    by_name = model.by_name
    lines = ['digraph deps {', '  rankdir=LR;', '  node [style=filled, fontname="sans-serif", shape=box];']

    for n in nodes:
        ci = by_name.get(n)
        st = ci.stereotype if ci else "other"
        fill = _COLOR.get(st, _COLOR["other"])
        attrs = [f'fillcolor="{fill}"', 'fontcolor=white']
        label = f"{n}\\n[{st}]"
        if n in orphans:
            attrs += ['color="#D64545"', 'penwidth=3', 'style="filled,dashed"']
            label += "\\n(orphan)"
        if n in cycle_nodes:
            attrs += ['color="#D64545"', 'penwidth=3']
        lines.append(f'  "{n}" [label="{label}", {", ".join(attrs)}];')

    for a, b in edges:
        if (a, b) in cycle_edges:
            lines.append(f'  "{a}" -> "{b}" [color="#D64545", penwidth=2];')
        else:
            lines.append(f'  "{a}" -> "{b}" [color="#9AA0A6"];')

    lines.append('}')
    return "\n".join(lines)
