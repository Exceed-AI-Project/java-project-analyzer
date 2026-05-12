import json
from data.dummy_data import _DUMMY_CLASSES, _DUMMY_CALL_GRAPH

_GRAPH_COLORS = {
    "controller": "#4e9af1",
    "service":    "#f1c44e",
    "repository": "#4ef17a",
    "model":      "#f17a4e",
}


def _class_group(class_name: str) -> str:
    name = class_name.lower()
    if "controller" in name:
        return "controller"
    if "service" in name:
        return "service"
    if "repository" in name:
        return "repository"
    return "model"


def _build_graph_html(
    focus_class: str | None = None,
    graph_type: str = "클래스 의존성 그래프",
) -> str:
    """vis.js 기반 의존성 그래프 HTML 생성
    # TODO: NetworkX + Pyvis 연결
    """
    if graph_type == "패키지 의존성 그래프":
        node_dicts = [
            {
                "id": grp, "label": f"com.example\n.{grp}",
                "color": {"background": _GRAPH_COLORS[grp], "border": "#555555"},
                "font": {"color": "#ffffff"}, "shape": "hexagon", "size": 26,
            }
            for grp in ("controller", "service", "repository", "model")
        ]
        edge_dicts = [
            {"from": "controller", "to": "service",    "arrows": "to", "color": {"color": "#888888"}},
            {"from": "service",    "to": "repository", "arrows": "to", "color": {"color": "#888888"}},
        ]
    else:
        node_dicts = []
        for c in _DUMMY_CLASSES:
            group    = _class_group(c["클래스명"])
            is_focus = c["클래스명"] == focus_class
            node_dicts.append({
                "id":    c["클래스명"],
                "label": c["클래스명"],
                "color": {
                    "background": "#ff6b6b" if is_focus else _GRAPH_COLORS.get(group, "#aaaaaa"),
                    "border":     "#ffffff" if is_focus else "#555555",
                },
                "font":  {"color": "#ffffff"},
                "shape": "box" if c["타입"] == "Interface" else "ellipse",
                "size":  20 if is_focus else 14,
            })

        seen: set[tuple[str, str]] = set()
        edge_dicts = []
        for call in _DUMMY_CALL_GRAPH:
            key = (call["호출자 클래스"], call["피호출 클래스"])
            if key not in seen:
                seen.add(key)
                edge_dicts.append({
                    "from":   call["호출자 클래스"],
                    "to":     call["피호출 클래스"],
                    "arrows": "to",
                    "color":  {"color": "#888888"},
                })

    nodes_js = json.dumps(node_dicts)
    edges_js = json.dumps(edge_dicts)

    return f"""<!DOCTYPE html>
<html>
<head>
  <script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>
  <style>
    body  {{ margin: 0; background: #0e1117; }}
    #graph {{ width: 100%; height: 100%; }}
  </style>
</head>
<body>
  <div id="graph"></div>
  <script>
    var nodes = new vis.DataSet({nodes_js});
    var edges = new vis.DataSet({edges_js});
    var options = {{
      physics: {{ stabilization: {{ iterations: 150 }} }},
      interaction: {{ hover: true, tooltipDelay: 200 }},
    }};
    new vis.Network(document.getElementById("graph"), {{ nodes: nodes, edges: edges }}, options);
  </script>
</body>
</html>"""
