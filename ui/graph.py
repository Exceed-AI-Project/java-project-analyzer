import json
from collections import defaultdict
import streamlit as st
import streamlit.components.v1 as components
from services.ast_analyzer import build_model, run_all_detectors
from services import depgraph
from services.project_manager import scan_projects

# 빛나는 다크 팔레트 (스테레오타입별)
_PALETTE = {
    "controller": "#5B8DEF", "service": "#4FD1C5", "repository": "#F6AD55",
    "entity":     "#B794F4", "dto":     "#A0AEC0", "component": "#38B2AC",
    "other":      "#7B8AA6",
}
_REFACTOR_MENU = "🛠️ 리팩토링 제안"
_BG = "radial-gradient(circle at 50% 38%, #1b2a4a 0%, #0b1124 62%, #060912 100%)"


def _project_path():
    name = st.session_state.selected_project
    for p in scan_projects():
        if p.name == name:
            return p.path
    return None


def _hover(ci, fcount, high):
    anns = ", ".join("@" + a for a in ci.annotations) or "-"
    methods = ", ".join(f"{m.name}()" for m in ci.methods[:6])
    if len(ci.methods) > 6:
        methods += f" +{len(ci.methods)-6}"
    warn = (f"<br><span style='color:#ff8f8f'>⚠ 결함 {fcount}건"
            + (f" (high {high})" if high else "") + "</span>") if fcount else ""
    return (f"<div style='font-family:sans-serif;color:#e7eeff;padding:4px 2px'>"
            f"<b style='font-size:13px'>{ci.name}</b> "
            f"<span style='color:#9fb3da'>[{ci.stereotype}]</span><br>"
            f"<span style='color:#9fb3da'>annotations:</span> {anns}<br>"
            f"<span style='color:#9fb3da'>fields {len(ci.fields)} · methods {len(ci.methods)}</span><br>"
            f"<span style='color:#cdd9f5'>{methods}</span>{warn}</div>")


def _build_html(model, findings):
    nodes_list, edges_list = depgraph.build_graph(model)
    cycles = depgraph.find_cycles(edges_list)
    orphans = set(depgraph.find_orphans(model, edges_list))
    cycle_nodes = {n for cy in cycles for n in cy}
    cycle_edges = {(cy[i], cy[i+1]) for cy in cycles for i in range(len(cy)-1)}

    by_class = defaultdict(list)
    for f in findings:
        cls = f.location.split(">")[1].strip() if ">" in f.location else ""
        by_class[cls].append(f)
    degree = defaultdict(int)
    for a, b in edges_list:
        degree[a] += 1; degree[b] += 1

    by_name = model.by_name
    nodes = []
    for n in nodes_list:
        ci = by_name.get(n)
        stereo = ci.stereotype if ci else "other"
        base = _PALETTE.get(stereo, _PALETTE["other"])
        flagged = n in cycle_nodes or n in orphans
        border = "#FF5A5A" if flagged else base
        fnds = by_class.get(n, [])
        high = sum(1 for f in fnds if f.severity == "high")
        nodes.append({
            "id": n, "label": n,
            "title": _hover(ci, len(fnds), high) if ci else n,
            "value": degree.get(n, 1) + 1,
            "shape": "dot",
            "color": {"background": base, "border": border,
                      "highlight": {"background": base, "border": "#FFFFFF"}},
            "borderWidth": 4 if flagged else 2,
            "shadow": {"enabled": True, "color": base, "size": 22, "x": 0, "y": 0},
            "font": {"color": "#e7eeff", "size": 14, "strokeWidth": 0, "vadjust": -2},
        })
    edges = []
    for a, b in edges_list:
        cyc = (a, b) in cycle_edges
        edges.append({
            "from": a, "to": b,
            "color": {"color": "rgba(255,90,90,0.65)" if cyc else "rgba(120,150,220,0.32)",
                      "highlight": "#9fc0ff"},
            "width": 2.2 if cyc else 1.4,
        })

    tmpl = """
<script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>
<div id="net" style="width:100%;height:620px;border-radius:14px;background:__BG__;
     box-shadow:inset 0 0 120px rgba(0,0,0,0.6);"></div>
<script>
  const nodes = new vis.DataSet(__NODES__);
  const edges = new vis.DataSet(__EDGES__);
  const options = {
    nodes: { scaling:{min:14,max:46,label:{enabled:true,min:12,max:20}} },
    edges: { smooth:{enabled:true,type:"continuous"},
             arrows:{to:{enabled:true,scaleFactor:0.5}} },
    physics: { solver:"forceAtlas2Based",
               forceAtlas2Based:{gravitationalConstant:-55,springLength:130,springConstant:0.05},
               stabilization:{iterations:260} },
    interaction: { hover:true, dragView:true, zoomView:true, dragNodes:true,
                   tooltipDelay:120, navigationButtons:true, keyboard:false }
  };
  new vis.Network(document.getElementById("net"), {nodes, edges}, options);
</script>
"""
    return (tmpl.replace("__NODES__", json.dumps(nodes, ensure_ascii=False))
                .replace("__EDGES__", json.dumps(edges, ensure_ascii=False))
                .replace("__BG__", _BG))


def render_graph():
    st.title("🕸 의존성 맵")
    if not st.session_state.selected_project:
        st.warning("⚠️ 먼저 홈에서 프로젝트를 선택해주세요!")
        return
    st.success(f"선택된 프로젝트: **{st.session_state.selected_project}**")
    st.caption("드래그로 이동 · 휠로 확대/축소 · 노드 hover 시 코드 요약. "
               "빨강=순환 의존성, 빨강 테두리=고아(미사용 빈). 화살표=의존 방향.")

    model = st.session_state.get("ast_model")
    findings = st.session_state.get("ast_findings")
    if model is None or findings is None or st.button("그래프 생성/갱신"):
        with st.spinner("파싱 + 그래프 구성 중..."):
            model = build_model(_project_path())
            findings = run_all_detectors(model)
        st.session_state.ast_model = model
        st.session_state.ast_findings = findings

    nodes_list, edges_list = depgraph.build_graph(model)
    cycles = depgraph.find_cycles(edges_list)
    orphans = depgraph.find_orphans(model, edges_list)
    c = st.columns(4)
    c[0].metric("노드", len(nodes_list)); c[1].metric("엣지", len(edges_list))
    c[2].metric("순환", len(cycles)); c[3].metric("고아", len(orphans))

    if not nodes_list:
        st.info("표시할 클래스가 없어요.")
        return

    # 범례
    legend = "&nbsp;&nbsp;".join(
        f"<span style='color:{col};font-size:18px'>●</span> {name}"
        for name, col in _PALETTE.items() if name != "other")
    st.markdown(legend, unsafe_allow_html=True)

    components.html(_build_html(model, findings), height=660, scrolling=False)

    # 클릭 대체: 캔버스 아래에서 클래스 선택 → 리팩토링으로 이동
    cols = st.columns([3, 1])
    target = cols[0].selectbox("클래스로 이동", ["—"] + sorted(nodes_list))
    if cols[1].button("🛠 리팩토링으로", use_container_width=True, disabled=target == "—"):
        st.session_state.focus_class = target
        st.session_state.menu = _REFACTOR_MENU
        st.rerun()

    if cycles:
        st.subheader("🔴 순환 의존성")
        for cy in cycles:
            st.code(" → ".join(cy))
    if orphans:
        st.subheader("⚪ 고아(미사용 빈 후보)")
        st.write(", ".join(sorted(orphans)))
