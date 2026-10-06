# ═══════════════════════════════════════════════════════
# api/dashboard.py — HTML du dashboard temps réel
# ═══════════════════════════════════════════════════════

from config import SERVER_PORT

DASHBOARD_HTML = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>IBN Voice Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Outfit:wght@400;500;600&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'Outfit', sans-serif;background:var(--bg);color:var(--t);height:100vh;overflow:hidden;transition:background .3s}}
body::before{{content:'';position:fixed;inset:0;background-image:linear-gradient(var(--b) 1px,transparent 1px),linear-gradient(90deg,var(--b) 1px,transparent 1px);background-size:40px 40px;opacity:.5;pointer-events:none}}
.topbar{{display:flex;align-items:center;gap:12px;padding:10px 24px;background:var(--s);border-bottom:1px solid var(--b);position:relative;z-index:10;flex-shrink:0}}
.logo{{display:flex;align-items:center;gap:10px}}
.logo-icon{{width:34px;height:34px;background:linear-gradient(135deg,#0ea5e9,#0369a1);border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:16px;box-shadow:0 0 16px rgba(14,165,233,.3)}}
.logo-title{{font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:13px;font-weight:700;color:var(--a)}}
.logo-sub{{font-size:10px;color:var(--t3)}}
.topbar-right{{margin-left:auto;display:flex;align-items:center;gap:10px}}
.mic-btn{{font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:11px;font-weight:600;padding:7px 16px;border-radius:4px;border:1px solid var(--a);background:rgba(56,189,248,.1);color:var(--a);cursor:pointer;transition:all .25s;display:flex;align-items:center;gap:6px}}
.mic-btn:hover{{background:rgba(56,189,248,.2)}}
.mic-btn.recording{{background:rgba(248,113,113,.15);color:#fca5a5;border-color:rgba(248,113,113,.5);animation:micPulse 1s ease-in-out infinite}}
.mic-btn.processing{{background:rgba(251,191,36,.1);color:#fbbf24;border-color:rgba(251,191,36,.4);cursor:not-allowed}}
.reset-btn{{font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:10px;padding:6px 12px;border-radius:4px;border:1px solid var(--b);background:transparent;color:var(--t3);cursor:pointer;transition:all .2s}}
.reset-btn:hover{{border-color:var(--a);color:var(--a)}}
.theme-btn{{background:var(--s2);border:1px solid var(--b);border-radius:6px;padding:6px 10px;cursor:pointer;font-size:14px;transition:all .15s}}
.theme-btn:hover{{border-color:var(--a)}}
@keyframes micPulse{{0%,100%{{box-shadow:0 0 0 0 rgba(248,113,113,.3)}}50%{{box-shadow:0 0 0 8px rgba(248,113,113,0)}}}}
.main{{display:flex;height:calc(100vh - 53px);gap:0;position:relative;z-index:1}}
.left{{flex:1;display:flex;flex-direction:column;gap:10px;padding:14px;overflow-y:auto}}
.left::-webkit-scrollbar{{width:3px}}
.left::-webkit-scrollbar-thumb{{background:var(--b);border-radius:2px}}
.card{{background:var(--s);border:1px solid var(--b);border-radius:6px;padding:14px;transition:background .3s,border .3s}}
.card-title{{font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:10px;font-weight:600;color:var(--a);letter-spacing:.1em;text-transform:uppercase;margin-bottom:10px;display:flex;align-items:center;gap:7px}}
.card-title::before{{content:'';width:6px;height:6px;border-radius:50%;background:var(--a);box-shadow:0 0 6px var(--a);flex-shrink:0}}
.transcript-box{{background:var(--s2);border:1px solid var(--b);border-radius:4px;padding:12px;font-size:13px;color:var(--t);min-height:48px;font-style:italic;line-height:1.6;transition:border .3s}}
.transcript-box.recording{{border-color:rgba(248,113,113,.5);animation:borderPulse 1.5s ease-in-out infinite}}
.transcript-box.processing{{border-color:rgba(251,191,36,.4)}}
@keyframes borderPulse{{0%,100%{{border-color:rgba(248,113,113,.2)}}50%{{border-color:rgba(248,113,113,.7)}}}}
.text-input-wrap,.text-input,.send-btn{{display:none!important}}
.helper-txt{{margin-top:6px;font-size:10px;color:var(--t3);font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace}}
.intent-node{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:6px}}
.info-box{{background:var(--s2);border:1px solid var(--b);border-radius:4px;padding:10px}}
.info-label{{font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:9px;color:var(--t3);letter-spacing:.1em;text-transform:uppercase;margin-bottom:4px}}
.info-val{{font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:16px;font-weight:700;color:var(--a)}}
.info-sub{{font-size:10px;color:var(--t3);margin-top:2px}}
.kpi-row{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}}
.kpi{{background:var(--s2);border:1px solid var(--b);border-radius:4px;padding:10px}}
.kpi-val{{font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:22px;font-weight:700;color:var(--t)}}
.kpi-lbl{{font-size:9px;color:var(--t3);letter-spacing:.08em;text-transform:uppercase;margin-top:2px}}
.kpi-sub{{font-size:9px;color:var(--t2);margin-top:4px}}
.right{{width:360px;min-width:300px;display:flex;flex-direction:column;gap:10px;padding:14px;border-left:1px solid var(--b);overflow-y:auto}}
.right::-webkit-scrollbar{{width:3px}}
.right::-webkit-scrollbar-thumb{{background:var(--b);border-radius:2px}}
.node-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:6px}}
.node-card{{background:var(--s2);border:1px solid var(--b);border-radius:4px;padding:9px;transition:all .3s;border-left:3px solid var(--b);position:relative}}
.node-card.gw{{border-left-color:#f59e0b}}
.node-card.cp{{border-left-color:var(--a)}}
.node-card.active{{border-color:rgba(34,211,238,.4);box-shadow:0 0 10px rgba(34,211,238,.1)}}
.node-card.latest-command-node{{border-color:var(--a);box-shadow:0 0 18px rgba(34,211,238,.8);animation:pulseLatestCommand 1.4s ease-in-out infinite}}
.node-card.latest-placement{{border-color:var(--a);box-shadow:0 0 18px rgba(34,211,238,.8);animation:pulseLatestCommand 1.4s ease-in-out infinite}}
.node-card.hover-placement{{border-color:#f59e0b;box-shadow:0 0 18px rgba(245,158,11,.6)}}
@keyframes pulseLatestCommand{{0%{{box-shadow:0 0 8px rgba(34,211,238,.35)}}50%{{box-shadow:0 0 24px rgba(34,211,238,.95)}}100%{{box-shadow:0 0 8px rgba(34,211,238,.35)}}}}
.latest-label{{display:inline-flex;align-items:center;gap:4px;margin:0 0 6px;padding:2px 6px;border-radius:999px;border:1px solid rgba(34,211,238,.45);background:rgba(34,211,238,.12);color:var(--a);font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:8px;font-weight:700;text-transform:uppercase;letter-spacing:.04em}}
.latest-label span{{color:var(--t2);font-weight:600;text-transform:none;letter-spacing:0}}
.node-intents-pop{{display:none;margin-top:7px;padding:6px;border-radius:4px;border:1px solid var(--b);background:var(--s);color:var(--t2);font-size:9px;line-height:1.45}}
.node-card:hover .node-intents-pop{{display:block}}
.node-id{{font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:11px;font-weight:700;color:var(--a);margin-bottom:6px;display:flex;justify-content:space-between;align-items:center}}
.node-badge{{font-size:8px;padding:1px 5px;border-radius:2px;font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace}}
.node-badge.gw{{background:rgba(245,158,11,.15);color:#f59e0b}}
.node-badge.cp{{background:rgba(56,189,248,.12);color:var(--a)}}
.res-row{{display:flex;align-items:center;gap:5px;margin-bottom:3px}}
.res-lbl{{font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:8px;color:var(--t3);width:26px;flex-shrink:0}}
.bar{{flex:1;height:4px;background:var(--s);border-radius:2px;overflow:hidden}}
.bar-fill{{height:100%;border-radius:2px;transition:width .5s ease,background .3s}}
.res-pct{{font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:8px;color:var(--t2);width:24px;text-align:right}}
.log-list{{display:flex;flex-direction:column;gap:4px;max-height:280px;overflow-y:auto}}
.log-list::-webkit-scrollbar{{width:3px}}
.log-item{{display:flex;align-items:flex-start;gap:7px;padding:7px 9px;border-radius:3px;border-left:2px solid;animation:logIn .25s ease both}}
@keyframes logIn{{from{{opacity:0;transform:translateX(-6px)}}to{{opacity:1;transform:translateX(0)}}}}
.log-item.ok{{background:rgba(34,211,238,.05);border-color:#22d3ee}}
.log-item.fail{{background:rgba(248,113,113,.05);border-color:#f87171}}
.log-item[data-node-id]{{cursor:pointer}}
.log-item[data-node-id]:hover{{background:rgba(245,158,11,.08);box-shadow:0 0 0 1px rgba(245,158,11,.22) inset}}
.log-item.latest-log{{box-shadow:0 0 0 1px rgba(34,211,238,.28) inset}}
.log-icon{{font-size:11px;flex-shrink:0}}
.log-content{{flex:1;min-width:0}}
.log-id{{font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:10px;font-weight:700;color:var(--a)}}
.log-desc{{font-size:11px;color:var(--t2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.log-detail{{font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:9px;color:#22d3ee;margin-top:1px}}
.log-fail-txt{{font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:9px;color:#f87171;margin-top:1px}}
.log-time-metric{{font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:9px;color:#fbbf24;margin-top:2px}}
.log-command-time{{font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:9px;color:var(--a);margin-top:3px}}
.log-time{{font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:8px;color:var(--t3);flex-shrink:0}}
.log-empty{{font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:11px;color:var(--t3);padding:12px;text-align:center}}
.tabs{{display:flex;gap:4px;margin-left:20px}}
.tab{{font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:11px;font-weight:600;padding:6px 14px;border-radius:4px;border:1px solid var(--b);background:transparent;color:var(--t3);cursor:pointer;transition:all .2s;text-decoration:none}}
.tab:hover{{border-color:var(--a);color:var(--a)}}
.tab.active{{background:rgba(56,189,248,.15);border-color:var(--a);color:var(--a)}}
.view{{display:none}}
.view.active{{display:flex}}
#graphView{{flex-direction:column;padding:14px;gap:10px;height:calc(100vh - 53px);overflow:hidden}}
.graph-container{{flex:1;background:var(--graph-bg, var(--s2));border:1px solid var(--b);border-radius:8px;overflow:hidden;position:relative;min-height:0}}
.graph-canvas{{width:100%;height:100%;display:block}}
.graph-legend{{display:flex;gap:12px;padding:8px 16px;background:var(--s);border:1px solid var(--b);border-radius:6px;align-items:center;flex-wrap:wrap}}
.legend-item{{display:flex;align-items:center;gap:5px;font-size:10px;color:var(--t2)}}
.legend-dot{{width:10px;height:10px;border-radius:50%;flex-shrink:0}}
.graph-stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}}
.graph-tooltip{{position:absolute;background:var(--s);border:1px solid var(--a);border-radius:4px;padding:8px 12px;font-size:11px;color:var(--t);pointer-events:none;display:none;z-index:100;max-width:220px;font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace}}
#graphView .card-title{{font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:10px;font-weight:600;color:var(--a);letter-spacing:.1em;text-transform:uppercase}}
</style>
<link rel="stylesheet" href="/static/css/theme.css">
</head>
<body>
<div class="topbar">
  <div class="logo">
    <div class="logo-icon">🎤</div>
    <div>
      <div class="logo-title">IBN · Voice Dashboard</div>
      <div class="logo-sub">Placement temps réel · Whisper · Dataset 4</div>
    </div>
  </div>
  <div class="tabs">
    <button class="tab active" id="tabDash" onclick="switchTab('dashboard')">📊 Dashboard</button>
    <button class="tab" id="tabGraph" onclick="switchTab('graph')">🕸️ Graphe Neo4j</button>
    <button class="tab" id="tabChatbot" onclick="window.location.href='/chatbot'">💬 Chatbot</button>
    <a class="tab" id="tabAnalytics" href="/analytics">📈 Analytics</a>
  </div>
  <div class="topbar-right">
    <button class="mic-btn" id="micBtn" onclick="toggleRecording()">🎤 Parler</button>
    <button class="reset-btn" onclick="resetSystem()">↺ Reset</button>
    <button class="theme-btn" onclick="toggleTheme()">🌙</button>
  </div>
</div>

<div id="dashView" class="main view active">
  <div class="left">
    <div class="card">
      <div class="card-title">Reconnaissance Vocale</div>

      <div class="transcript-box" id="transcriptBox">
        En attente de commande vocale... Clique sur 🎤 Parler.
      </div>

      <div class="helper-txt">Utilise uniquement le microphone pour envoyer une intention.</div>

      <div class="intent-node" id="intentNode" style="display:none">
        <div class="info-box">
          <div class="info-label">Intention détectée</div>
          <div class="info-val" id="intentVal">—</div>
          <div class="info-sub" id="intentDesc">—</div>
        </div>
        <div class="info-box">
          <div class="info-label">Nœud sélectionné</div>
          <div class="info-val" id="nodeVal">—</div>
          <div class="info-sub" id="nodeLatency">—</div>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-title">Statistiques</div>
      <div class="kpi-row">
        <div class="kpi"><div class="kpi-val" id="kpiTotal" style="color:#7dd3fc">0</div><div class="kpi-lbl">Total</div></div>
        <div class="kpi"><div class="kpi-val" id="kpiSuccess" style="color:#22d3ee">0</div><div class="kpi-lbl">Succès</div></div>
        <div class="kpi"><div class="kpi-val" id="kpiFail" style="color:#f87171">0</div><div class="kpi-lbl">Échecs</div></div>
        <div class="kpi"><div class="kpi-val" id="kpiPlacementLatest" style="color:#fbbf24">--</div><div class="kpi-lbl">Processing Time</div><div class="kpi-sub" id="kpiPlacementAvg">Average: --</div></div>
      </div>
    </div>

    <div class="card">
      <div class="card-title">État des Nœuds en Temps Réel</div>
      <div class="node-grid" id="nodeGrid"></div>
    </div>
  </div>

  <div class="right">
    <div class="card" style="flex:1">
      <div class="card-title">Journal de Placement</div>
      <div class="log-list" id="logList">
        <div class="log-empty">Aucun placement — clique sur 🎤 Parler pour commencer</div>
      </div>
    </div>
  </div>
</div>

<!-- ═══ VUE GRAPHE NEO4J ═══ -->
<div id="graphView" class="view graph-wrapper" style="flex-direction:column;padding:12px;gap:10px;height:calc(100vh - 53px);overflow:hidden">
  <div class="graph-stats" style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;flex-shrink:0">
    <div class="stats-box top-card neo-box" style="background:var(--card);border:1px solid var(--border);border-radius:6px;padding:10px 14px">
      <div style="font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:22px;font-weight:700;color:#7dd3fc" id="gTotalNodes">0</div>
      <div style="font-size:9px;color:var(--t3);letter-spacing:.08em;text-transform:uppercase;margin-top:2px">Intentions</div>
    </div>
    <div class="stats-box top-card neo-box" style="background:var(--card);border:1px solid var(--border);border-radius:6px;padding:10px 14px">
      <div style="font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:22px;font-weight:700;color:#22d3ee" id="gTotalIbn">0</div>
      <div style="font-size:9px;color:var(--t3);letter-spacing:.08em;text-transform:uppercase;margin-top:2px">Nœuds IBN</div>
    </div>
    <div class="stats-box top-card neo-box" style="background:var(--card);border:1px solid var(--border);border-radius:6px;padding:10px 14px">
      <div style="font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:22px;font-weight:700;color:#a78bfa" id="gTotalEdges">0</div>
      <div style="font-size:9px;color:var(--t3);letter-spacing:.08em;text-transform:uppercase;margin-top:2px">Placements</div>
    </div>
  </div>

  <div class="legend-bar graph-panel neo-box" style="display:flex;gap:10px;padding:7px 14px;background:var(--card);border:1px solid var(--border);border-radius:6px;align-items:center;flex-wrap:wrap;flex-shrink:0">
    <span style="font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:9px;color:var(--t3);text-transform:uppercase;letter-spacing:.1em">Légende</span>
    <div class="legend-item"><div style="width:22px;height:12px;border-radius:3px;background:#38bdf8"></div>Intention</div>
    <div class="legend-item"><div class="legend-dot" style="background:#22d3ee"></div>Computing node</div>
    <div class="legend-item"><div style="width:12px;height:12px;background:#a78bfa;border-radius:2px"></div>Gateway</div>
    <div class="legend-item"><div class="legend-dot" style="background:#f59e0b"></div>Loaded (&gt;50%)</div>
    <div class="legend-item"><div class="legend-dot" style="background:#f87171"></div>Saturated (&gt;80%)</div>
    <div class="legend-item"><div style="width:20px;height:2px;background:#22d3ee;border-radius:1px"></div>PLACED_ON</div>
    <div class="legend-item" style="color:var(--t2);font-size:10px">Clic = détails</div>
    <button class="refresh-panel neo-box" onclick="loadGraph()" style="margin-left:auto;font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:10px;padding:5px 14px;border-radius:4px;border:1px solid var(--a);background:var(--input);color:var(--a);cursor:pointer">↻ Rafraîchir</button>
  </div>

  <div class="graph-body graph-wrapper" style="flex:1;display:flex;gap:10px;min-height:0">
    <div class="graph-panel cy-container neo-box" style="flex:1;background:var(--graph-bg, var(--card));border:1px solid var(--border);border-radius:8px;overflow:hidden;position:relative;min-height:0">
      <canvas id="graphCanvas" style="width:100%;height:100%;display:block"></canvas>
      <div id="graphHint" style="position:absolute;bottom:12px;left:50%;transform:translateX(-50%);font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:10px;color:var(--t3);pointer-events:none">
        🖱️ Clique sur un nœud pour voir ses détails
      </div>
    </div>

    <div id="nodePanel" class="details-panel right-panel sidebar-box graph-panel neo-box" style="width:280px;flex-shrink:0;background:var(--card);border:1px solid var(--border);border-radius:8px;overflow-y:auto;transition:all .3s">
      <div id="panelEmpty" style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:12px;padding:20px;text-align:center">
        <div style="font-size:36px;opacity:.3">🕸️</div>
        <div style="font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:10px;color:var(--t3);line-height:1.6">
          Clique sur un nœud<br>pour afficher<br>ses détails
        </div>
      </div>
      <div id="panelContent" style="display:none;padding:16px"></div>
    </div>
  </div>
</div>

<script>
const ws = new WebSocket('ws://localhost:{SERVER_PORT}/ws');
let isRecording = false;
const micBtn = document.getElementById('micBtn');
const box = document.getElementById('transcriptBox');
const textInput = {{ addEventListener: () => {{}} }};
const sendTextBtn = {{ disabled: false, textContent: '' }};
let latestCommandId = '';
let latestCommandText = '';
let latestCommandIntentIds = [];
let latestCommandPlacements = [];
let latestHighlightedNodeIds = [];
let latestCommandTotalTimeMs = 0;
let latestCommandTiming = {{}};
let hoverPlacedNodeIds = [];

function toggleRecording() {{
  if (isRecording) {{
    ws.send(JSON.stringify({{cmd: 'stop_recording'}}));
    isRecording = false;
    micBtn.className = 'mic-btn processing';
    micBtn.textContent = '⏳ Traitement...';
    micBtn.disabled = true;
    box.className = 'transcript-box processing';
    box.textContent = '⏳ Transcription en cours...';
  }} else {{
    ws.send(JSON.stringify({{cmd: 'start_recording'}}));
    isRecording = true;
    micBtn.className = 'mic-btn recording';
    micBtn.textContent = '⏹ Stop';
    micBtn.disabled = false;
  }}
}}

function sendTextCommand() {{
  return;
  const text = textInput.value.trim();
  if (!text) return;

  ws.send(JSON.stringify({{
    cmd: 'submit_text',
    text: text
  }}));

  sendTextBtn.disabled = true;
  sendTextBtn.textContent = '⏳ Analyse...';
  box.className = 'transcript-box processing';
  box.textContent = '⏳ Analyse du texte en cours...';
}}

function resetSystem() {{
  ws.send(JSON.stringify({{cmd: 'reset'}}));
  document.getElementById('intentNode').style.display = 'none';
  clearLatestCommandHighlight();
  box.className = 'transcript-box';
  box.textContent = 'Système remis à zéro. Clique sur 🎤 Parler pour recommencer.';
  setIdle();
}}

function setIdle() {{
  isRecording = false;
  micBtn.className = 'mic-btn';
  micBtn.textContent = '🎤 Parler';
  micBtn.disabled = false;

  sendTextBtn.textContent = '✍️ Envoyer';

  box.className = 'transcript-box';
}}

textInput.addEventListener('keydown', (e) => {{
  if (e.key === 'Enter' && e.ctrlKey) {{
    e.preventDefault();
    sendTextCommand();
  }}
}});

function nodeIdsFromPlacement(p) {{
  const ids = [];
  if (p?.node) ids.push(p.node);
  if (Array.isArray(p?.nodes)) ids.push(...p.nodes.filter(Boolean));
  return [...new Set(ids.map(id => String(id)))];
}}

function placementNodeEntries(p) {{
  if (Array.isArray(p?.nodes) && p.nodes.length) {{
    return p.nodes
      .map((nodeId, index) => ({{
        nodeId: nodeId ? String(nodeId) : '',
        service: Array.isArray(p.services) ? p.services[index] : ''
      }}))
      .filter(item => item.nodeId);
  }}
  return p?.node ? [{{nodeId: String(p.node), service: ''}}] : [];
}}

function commandKeyFromPlacement(p) {{
  return p?.command_id || (p?.text ? `text:${{p.text}}` : `fallback:${{p?.time || ''}}:${{p?.id || ''}}`);
}}

function updateLatestCommandFromHistory(placements, msg = null) {{
  const list = placements || [];
  const first = list[0];
  if (!first) {{
    latestCommandId = '';
    latestCommandText = '';
    latestCommandIntentIds = [];
    latestCommandPlacements = [];
    latestHighlightedNodeIds = [];
    latestCommandTotalTimeMs = 0;
    latestCommandTiming = {{}};
    return;
  }}

  const latestKey = msg?.command_id || commandKeyFromPlacement(first);
  const commandGroup = [];
  for (const p of list) {{
    if (commandKeyFromPlacement(p) !== latestKey) break;
    commandGroup.push(p);
  }}

  latestCommandId = latestKey;
  latestCommandText = msg?.command_text || first.text || '';
  latestCommandIntentIds = commandGroup.map(p => p.id).filter(Boolean);
  latestCommandPlacements = [];
  latestCommandTotalTimeMs = msg?.total_time_ms || first.command_total_time_ms || 0;
  latestCommandTiming = msg?.timing || first.timing || {{}};

  commandGroup.forEach(p => {{
    if (!p?.success) return;
    const entries = placementNodeEntries(p);
    const grouped = p.grouped || entries.length <= 1;
    entries.forEach((entry, index) => {{
      latestCommandPlacements.push({{
        command_id: latestCommandId,
        intention_id: p.id || '',
        intention_description: p.desc || '',
        node_id: entry.nodeId,
        services: grouped ? (p.services || []) : [entry.service || (p.services || [])[index]].filter(Boolean),
        latency: p.lat,
        time_ms: p.time_ms || p.placement_time_ms || 0,
        command_total_time_ms: p.command_total_time_ms || latestCommandTotalTimeMs,
        timing: p.timing || latestCommandTiming,
        status: (p.status || p.source || 'PLACED').toString().toUpperCase()
      }});
    }});
  }});

  latestHighlightedNodeIds = [...new Set(latestCommandPlacements.map(p => p.node_id).filter(Boolean))];
}}

function latestDetailsForNode(nodeId) {{
  return latestCommandPlacements.filter(p => p.node_id === nodeId);
}}

function clearLatestCommandHighlight() {{
  latestCommandId = '';
  latestCommandText = '';
  latestCommandIntentIds = [];
  latestCommandPlacements = [];
  latestHighlightedNodeIds = [];
  latestCommandTotalTimeMs = 0;
  latestCommandTiming = {{}};
  hoverPlacedNodeIds = [];
  applyNodeHighlights();
}}

function setHoveredPlacementNode(nodeIds) {{
  const ids = Array.isArray(nodeIds) ? nodeIds : [nodeIds];
  hoverPlacedNodeIds = ids.filter(Boolean).map(id => String(id));
  applyNodeHighlights();
}}

function applyNodeHighlights() {{
  document.querySelectorAll('.node-card[data-node-id]').forEach(card => {{
    const id = card.dataset.nodeId;
    card.classList.toggle('latest-command-node', latestHighlightedNodeIds.includes(id));
    card.classList.toggle('hover-placement', hoverPlacedNodeIds.includes(id));
  }});
}}

ws.onmessage = (e) => {{
  const msg = JSON.parse(e.data);

  if (msg.type === 'init') {{
    updateLatestCommandFromHistory(msg.state.placements);
    renderNodes(msg.state.nodes);
    renderLog(msg.state.placements);
    updateStats(msg.state.stats);
  }}

  if (msg.type === 'listening') {{
    isRecording = true;
    micBtn.className = 'mic-btn recording';
    micBtn.textContent = '⏹ Stop';
    micBtn.disabled = false;
    box.className = 'transcript-box recording';
    box.textContent = '🎤 Écoute en cours... Parle maintenant.';
  }}

  if (msg.type === 'recording_stopped') {{
    micBtn.className = 'mic-btn processing';
    micBtn.textContent = '⏳ Traitement...';
    micBtn.disabled = true;
    box.className = 'transcript-box processing';
    box.textContent = '⏳ Transcription et analyse...';
  }}

  if (msg.type === 'transcript') {{
    box.className = 'transcript-box';
    box.textContent = msg.summary || msg.text;
  }}

  if (msg.type === 'placement' || msg.type === 'placement_result') {{
    setIdle();
    document.getElementById('intentNode').style.display = 'grid';
    document.getElementById('intentVal').textContent = msg.intent;
    document.getElementById('nodeVal').textContent = msg.node ? msg.node.toUpperCase() : '—';
    document.getElementById('nodeLatency').textContent = `${{msg.lat}} ms`;
    document.getElementById('intentDesc').textContent = msg.services.join(', ');
    updateLatestCommandFromHistory(msg.placements, msg);
    renderNodes(msg.nodes);
    renderLog(msg.placements);
    updateStats(msg.stats);
    textInput.value = '';
  }}

  if (msg.type === 'no_intent') {{
    setIdle();
    clearLatestCommandHighlight();
    box.textContent = msg.text
      ? `❓ "${{msg.text}}" — Aucune intention IBN détectée`
      : '❌ Aucun audio valide détecté. Réessayez.';
  }}

  if (msg.type === 'placement_failed') {{
    setIdle();
    clearLatestCommandHighlight();
    document.getElementById('nodeVal').textContent = 'ÉCHEC';
    document.getElementById('nodeLatency').textContent = 'Aucun nœud disponible';
    renderNodes(msg.nodes);
    updateStats(msg.stats);
  }}
}};

ws.onclose = () => {{
  setIdle();
  box.textContent = '⚠️ Connexion perdue. Rechargez la page.';
}};

const barColor = p => p>=80?'#f87171':p>=50?'#f59e0b':'#22d3ee';
const pct = (u,c) => c>0?Math.min(100,Math.round(u/c*100)):0;
const escapeHtml = (value = '') => String(value).replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
const formatSeconds = ms => `${{(Number(ms || 0) / 1000).toFixed(3)}} s`;

function renderNodes(nodes) {{
  const grid = document.getElementById('nodeGrid');
  grid.innerHTML = nodes.map(n => {{
    const cpu = pct(n.cpu_used,n.cpu), mem = pct(n.mem_used,n.mem), bw = pct(n.bw_used,n.bw);
    const isGW = n.type==='gateway', lc = n.lat>70?'#f87171':n.lat>50?'#f59e0b':'#22d3ee';
    const nodeLatestDetails = latestDetailsForNode(n.id);
    const isLatest = nodeLatestDetails.length > 0;
    const isHover = hoverPlacedNodeIds.includes(n.id);
    const intents = Array.isArray(n.intents) ? n.intents : [];
    const intentsText = intents.length ? intents.join(', ') : 'Aucune intention placée';
    const latestIntentText = [...new Set(nodeLatestDetails.map(d => d.intention_id).filter(Boolean))].join(', ');
    const latestMeta = latestIntentText ? `${{latestIntentText}} · ${{latestCommandId}}` : latestCommandId;
    const latestLabel = isLatest ? `<div class="latest-label">Latest command <span>${{escapeHtml(latestMeta)}}</span></div>` : '';
    const latestDetailsHtml = isLatest
      ? `<div class="node-intents-pop"><strong>Latest command on ${{escapeHtml(n.id.toUpperCase())}}</strong><br>${{
          nodeLatestDetails.map(d => `
            <div style="margin-top:5px">
              <b>${{escapeHtml(d.intention_id)}}</b> · ${{escapeHtml(d.status)}} · ${{d.latency ?? '?'}}ms<br>
              <span>${{escapeHtml((d.services || []).join(', ') || 'services n/a')}}</span><br>
              <span style="color:#fbbf24">⚡ Placement: ${{d.time_ms ? formatSeconds(d.time_ms) : '?'}}</span><br>
              <span style="color:var(--a)">Total: ${{d.command_total_time_ms ? formatSeconds(d.command_total_time_ms) : '?'}}</span>
            </div>`).join('')
        }}</div>`
      : `<div class="node-intents-pop"><strong>Intentions placées</strong><br>${{escapeHtml(intentsText)}}</div>`;
    return `<div class="node-card ${{isGW?'gw':'cp'}} ${{n.active?'active':''}} ${{isLatest?'latest-command-node':''}} ${{isHover?'hover-placement':''}}" data-node-id="${{n.id}}" title="Intentions: ${{escapeHtml(intentsText)}}">
      ${{latestLabel}}
      <div class="node-id">${{n.id.toUpperCase()}}<span class="node-badge ${{isGW?'gw':'cp'}}">${{isGW?'GW':'CP'}}</span></div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:3px;margin-bottom:6px">
        ${{[['CPU',n.cpu_used,n.cpu,'#38bdf8'],['MEM',n.mem_used,n.mem+'G','#818cf8'],
           ['DISK',n.disk_used,n.disk+'G','#34d399'],['BW',n.bw_used,n.bw+'M','#f59e0b']]
          .map(([l,u,c,col])=>`<div style="font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:8px;background:var(--s);border-radius:3px;padding:3px 5px">
            <div style="color:var(--t3);font-size:7px">${{l}}</div>
            <div style="color:${{col}};font-weight:700">${{u}}/${{c}}</div></div>`).join('')}}
      </div>
      ${{[['CPU',cpu],['MEM',mem],['BW',bw]].map(([l,v])=>`
        <div class="res-row"><span class="res-lbl">${{l}}</span>
        <div class="bar"><div class="bar-fill" style="width:${{v}}%;background:${{barColor(v)}}"></div></div>
        <span class="res-pct">${{v}}%</span></div>`).join('')}}
      <div style="font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:8px;margin-top:5px;display:flex;justify-content:space-between">
        <span style="color:${{lc}}">⏱ ${{n.lat}}ms</span>
        <span style="color:${{n.active?'#22d3ee':'var(--t3)'}}">${{intents.length}} intent${{intents.length!==1?'s':''}}</span>
      </div>
      ${{latestDetailsHtml}}
    </div>`;
  }}).join('');
  applyNodeHighlights();
}}

function renderLog(placements) {{
  const list = document.getElementById('logList');
  updatePlacementTimeStats(placements);

  if (!placements || !placements.length) {{
    list.innerHTML = '<div class="log-empty">Aucun placement — clique sur 🎤 Parler pour commencer</div>';
    return;
  }}

  list.innerHTML = placements.map((p, index) => {{
    const nodeIds = nodeIdsFromPlacement(p);
    const nodeId = nodeIds[0] || '';
    const commandKey = commandKeyFromPlacement(p);
    const isLatestCommand = commandKeyFromPlacement(p) === latestCommandId;
    const hoverIds = isLatestCommand ? latestHighlightedNodeIds : nodeIds;
    const nodeAttr = nodeId ? ` data-node-id="${{nodeId}}" data-node-ids="${{hoverIds.join(',')}}"` : '';
    const latestClass = isLatestCommand ? ' latest-log' : '';
    const targetText = nodeIds.length > 1 ? nodeIds.map(id => id.toUpperCase()).join(', ') : (p.node || p.nodes?.[0] || '?').toUpperCase();
    const intentTime = p.time_ms || p.placement_time_ms;
    const showCommandTotal = index === 0 || commandKeyFromPlacement(placements[index - 1]) !== commandKey;
    const commandTotal = p.command_total_time_ms;
    const timing = p.timing || {{}};
    const classificationTime = p.classification_time_ms || timing.classification_time_ms;
    const algorithmTime = p.placement_algorithm_time_ms || timing.placement_algorithm_time_ms;
    const neo4jTime = p.neo4j_time_ms || timing.neo4j_time_ms;
    const websocketTime = p.websocket_prepare_time_ms || timing.websocket_prepare_time_ms;
    return `
    <div class="log-item ${{p.success ? 'ok' : 'fail'}}${{latestClass}}"${{nodeAttr}}>
      <div class="log-icon">${{p.success ? '✅' : '❌'}}</div>
      <div class="log-content">
        <div class="log-id">${{p.id}}</div>
        <div class="log-desc">${{p.desc}}</div>
        ${{p.success
          ? `<div class="log-detail">${{(p.status || p.source || 'PLACED').toUpperCase()}} → ${{targetText}} (${{p.lat ?? '?'}}ms)</div>`
          : `<div class="log-fail-txt">ÉCHEC — ${{(p.source || 'failed').toUpperCase()}}</div>`
        }}
        ${{intentTime ? `<div class="log-time-metric">⚡ Per intention: ${{formatSeconds(intentTime)}}</div>` : ''}}
        ${{showCommandTotal && commandTotal ? `<div class="log-command-time">Total processing time: ${{formatSeconds(commandTotal)}}</div>` : ''}}
        ${{showCommandTotal && (classificationTime || algorithmTime || neo4jTime || websocketTime) ? `<div class="log-command-time">Classification: ${{formatSeconds(classificationTime)}} · Placement: ${{formatSeconds(algorithmTime)}} · Neo4j: ${{formatSeconds(neo4jTime)}} · WS prep: ${{formatSeconds(websocketTime)}}</div>` : ''}}
      </div>
      <div class="log-time">${{p.time || ''}}</div>
    </div>`;
  }}).join('');

  list.querySelectorAll('.log-item[data-node-id]').forEach(item => {{
    item.addEventListener('mouseenter', () => setHoveredPlacementNode((item.dataset.nodeIds || item.dataset.nodeId).split(',')));
    item.addEventListener('mouseleave', () => setHoveredPlacementNode([]));
  }});
}}

function updateStats(s) {{
  document.getElementById('kpiTotal').textContent = s.total;
  document.getElementById('kpiSuccess').textContent = s.success;
  document.getElementById('kpiFail').textContent = s.fail;
}}

function updatePlacementTimeStats(placements) {{
  const latestEl = document.getElementById('kpiPlacementLatest');
  const avgEl = document.getElementById('kpiPlacementAvg');
  const seen = new Set();
  const commandTimes = [];
  (placements || []).forEach(p => {{
    const total = p.command_total_time_ms;
    if (!total) return;
    const key = commandKeyFromPlacement(p);
    if (seen.has(key)) return;
    seen.add(key);
    commandTimes.push(Number(total));
  }});
  if (!commandTimes.length) {{
    latestEl.textContent = '--';
    avgEl.textContent = 'Average processing: --';
    return;
  }}
  latestEl.textContent = `⚡ ${{formatSeconds(commandTimes[0])}}`;
  const avg = commandTimes.reduce((a,b) => a + b, 0) / commandTimes.length;
  avgEl.textContent = `Average processing: ${{formatSeconds(avg)}}`;
}}

function applyTheme(theme) {{
  const dark = theme === 'dark';
  document.body.classList.toggle('dark', dark);
  localStorage.setItem('ibn-theme', dark ? 'dark' : 'light');
  document.querySelector('.theme-btn').textContent = dark ? '☀️' : '🌙';
}}

function toggleTheme() {{
  const next = document.body.classList.contains('dark') ? 'light' : 'dark';
  applyTheme(next);
}}

applyTheme(localStorage.getItem('ibn-theme') || 'dark');

function switchTab(tab) {{
  document.getElementById('dashView').classList.toggle('active', tab === 'dashboard');
  document.getElementById('graphView').classList.toggle('active', tab === 'graph');
  document.getElementById('tabDash').classList.toggle('active', tab === 'dashboard');
  document.getElementById('tabGraph').classList.toggle('active', tab === 'graph');
  if (tab === 'graph') loadGraph();
}}

if (window.location.hash === '#graph') {{
  switchTab('graph');
}}

let graphData = {{ nodes: [], edges: [] }};
let animFrame = null;
let dragging  = null;
let hovering  = null;
let selected  = null;

async function loadGraph() {{
  try {{
    const r = await fetch('/graph');
    const d = await r.json();
    if (d.error) {{ console.warn('Graph error:', d.error); return; }}

    const oldPos = {{}};
    graphData.nodes.forEach(n => {{ oldPos[n.id] = {{x: n.x, y: n.y, vx: n.vx, vy: n.vy}}; }});
    graphData = d;
    graphData.nodes.forEach(n => {{ if (oldPos[n.id]) Object.assign(n, oldPos[n.id]); }});

    document.getElementById('gTotalNodes').textContent = d.nodes.filter(n=>n.type==='intention').length;
    document.getElementById('gTotalIbn').textContent = d.nodes.filter(n=>n.type==='ibnnode').length;
    document.getElementById('gTotalEdges').textContent = d.edges.length;

    initGraphPositions();
    if (animFrame) cancelAnimationFrame(animFrame);
    runSimulation();
  }} catch(e) {{
    console.error('loadGraph error', e);
  }}
}}

function initGraphPositions() {{
  const canvas = document.getElementById('graphCanvas');
  const W = canvas.offsetWidth || 800;
  const H = canvas.offsetHeight || 500;

  const ibn = graphData.nodes.filter(n => n.type === 'ibnnode');
  const ints = graphData.nodes.filter(n => n.type === 'intention');

  ibn.forEach((n, i) => {{
    if (!n.x) {{
      const angle = (i / Math.max(ibn.length,1)) * Math.PI * 2;
      n.x = W/2 + Math.cos(angle) * Math.min(W,H)*0.28;
      n.y = H/2 + Math.sin(angle) * Math.min(W,H)*0.28;
      n.vx = 0; n.vy = 0;
    }}
  }});

  ints.forEach((n, i) => {{
    if (!n.x) {{
      const angle = (i / Math.max(ints.length,1)) * Math.PI * 2;
      n.x = W/2 + Math.cos(angle) * Math.min(W,H)*0.44;
      n.y = H/2 + Math.sin(angle) * Math.min(W,H)*0.44;
      n.vx = 0; n.vy = 0;
    }}
  }});
}}

function showPanel(n) {{
  const empty = document.getElementById('panelEmpty');
  const pcontent = document.getElementById('panelContent');
  document.getElementById('graphHint').style.display = n ? 'none' : 'block';

  if (!n) {{
    empty.style.display = 'flex';
    pcontent.style.display = 'none';
    return;
  }}

  empty.style.display = 'none';
  pcontent.style.display = 'block';

  if (n.type === 'ibnnode') {{
    const isGW = n.node_type === 'gateway';
    const typeCol = isGW ? '#f59e0b' : '#38bdf8';
    const typeIcon = isGW ? '🔶' : '🔵';
    const statCol = n.active ? '#22d3ee' : '#475569';
    const statTxt = n.active ? '● ACTIF' : '○ INACTIF';
    const pMax = Math.max(n.pct_cpu||0, n.pct_mem||0, n.pct_bw||0);
    const loadCol = pMax>=80?'#f87171':pMax>=50?'#f59e0b':'#22d3ee';

    function resRow(label, used, cap, pct, col) {{
      const w = Math.min(pct, 100);
      const c = pct>=80?'#f87171':pct>=50?'#f59e0b':col;
      return `<div style="margin-bottom:10px">
        <div style="display:flex;justify-content:space-between;margin-bottom:4px">
          <span style="font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:9px;color:#94a3b8">${{label}}</span>
          <span style="font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:9px;color:${{c}}">${{used}}/${{cap}} (${{pct}}%)</span>
        </div>
        <div style="height:5px;background:var(--s);border-radius:3px;overflow:hidden">
          <div style="height:100%;width:${{w}}%;background:${{c}};border-radius:3px;transition:width .4s"></div>
        </div>
      </div>`;
    }}

    pcontent.innerHTML = `
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px;padding-bottom:12px;border-bottom:1px solid var(--b)">
        <div style="width:36px;height:36px;border-radius:8px;background:rgba(56,189,248,.1);border:1px solid ${{typeCol}}33;display:flex;align-items:center;justify-content:center;font-size:18px">${{typeIcon}}</div>
        <div>
          <div style="font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:15px;font-weight:700;color:${{typeCol}}">${{n.id.toUpperCase()}}</div>
          <div style="font-size:10px;color:var(--t2)">${{isGW ? 'Gateway Node' : 'Computing Node'}}</div>
        </div>
      </div>

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:14px">
        <div style="background:var(--s2);border-radius:6px;padding:8px;border:1px solid var(--b)">
          <div style="font-size:9px;color:var(--t2);margin-bottom:3px;font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace">STATUT</div>
          <div style="font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:11px;font-weight:600;color:${{statCol}}">${{statTxt}}</div>
        </div>
        <div style="background:var(--s2);border-radius:6px;padding:8px;border:1px solid var(--b)">
          <div style="font-size:9px;color:var(--t2);margin-bottom:3px;font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace">LATENCE</div>
          <div style="font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:11px;font-weight:600;color:#38bdf8">${{n.lat}}ms</div>
          <div style="font-size:8px;color:var(--t3)">${{n.lat_min}}–${{n.lat_max}}ms</div>
        </div>
      </div>

      <div style="background:var(--s2);border-radius:6px;padding:10px;border:1px solid var(--b);margin-bottom:14px">
        <div style="display:flex;justify-content:space-between;margin-bottom:6px">
          <span style="font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:9px;color:var(--t2);text-transform:uppercase;letter-spacing:.08em">Charge globale</span>
          <span style="font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:11px;font-weight:700;color:${{loadCol}}">${{pMax}}%</span>
        </div>
        <div style="height:6px;background:var(--s);border-radius:3px;overflow:hidden">
          <div style="height:100%;width:${{pMax}}%;background:${{loadCol}};border-radius:3px;box-shadow:0 0 6px ${{loadCol}}66"></div>
        </div>
      </div>

      <div style="background:var(--s2);border-radius:6px;padding:10px;border:1px solid var(--b);margin-bottom:14px">
        <div style="font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:9px;color:var(--t2);text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px">Ressources</div>
        ${{resRow('CPU', n.used_cpu, n.cap_cpu+' cores', n.pct_cpu, '#38bdf8')}}
        ${{resRow('MEM', n.used_mem+'G', n.cap_mem+'G', n.pct_mem, '#818cf8')}}
        ${{resRow('BW', n.used_bw+'M', n.cap_bw+'M', n.pct_bw, '#f59e0b')}}
        <div style="display:flex;justify-content:space-between;margin-top:6px">
          <span style="font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:9px;color:var(--t2)">DISK</span>
          <span style="font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:9px;color:#34d399">${{n.used_disk}}G / ${{n.cap_disk}}G</span>
        </div>
      </div>

      <div style="background:var(--s2);border-radius:6px;padding:10px;border:1px solid var(--b)">
        <div style="font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:9px;color:var(--t2);text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px">
          Intentions placées (${{n.intents.length}})
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:5px">
          ${{n.intents.length
            ? n.intents.map(i=>`<span style="background:rgba(56,189,248,.12);color:#38bdf8;padding:3px 8px;border-radius:4px;font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:10px;border:1px solid rgba(56,189,248,.2)">${{i}}</span>`).join('')
            : '<span style="color:var(--t3);font-size:11px">Aucune intention</span>'
          }}
        </div>
      </div>`;
  }} else {{
    const sc = n.success ? '#22d3ee' : '#f87171';
    const icon = n.success ? '✅' : '❌';
    const timing = n.timing || {{}};
    const placementTime = n.placement_time_ms ? `⚡ Placement: ${{formatSeconds(n.placement_time_ms)}}` : '—';
    const commandTime = n.command_total_time_ms ? `Total processing: ${{formatSeconds(n.command_total_time_ms)}}` : '';
    const classificationTime = n.classification_time_ms || timing.classification_time_ms;
    const algorithmTime = n.placement_algorithm_time_ms || timing.placement_algorithm_time_ms;
    const neo4jTime = n.neo4j_time_ms || timing.neo4j_time_ms;
    const websocketTime = n.websocket_prepare_time_ms || timing.websocket_prepare_time_ms;
    pcontent.innerHTML = `
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px;padding-bottom:12px;border-bottom:1px solid var(--b)">
        <div style="width:36px;height:36px;border-radius:8px;background:rgba(56,189,248,.1);border:1px solid rgba(56,189,248,.2);display:flex;align-items:center;justify-content:center;font-size:18px">🎯</div>
        <div>
          <div style="font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:15px;font-weight:700;color:#38bdf8">${{n.id.toUpperCase()}}</div>
          <div style="font-size:10px;color:${{sc}}">${{icon}} ${{n.success ? 'Placée avec succès' : 'Placement échoué'}}</div>
        </div>
      </div>

      <div style="background:var(--s2);border-radius:6px;padding:10px;border:1px solid var(--b);margin-bottom:10px">
        <div style="font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:9px;color:var(--t2);margin-bottom:6px;text-transform:uppercase;letter-spacing:.08em">Description</div>
        <div style="font-size:11px;color:var(--t);line-height:1.6">${{n.desc || '—'}}</div>
      </div>

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px">
        <div style="background:var(--s2);border-radius:6px;padding:8px;border:1px solid var(--b)">
          <div style="font-size:9px;color:var(--t2);margin-bottom:3px;font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace">SERVICES</div>
          <div style="font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:11px;color:#a78bfa">${{n.services || '—'}}</div>
        </div>
        <div style="background:var(--s2);border-radius:6px;padding:8px;border:1px solid var(--b)">
          <div style="font-size:9px;color:var(--t2);margin-bottom:3px;font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace">TIMESTAMP</div>
          <div style="font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:11px;color:#38bdf8">${{n.ts || '—'}}</div>
        </div>
      </div>

      <div style="background:var(--s2);border-radius:6px;padding:10px;border:1px solid var(--b);margin-bottom:10px">
        <div style="font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:9px;color:var(--t2);margin-bottom:6px;text-transform:uppercase;letter-spacing:.08em">Processing Time</div>
        <div style="font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:12px;color:#fbbf24">${{placementTime}}</div>
        <div style="font-size:9px;color:var(--t3);margin-top:3px">${{commandTime}}</div>
        <div style="font-size:9px;color:var(--t3);margin-top:3px">Classification: ${{formatSeconds(classificationTime)}} · Algorithm: ${{formatSeconds(algorithmTime)}} · Neo4j: ${{formatSeconds(neo4jTime)}} · WS prep: ${{formatSeconds(websocketTime)}}</div>
      </div>

      <div style="background:var(--s2);border-radius:6px;padding:10px;border:1px solid var(--b)">
        <div style="font-family:'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', 'JetBrains Mono', monospace;font-size:9px;color:var(--t2);margin-bottom:6px;text-transform:uppercase;letter-spacing:.08em">Commande vocale</div>
        <div style="font-size:10px;color:var(--t2);font-style:italic;line-height:1.5">"${{(n.voice_text||'').slice(0,120)}}${{(n.voice_text||'').length>120?'...':''}}"</div>
      </div>`;
  }}
}}

function drawCircle(ctx, x, y, radius, fill, stroke, lineWidth) {{
  ctx.beginPath();
  ctx.arc(x, y, radius, 0, Math.PI * 2);
  ctx.fillStyle = fill;
  ctx.fill();
  ctx.strokeStyle = stroke;
  ctx.lineWidth = lineWidth;
  ctx.stroke();
}}

function drawSquare(ctx, x, y, size, fill, stroke, lineWidth) {{
  const left = x - size / 2;
  const top = y - size / 2;
  ctx.beginPath();
  ctx.rect(left, top, size, size);
  ctx.fillStyle = fill;
  ctx.fill();
  ctx.strokeStyle = stroke;
  ctx.lineWidth = lineWidth;
  ctx.stroke();
}}

function drawRectangle(ctx, x, y, width, height, fill, stroke, lineWidth) {{
  const left = x - width / 2;
  const top = y - height / 2;
  ctx.beginPath();
  if (ctx.roundRect) {{
    ctx.roundRect(left, top, width, height, 7);
  }} else {{
    ctx.rect(left, top, width, height);
  }}
  ctx.fillStyle = fill;
  ctx.fill();
  ctx.strokeStyle = stroke;
  ctx.lineWidth = lineWidth;
  ctx.stroke();
}}

function graphNodeKind(n) {{
  const id = (n.id || '').toLowerCase();
  if (n.type === 'intention' || id.startsWith('i')) return 'intention';
  if (n.node_type === 'gateway' || n.type === 'gateway' || id.startsWith('g')) return 'gateway';
  if (n.node_type === 'computing' || n.type === 'computing' || id.startsWith('n')) return 'computing';
  return n.type === 'ibnnode' ? 'computing' : 'intention';
}}

function runSimulation() {{
  const canvas = document.getElementById('graphCanvas');
  canvas.width = canvas.offsetWidth;
  canvas.height = canvas.offsetHeight;
  const ctx = canvas.getContext('2d');
  const cssVar = name => getComputedStyle(document.body).getPropertyValue(name).trim();
  const nodeMap = {{}};
  graphData.nodes.forEach(n => nodeMap[n.id] = n);

  function step() {{
    const W = canvas.width, H = canvas.height;

    graphData.nodes.forEach(a => {{
      graphData.nodes.forEach(b => {{
        if (a === b) return;
        const dx = a.x - b.x, dy = a.y - b.y;
        const dist = Math.sqrt(dx*dx + dy*dy) || 1;
        const force = 5000 / (dist * dist);
        a.vx += (dx/dist) * force;
        a.vy += (dy/dist) * force;
      }});
    }});

    graphData.edges.forEach(e => {{
      const a = nodeMap[e.from], b = nodeMap[e.to];
      if (!a || !b) return;
      const dx = b.x - a.x, dy = b.y - a.y;
      const dist = Math.sqrt(dx*dx + dy*dy) || 1;
      const force = (dist - 150) * 0.04;
      a.vx += (dx/dist)*force; a.vy += (dy/dist)*force;
      b.vx -= (dx/dist)*force; b.vy -= (dy/dist)*force;
    }});

    graphData.nodes.forEach(n => {{
      if (n === dragging) return;
      n.vx *= 0.85; n.vy *= 0.85;
      n.x = Math.max(40, Math.min(W-40, n.x + n.vx));
      n.y = Math.max(40, Math.min(H-40, n.y + n.vy));
    }});

    ctx.clearRect(0, 0, W, H);

    ctx.strokeStyle = cssVar('--border');
    ctx.lineWidth = 1;
    for (let x = 0; x < W; x += 40) {{ ctx.beginPath(); ctx.moveTo(x,0); ctx.lineTo(x,H); ctx.stroke(); }}
    for (let y = 0; y < H; y += 40) {{ ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(W,y); ctx.stroke(); }}

    graphData.edges.forEach(e => {{
      const a = nodeMap[e.from], b = nodeMap[e.to];
      if (!a || !b) return;
      ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y);
      ctx.strokeStyle = 'rgba(34,211,238,0.4)'; ctx.lineWidth = 1.5; ctx.stroke();

      const angle = Math.atan2(b.y-a.y, b.x-a.x);
      const ax = b.x - Math.cos(angle)*20, ay = b.y - Math.sin(angle)*20;
      ctx.beginPath();
      ctx.moveTo(ax, ay);
      ctx.lineTo(ax - Math.cos(angle-0.4)*8, ay - Math.sin(angle-0.4)*8);
      ctx.lineTo(ax - Math.cos(angle+0.4)*8, ay - Math.sin(angle+0.4)*8);
      ctx.closePath(); ctx.fillStyle = 'rgba(34,211,238,0.7)'; ctx.fill();

      const mx = (a.x+b.x)/2, my = (a.y+b.y)/2;
      ctx.font = '9px JetBrains Mono'; ctx.fillStyle = cssVar('--muted');
      const edgeLabel = e.placement_time_ms ? `${{e.lat || '?'}}ms · ⚡${{formatSeconds(e.placement_time_ms)}}` : (e.lat ? e.lat+'ms' : '');
      ctx.textAlign = 'center'; ctx.fillText(edgeLabel, mx, my-4);
    }});

    graphData.nodes.forEach(n => {{
      const isHover = n === hovering;
      const isSel = n === selected;
      const kind = graphNodeKind(n);
      let r = 24, fillColor, strokeColor;
      let rectW = 58, rectH = 30, squareSize = 42;

      if (kind === 'computing') {{
        r = 24;
        const pctMax = Math.max(n.pct_cpu||0, n.pct_mem||0, n.pct_bw||0);
        fillColor = pctMax >= 80 ? '#f87171' : pctMax >= 50 ? '#f59e0b' : n.active ? '#22d3ee' : '#475569';
        strokeColor = isSel ? cssVar('--text') : n.active ? cssVar('--border-strong') : cssVar('--border');
      }} else if (kind === 'gateway') {{
        squareSize = 42;
        fillColor = n.active ? '#a78bfa' : '#475569';
        strokeColor = isSel ? cssVar('--text') : cssVar('--border-strong');
      }} else {{
        rectW = Math.max(48, String(n.label || n.id || '').length * 10 + 22);
        rectH = 30;
        fillColor = '#38bdf8';
        strokeColor = isSel ? cssVar('--text') : cssVar('--border-strong');
      }}

      if (isHover || isSel) {{
        ctx.shadowColor = fillColor;
        ctx.shadowBlur = 14;
      }}

      const lineWidth = isSel ? 2.5 : 1;
      const grow = isHover || isSel ? 4 : 0;
      if (kind === 'intention') {{
        drawRectangle(ctx, n.x, n.y, rectW + grow, rectH + grow, fillColor, strokeColor, lineWidth);
      }} else if (kind === 'gateway') {{
        drawSquare(ctx, n.x, n.y, squareSize + grow, fillColor, strokeColor, lineWidth);
      }} else {{
        drawCircle(ctx, n.x, n.y, r + grow / 2, fillColor, strokeColor, lineWidth);
      }}
      ctx.shadowBlur = 0;

      ctx.font = `bold ${{n.type==='ibnnode'?11:10}}px "Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji", 'JetBrains Mono', monospace`;
      ctx.fillStyle = cssVar('--on-accent');
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(n.label, n.x, n.y);

      if (kind === 'computing' || kind === 'gateway') {{
        const badge = kind === 'gateway' ? 'GW' : 'CP';
        const badgeY = n.y + (kind === 'gateway' ? squareSize / 2 : r) + 10;
        ctx.font = '7px JetBrains Mono';
        ctx.fillStyle = cssVar('--muted');
        ctx.fillText(badge, n.x, badgeY);

        const baseY = n.y + (kind === 'gateway' ? squareSize / 2 : r) + 16;
        const bw2 = 36, bh2 = 3, bx2 = n.x - bw2/2, by2 = baseY;
        ctx.fillStyle = cssVar('--border');
        ctx.beginPath();
        if (ctx.roundRect) {{
          ctx.roundRect(bx2,by2,bw2,bh2,2);
        }} else {{
          ctx.rect(bx2,by2,bw2,bh2);
        }}
        ctx.fill();

        const pct2 = Math.max(n.pct_cpu||0, n.pct_mem||0, n.pct_bw||0);
        const barC2 = pct2>=80?'#f87171':pct2>=50?'#f59e0b':'#22d3ee';
        ctx.fillStyle = barC2;
        ctx.beginPath();
        if (ctx.roundRect) {{
          ctx.roundRect(bx2,by2,bw2*(pct2/100),bh2,2);
        }} else {{
          ctx.rect(bx2,by2,bw2*(pct2/100),bh2);
        }}
        ctx.fill();
      }}
    }});

    animFrame = requestAnimationFrame(step);
  }}

  step();
}}

const canvas = document.getElementById('graphCanvas');

canvas.addEventListener('mousemove', e => {{
  const rect = canvas.getBoundingClientRect();
  const mx = e.clientX - rect.left, my = e.clientY - rect.top;
  if (dragging) {{
    dragging.x = mx;
    dragging.y = my;
    return;
  }}
  hovering = graphData.nodes.find(n => Math.hypot(n.x-mx, n.y-my) < 28) || null;
  canvas.style.cursor = hovering ? 'pointer' : 'default';
}});

canvas.addEventListener('mousedown', e => {{
  const rect = canvas.getBoundingClientRect();
  const mx = e.clientX - rect.left, my = e.clientY - rect.top;
  dragging = graphData.nodes.find(n => Math.hypot(n.x-mx, n.y-my) < 28) || null;
}});

canvas.addEventListener('mouseup', e => {{
  const rect = canvas.getBoundingClientRect();
  const mx = e.clientX - rect.left, my = e.clientY - rect.top;
  const clicked = graphData.nodes.find(n => Math.hypot(n.x-mx, n.y-my) < 28);
  if (clicked && clicked === dragging) {{
    selected = (clicked === selected) ? null : clicked;
    showPanel(selected);
  }}
  dragging = null;
}});

canvas.addEventListener('mouseleave', () => {{
  dragging = null;
  hovering = null;
  canvas.style.cursor='default';
}});

window.addEventListener('resize', () => {{
  if (document.getElementById('graphView').classList.contains('active')) {{
    const c = document.getElementById('graphCanvas');
    c.width = c.offsetWidth;
    c.height = c.offsetHeight;
  }}
}});
</script>
</body>
</html>
"""
