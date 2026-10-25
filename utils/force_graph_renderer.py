"""
ForceGraph2D Renderer for FHIR R4 Bundles
Directly integrates Vasco Asturiano's force-graph / react-force-graph engine:
- Monochrome (#ffffff / #000000) clinical cluster visualization
- Patient at the core radiating outward to Encounters, Conditions, Observations, and Meds
- 1-hop interactive neighborhood highlighting on hover/click
- Animated directional link particles visualizing FHIR pointer resolution
- Interactive live Node Inspector showing raw JSON, inbound & outbound reference links
- Embedded offline bundle (no CDN dependency, zero latency)
"""

import json
import os
from typing import Dict, Any
from utils.graph_crawler import build_fhir_graph

# Read local minified bundle once
BUNDLE_PATH = os.path.join(os.path.dirname(__file__), "force-graph.min.js")
FORCE_GRAPH_JS = ""
if os.path.exists(BUNDLE_PATH):
    with open(BUNDLE_PATH, "r", encoding="utf-8") as f:
        FORCE_GRAPH_JS = f.read()

def render_force_graph_html(bundle: Dict[str, Any], height: int = 680) -> str:
    """
    Generates a self-contained, offline HTML/JS visualization
    using ForceGraph2D with Patrick Hand typography and a live Node Inspector.
    """
    graph_data = build_fhir_graph(bundle)
    nodes = graph_data["nodes"]
    links = graph_data["links"]

    # Initial selected node: Patient if available, else first node
    initial_id = ""
    for n in nodes:
        if n.get("resourceType") == "Patient":
            initial_id = n.get("id")
            break
    if not initial_id and nodes:
        initial_id = nodes[0].get("id")

    nodes_json = json.dumps(nodes)
    links_json = json.dumps(links)

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>FHIR Care Network ForceGraph2D</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Patrick+Hand&family=JetBrains+Mono&display=swap');

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}

    body {{
      background-color: #ffffff;
      color: #000000;
      font-family: 'Patrick Hand', cursive, sans-serif;
      overflow: hidden;
      width: 100vw;
      height: 100vh;
    }}

    #studio-layout {{
      display: flex;
      width: 100%;
      height: 100%;
      gap: 12px;
      padding: 8px;
    }}

    /* Left: Graph Canvas Container */
    #graph-container {{
      flex: 1.5;
      position: relative;
      border: 2px solid #000000;
      border-radius: 6px;
      background-color: #ffffff;
      overflow: hidden;
      min-height: 500px;
    }}

    #graph-canvas {{
      width: 100%;
      height: 100%;
    }}

    /* Floating Toolbar */
    #toolbar {{
      position: absolute;
      top: 10px;
      left: 10px;
      display: flex;
      gap: 6px;
      background: #ffffff;
      border: 1.5px solid #000000;
      border-radius: 4px;
      padding: 4px 8px;
      z-index: 10;
      box-shadow: 2px 2px 0px rgba(0,0,0,0.1);
    }}

    .tool-btn {{
      background: #ffffff;
      color: #000000;
      border: 1px solid #000000;
      border-radius: 3px;
      font-family: 'Patrick Hand', cursive, sans-serif;
      font-size: 0.95rem;
      font-weight: bold;
      padding: 2px 8px;
      cursor: pointer;
      transition: background 0.15s;
    }}

    .tool-btn:hover {{
      background: #000000;
      color: #ffffff;
    }}

    .tool-btn.active {{
      background: #000000;
      color: #ffffff;
    }}

    /* Legend Overlay */
    #legend {{
      position: absolute;
      bottom: 10px;
      left: 10px;
      background: rgba(255, 255, 255, 0.92);
      border: 1.5px solid #000000;
      border-radius: 4px;
      padding: 6px 10px;
      font-size: 0.9rem;
      z-index: 10;
      line-height: 1.3;
    }}

    /* Right: Interactive Node Inspector Panel */
    #inspector-panel {{
      flex: 1.0;
      border: 2px solid #000000;
      border-radius: 6px;
      background-color: #fafafa;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }}

    #inspector-header {{
      padding: 12px 14px;
      border-bottom: 2px solid #000000;
      background-color: #ffffff;
    }}

    #inspector-title {{
      font-size: 1.35rem;
      font-weight: bold;
      line-height: 1.2;
    }}

    #inspector-sub {{
      font-size: 1.05rem;
      color: #444444;
      margin-top: 2px;
    }}

    #inspector-badge-row {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-top: 6px;
    }}

    .type-badge {{
      display: inline-block;
      border: 1px solid #000000;
      border-radius: 3px;
      padding: 2px 8px;
      font-size: 0.9rem;
      font-family: 'JetBrains Mono', monospace;
      font-weight: bold;
      background: #fafafa;
    }}

    #inspector-body {{
      flex: 1;
      overflow-y: auto;
      padding: 12px 14px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }}

    .section-title {{
      font-size: 1.1rem;
      font-weight: bold;
      border-bottom: 1px solid #000000;
      padding-bottom: 3px;
      margin-bottom: 6px;
    }}

    .ref-chip {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 4px 8px;
      border: 1px solid #000000;
      border-radius: 3px;
      background: #ffffff;
      margin-bottom: 4px;
      font-size: 0.95rem;
      cursor: pointer;
    }}

    .ref-chip:hover {{
      background: #f0f0f0;
    }}

    .ref-chip .rel-label {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.85rem;
      border-right: 1px solid #cccccc;
      padding-right: 6px;
      margin-right: 6px;
    }}

    pre.json-box {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.82rem;
      background: #ffffff;
      color: #000000;
      border: 1px solid #000000;
      border-radius: 3px;
      padding: 8px;
      overflow: auto;
      max-height: 250px;
      white-space: pre-wrap;
      word-break: break-all;
    }}
  </style>
  <script>
    {FORCE_GRAPH_JS}
  </script>
</head>
<body>
  <div id="studio-layout">
    <!-- Left: Canvas Area -->
    <div id="graph-container">
      <div id="toolbar">
        <button class="tool-btn active" id="btn-force" onclick="setMode('none')">Free-Force</button>
        <button class="tool-btn" id="btn-dag-td" onclick="setMode('td')">DAG: Top-Down</button>
        <button class="tool-btn" id="btn-dag-radial" onclick="setMode('radialout')">DAG: Radial</button>
        <button class="tool-btn" onclick="zoomFit()">Zoom to Fit</button>
      </div>

      <div id="graph-canvas"></div>

      <div id="legend">
        <b>Monochrome Clinical Hierarchy:</b><br>
        ● <b>Patient</b> (Solid Core) &nbsp;|&nbsp; ◯ <b>Encounter</b> (Ring) &nbsp;|&nbsp; ⬡ <b>Clinical Records</b>
      </div>
    </div>

    <!-- Right: Active Node Inspector -->
    <div id="inspector-panel">
      <div id="inspector-header">
        <div id="inspector-title">Select a node</div>
        <div id="inspector-sub">Click any node on the graph to inspect</div>
        <div id="inspector-badge-row">
          <span class="type-badge" id="inspector-type">Resource</span>
          <span style="font-family: 'JetBrains Mono', monospace; font-size: 0.85rem;" id="inspector-id">#id</span>
        </div>
      </div>

      <div id="inspector-body">
        <!-- Connected Inbound / Outbound -->
        <div>
          <div class="section-title">Care Network References</div>
          <div id="inbound-list" style="margin-bottom: 8px;">
            <span style="font-size: 0.95rem; color: #666;">Inbound (Referenced By): none</span>
          </div>
          <div id="outbound-list">
            <span style="font-size: 0.95rem; color: #666;">Outbound (Points To): none</span>
          </div>
        </div>

        <!-- Raw JSON -->
        <div>
          <div class="section-title">Resource FHIR Fields</div>
          <pre class="json-box" id="json-viewer">{{}}</pre>
        </div>
      </div>
    </div>
  </div>

  <script>
    const rawNodes = {nodes_json};
    const rawLinks = {links_json};

    const nodesById = {{}};
    rawNodes.forEach(n => {{
      nodesById[n.id] = n;
      n.neighbors = [];
      n.links = [];
    }});

    rawLinks.forEach(link => {{
      const sourceId = typeof link.source === 'object' ? link.source.id : link.source;
      const targetId = typeof link.target === 'object' ? link.target.id : link.target;
      const s = nodesById[sourceId];
      const t = nodesById[targetId];
      if (s && t) {{
        s.neighbors.push(t);
        t.neighbors.push(s);
        s.links.push(link);
        t.links.push(link);
      }}
    }});

    const graphData = {{ nodes: rawNodes, links: rawLinks }};

    let selectedNode = nodesById["{initial_id}"] || rawNodes[0] || null;
    let hoverNode = null;
    const highlightNodes = new Set();
    const highlightLinks = new Set();

    function updateHighlights() {{
      highlightNodes.clear();
      highlightLinks.clear();
      const active = hoverNode || selectedNode;
      if (active) {{
        highlightNodes.add(active);
        if (active.neighbors) active.neighbors.forEach(n => highlightNodes.add(n));
        if (active.links) active.links.forEach(l => highlightLinks.add(l));
      }}
    }}

    // Initialize ForceGraph2D
    const container = document.getElementById('graph-canvas');
    const Graph = ForceGraph()(container)
      .graphData(graphData)
      .backgroundColor('#ffffff')
      .nodeRelSize(7)
      .nodeId('id')
      .nodeVal(n => n.val || 12)
      .d3AlphaDecay(0.02)
      .d3VelocityDecay(0.3)
      .warmupTicks(30)
      .cooldownTicks(200)
      .linkDirectionalParticles(link => highlightLinks.has(link) ? 3 : 1)
      .linkDirectionalParticleWidth(link => highlightLinks.has(link) ? 3 : 1.5)
      .linkDirectionalParticleSpeed(0.005)
      .linkDirectionalArrowLength(6)
      .linkDirectionalArrowRelPos(1)
      .linkWidth(link => highlightLinks.has(link) ? 2.5 : 1.2)
      .linkColor(link => highlightLinks.has(link) ? '#000000' : '#888888')
      .nodeCanvasObject((node, ctx, globalScale) => {{
        const isSelected = (node === selectedNode);
        const isHovered = (node === hoverNode);
        const isHighlighted = highlightNodes.has(node);
        const isDimmed = highlightNodes.size > 0 && !isHighlighted;

        const r = (node.val || 12) * 0.72;

        ctx.save();
        ctx.globalAlpha = isDimmed ? 0.2 : 1.0;

        // Base circle
        ctx.beginPath();
        ctx.arc(node.x, node.y, r, 0, 2 * Math.PI, false);

        if (node.resourceType === 'Patient') {{
          // Solid black core
          ctx.fillStyle = '#000000';
          ctx.fill();
          ctx.lineWidth = isSelected ? 3 : 1.5;
          ctx.strokeStyle = '#000000';
          ctx.stroke();
        }} else if (node.resourceType === 'Encounter') {{
          // Crisp white with thick border
          ctx.fillStyle = isSelected ? '#eaeaea' : '#ffffff';
          ctx.fill();
          ctx.lineWidth = isSelected ? 3 : 2;
          ctx.strokeStyle = '#000000';
          ctx.stroke();
        }} else {{
          // Other resources
          ctx.fillStyle = isSelected ? '#e0e0e0' : (isHovered ? '#f5f5f5' : '#ffffff');
          ctx.fill();
          ctx.lineWidth = isSelected ? 2.5 : 1.5;
          ctx.strokeStyle = '#000000';
          ctx.stroke();
        }}

        // Selection Dashed Halo
        if (isSelected) {{
          ctx.beginPath();
          ctx.arc(node.x, node.y, r + 4, 0, 2 * Math.PI, false);
          ctx.lineWidth = 1.5;
          ctx.setLineDash([3, 3]);
          ctx.strokeStyle = '#000000';
          ctx.stroke();
          ctx.setLineDash([]);
        }}

        // Clinical Display Label (Patrick Hand font)
        const fontSize = Math.max(12 / globalScale, 4.0);
        ctx.font = `bold ${{fontSize}}px 'Patrick Hand', cursive, sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';

        if (node.resourceType === 'Patient') {{
          ctx.fillStyle = '#ffffff';
          // Render brief name inside if scaled, or black text below
          ctx.fillStyle = '#000000';
          ctx.fillText(node.label, node.x, node.y + r + 3);
        }} else {{
          ctx.fillStyle = '#000000';
          ctx.fillText(node.label, node.x, node.y + r + 3);
        }}

        ctx.restore();
      }})
      .onNodeHover(node => {{
        hoverNode = node || null;
        updateHighlights();
        container.style.cursor = node ? 'pointer' : 'default';
      }})
      .onLinkHover(link => {{
        highlightNodes.clear();
        highlightLinks.clear();
        if (link) {{
          highlightLinks.add(link);
          const s = typeof link.source === 'object' ? link.source : nodesById[link.source];
          const t = typeof link.target === 'object' ? link.target : nodesById[link.target];
          if (s) highlightNodes.add(s);
          if (t) highlightNodes.add(t);
        }}
      }})
      .onNodeClick(node => {{
        selectedNode = node;
        updateHighlights();
        renderInspector(node);
        Graph.centerAt(node.x, node.y, 400);
      }})
      .onBackgroundClick(() => {{
        updateHighlights();
      }});

    // Inspector Rendering
    function renderInspector(node) {{
      if (!node) return;
      document.getElementById('inspector-title').innerText = node.label || node.resourceType;
      document.getElementById('inspector-sub').innerText = node.subLabel || 'FHIR Resource';
      document.getElementById('inspector-type').innerText = node.resourceType || 'Resource';
      document.getElementById('inspector-id').innerText = '#' + (node.id || '').substring(0, 8);

      // Inbound references (who points to this node)
      const inbound = [];
      const outbound = [];

      rawLinks.forEach(link => {{
        const sId = typeof link.source === 'object' ? link.source.id : link.source;
        const tId = typeof link.target === 'object' ? link.target.id : link.target;
        if (tId === node.id) {{
          const sNode = nodesById[sId];
          if (sNode) inbound.push({{ rel: link.relation, node: sNode }});
        }}
        if (sId === node.id) {{
          const tNode = nodesById[tId];
          if (tNode) outbound.push({{ rel: link.relation, node: tNode }});
        }}
      }});

      const inDiv = document.getElementById('inbound-list');
      if (inbound.length > 0) {{
        inDiv.innerHTML = '<b>Referenced By (' + inbound.length + '):</b><br>' +
          inbound.map(item => `
            <div class="ref-chip" onclick="selectNodeById('${{item.node.id}}')">
              <span><span class="rel-label">${{item.rel}}</span>${{item.node.label}}</span>
              <span style="font-family: 'JetBrains Mono', monospace; font-size: 0.8rem;">[${{item.node.resourceType}}]</span>
            </div>
          `).join('');
      }} else {{
        inDiv.innerHTML = '<span style="font-size: 0.95rem; color: #666;">Inbound (Referenced By): None (Direct Leaf)</span>';
      }}

      const outDiv = document.getElementById('outbound-list');
      if (outbound.length > 0) {{
        outDiv.innerHTML = '<b>Points To (' + outbound.length + '):</b><br>' +
          outbound.map(item => `
            <div class="ref-chip" onclick="selectNodeById('${{item.node.id}}')">
              <span><span class="rel-label">${{item.rel}}</span>${{item.node.label}}</span>
              <span style="font-family: 'JetBrains Mono', monospace; font-size: 0.8rem;">[${{item.node.resourceType}}]</span>
            </div>
          `).join('');
      }} else {{
        outDiv.innerHTML = '<span style="font-size: 0.95rem; color: #666;">Outbound (Points To): None (Central Anchor)</span>';
      }}

      // JSON fields
      document.getElementById('json-viewer').innerText = JSON.stringify(node.data || {{}}, null, 2);
    }}

    function selectNodeById(id) {{
      const n = nodesById[id];
      if (n) {{
        selectedNode = n;
        updateHighlights();
        renderInspector(n);
        Graph.centerAt(n.x, n.y, 400);
      }}
    }}

    // Toolbar mode controls
    function setMode(mode) {{
      document.querySelectorAll('.tool-btn').forEach(b => b.classList.remove('active'));
      if (mode === 'none') {{
        document.getElementById('btn-force').classList.add('active');
        Graph.dagMode(null);
      }} else if (mode === 'td') {{
        document.getElementById('btn-dag-td').classList.add('active');
        Graph.dagMode('td');
      }} else if (mode === 'radialout') {{
        document.getElementById('btn-dag-radial').classList.add('active');
        Graph.dagMode('radialout');
      }}
      Graph.d3ReheatSimulation();
    }}

    function zoomFit() {{
      Graph.zoomToFit(400, 30);
    }}

    // Initial render
    updateHighlights();
    if (selectedNode) {{
      renderInspector(selectedNode);
    }}
    setTimeout(() => {{
      zoomFit();
    }}, 400);
  </script>
</body>
</html>"""
    return html
