import json
import os
import tempfile
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

# components.html() 대신 declare_component 사용 → 노드 클릭 값을 Python으로 반환
_VIS_TMPDIR = os.path.join(tempfile.gettempdir(), "vis_network_component")
os.makedirs(_VIS_TMPDIR, exist_ok=True)
_vis_graph = components.declare_component("vis_graph", path=_VIS_TMPDIR)

# __PALETTE__ / __NODES__ / __EDGES__ / __BG__ 는 _write_graph_html() 에서 치환
_GRAPH_TMPL = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>
<style>
body{margin:0;padding:0;overflow:hidden;background:transparent;}
</style>
</head>
<body>
<div id="net" style="width:100%;height:620px;border-radius:14px;background:__BG__;
     box-shadow:inset 0 0 120px rgba(0,0,0,0.6);"></div>
<div id="tooltip" style="
  display:none; position:fixed; z-index:9999;
  background:#0f1b35; border:1px solid #2e4a7a; border-radius:10px;
  padding:12px 16px; font-family:sans-serif; color:#e7eeff;
  min-width:220px; max-width:320px; pointer-events:none;
  box-shadow:0 4px 24px rgba(0,0,0,0.7);
"></div>
<script>
  window.parent.postMessage(
    {isStreamlitMessage:true,type:"streamlit:componentReady",apiVersion:1}, "*"
  );
  const PALETTE = __PALETTE__;
  const nodes   = new vis.DataSet(__NODES__);
  const edges   = new vis.DataSet(__EDGES__);
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
  const network = new vis.Network(document.getElementById("net"), {nodes, edges}, options);

  /* ── 커스텀 툴팁: hoverNode / blurNode / mousemove ── */
  network.on("hoverNode", function(params) {
    const node = nodes.get(params.node);
    const d    = node.tooltip_data;
    if (!d) return;
    const badgeColor = PALETTE[d.stereotype] || PALETTE["other"];
    const anns = d.annotations.length
      ? d.annotations.map(function(a){ return "@" + a; }).join(", ")
      : "-";
    const warnHtml = d.warn
      ? "<div style='margin-top:6px;font-size:11px;color:#ff8f8f'>⚠ " + d.warn + "</div>"
      : "";
    const tip = document.getElementById("tooltip");
    tip.innerHTML =
      "<div style='display:flex;align-items:center;gap:8px;margin-bottom:6px'>" +
        "<span style='font-weight:bold;font-size:15px;color:#ffffff'>" + d.name + "</span>" +
        "<span style='background:" + badgeColor + ";color:#fff;font-size:10px;" +
             "padding:2px 7px;border-radius:10px;font-weight:600'>" + d.stereotype + "</span>" +
      "</div>" +
      "<div style='font-size:11px;color:#9fb3da;margin-bottom:4px'>annotations: " + anns + "</div>" +
      "<div style='font-size:12px;margin-bottom:4px'>fields " + d.fields + " · methods " + d.methods + "</div>" +
      "<div style='font-size:11px;color:#cdd9f5'>" + d.method_names.join(", ") + "</div>" +
      warnHtml;
    tip.style.display = "block";
  });

  network.on("blurNode", function() {
    document.getElementById("tooltip").style.display = "none";
  });

  document.addEventListener("mousemove", function(e) {
    const tip = document.getElementById("tooltip");
    if (tip.style.display === "block") {
      tip.style.left = (e.clientX + 16) + "px";
      tip.style.top  = (e.clientY - 10) + "px";
    }
  });

  /* ── 노드 클릭 → Python 반환 ── */
  network.on("click", function(params) {
    if (params.nodes.length > 0) {
      window.parent.postMessage({
        isStreamlitMessage: true,
        type: "streamlit:setComponentValue",
        value: params.nodes[0],
        dataType: "json"
      }, "*");
    }
  });
</script>
</body>
</html>"""


def _project_path():
    name = st.session_state.selected_project
    for p in scan_projects():
        if p.name == name:
            return p.path
    return None


def _tooltip_data(ci, fcount, high):
    """노드에 포함할 커스텀 툴팁 데이터 dict 반환 (JS에서 HTML로 렌더링)."""
    warn = f"결함 {fcount}건" + (f" (high {high})" if high else "") if fcount else ""
    return {
        "name":         ci.name,
        "stereotype":   ci.stereotype,
        "annotations":  list(ci.annotations),
        "fields":       len(ci.fields),
        "methods":      len(ci.methods),
        "method_names": [f"{m.name}()" for m in ci.methods[:5]],
        "warn":         warn,
    }


def _write_graph_html(model, findings):
    nodes_list, edges_list = depgraph.build_graph(model)
    cycles  = depgraph.find_cycles(edges_list)
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
        ci     = by_name.get(n)
        stereo = ci.stereotype if ci else "other"
        base   = _PALETTE.get(stereo, _PALETTE["other"])
        flagged = n in cycle_nodes or n in orphans
        border  = "#FF5A5A" if flagged else base
        fnds    = by_class.get(n, [])
        high    = sum(1 for f in fnds if f.severity == "high")
        nodes.append({
            "id": n, "label": n,
            "tooltip_data": _tooltip_data(ci, len(fnds), high) if ci else {},
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

    html = (_GRAPH_TMPL
            .replace("__PALETTE__", json.dumps(_PALETTE))
            .replace("__NODES__",   json.dumps(nodes,  ensure_ascii=False))
            .replace("__EDGES__",   json.dumps(edges,  ensure_ascii=False))
            .replace("__BG__",      _BG))
    with open(os.path.join(_VIS_TMPDIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)


def render_graph():
    st.title("🕸 의존성 맵")
    if not st.session_state.selected_project:
        st.warning("⚠️ 먼저 홈에서 프로젝트를 선택해주세요!")
        return
    st.success(f"선택된 프로젝트: **{st.session_state.selected_project}**")
    st.caption("드래그로 이동 · 휠로 확대/축소 · 노드 hover 시 툴팁 · 클릭 시 아래 드롭다운에 자동 반영. "
               "빨강=순환 의존성, 빨강 테두리=고아(미사용 빈). 화살표=의존 방향.")

    model    = st.session_state.get("ast_model")
    findings = st.session_state.get("ast_findings")
    if model is None or findings is None or st.button("그래프 생성/갱신"):
        with st.spinner("파싱 + 그래프 구성 중..."):
            model    = build_model(_project_path())
            findings = run_all_detectors(model)
        st.session_state.ast_model    = model
        st.session_state.ast_findings = findings
        st.session_state.graph_version = st.session_state.get("graph_version", 0) + 1

    nodes_list, edges_list = depgraph.build_graph(model)
    cycles  = depgraph.find_cycles(edges_list)
    orphans = depgraph.find_orphans(model, edges_list)
    c = st.columns(4)
    c[0].metric("노드", len(nodes_list)); c[1].metric("엣지", len(edges_list))
    c[2].metric("순환", len(cycles));     c[3].metric("고아", len(orphans))

    if not nodes_list:
        st.info("표시할 클래스가 없어요.")
        return

    # 범례
    legend = "&nbsp;&nbsp;".join(
        f"<span style='color:{col};font-size:18px'>●</span> {name}"
        for name, col in _PALETTE.items() if name != "other")
    st.markdown(legend, unsafe_allow_html=True)

    # 그래프 파일 갱신 후 선언형 컴포넌트 렌더링
    # version prop이 바뀔 때만 iframe 재로드 (모델 재빌드 시)
    _write_graph_html(model, findings)
    graph_version = st.session_state.get("graph_version", 0)
    clicked = _vis_graph(key="vis_graph", height=660, version=graph_version, default=None)

    # 새 노드 클릭 → graph_class_select(selectbox) 세션 값 갱신
    all_nodes = ["—"] + sorted(nodes_list)
    if clicked and clicked != st.session_state.get("_last_vis_click"):
        st.session_state["_last_vis_click"] = clicked
        st.session_state["selected_class"]  = clicked
        if clicked in all_nodes:
            st.session_state["graph_class_select"] = clicked

    cols = st.columns([3, 1])
    target = cols[0].selectbox("클래스로 이동", all_nodes, key="graph_class_select", index=0)
    st.session_state["selected_class"] = target  # 수동 선택도 동기화
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
