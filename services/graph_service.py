import json
from pathlib import Path

STEREOTYPE_COLORS = {
    "controller": "#4A90D9",
    "service":    "#F5A623",
    "repository": "#7ED321",
    "entity":     "#9B59B6",
    "config":     "#95A5A6",
    "dto":        "#1ABC9C",
    "component":  "#E67E22",
    "unknown":    "#BDC3C7",
}

def _load_ast(project_name: str) -> dict:
    path = Path("ast_results") / f"{project_name}.json"
    if not path.exists():
        return {"classes": [], "call_edges": []}
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def _build_graph_html(focus_class: str = None, project_name: str = "AINotebook") -> str:
    data = _load_ast(project_name)
    classes = data.get("classes", [])
    edges = data.get("call_edges", [])

    nodes_js = []
    for cls in classes:
        name = cls["name"]
        stereotype = cls.get("stereotype", "unknown")
        color = STEREOTYPE_COLORS.get(stereotype, "#BDC3C7")
        is_focus = name == focus_class
        border = "#E74C3C" if is_focus else "#2C3E50"
        size = 30 if is_focus else 20
        nodes_js.append(
            f'{{id: "{name}", label: "{name}", color: {{background: "{color}", border: "{border}"}}, size: {size}}}'
        )

    seen = set()
    edges_js = []
    for e in edges:
        caller = e["caller_class"]
        callee = e["callee_class"]
        key = (caller, callee)
        if key not in seen:
            seen.add(key)
            edges_js.append(f'{{from: "{caller}", to: "{callee}", arrows: "to"}}')

    nodes_str = ",\n".join(nodes_js)
    edges_str = ",\n".join(edges_js)

    return f"""<!DOCTYPE html>
<html>
<head>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/vis/4.21.0/vis.min.js"></script>
  <link href="https://cdnjs.cloudflare.com/ajax/libs/vis/4.21.0/vis.min.css" rel="stylesheet"/>
  <style>body{{margin:0;}} #graph{{width:100%;height:400px;}}</style>
</head>
<body>
  <div id="graph"></div>
  <script>
    var nodes = new vis.DataSet([{nodes_str}]);
    var edges = new vis.DataSet([{edges_str}]);
    var container = document.getElementById('graph');
    var network = new vis.Network(container, {{nodes, edges}}, {{
      physics: {{stabilization: false}},
      edges: {{smooth: true}}
    }});
  </script>
</body>
</html>"""