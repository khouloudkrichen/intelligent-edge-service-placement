# ═══════════════════════════════════════════════════════
# api/server.py — FastAPI + WebSocket + routes
# ═══════════════════════════════════════════════════════

import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from api.dashboard         import DASHBOARD_HTML
from core.nodes            import state, init_nodes
from services.neo4j_writer import neo4j_driver, NEO4J_DB, clear_all

app = FastAPI(title="IBN Voice Dashboard")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ws_clients: list[WebSocket] = []

# ── Événements partagés avec voice_loop ─────────────────
import threading
recording_event = threading.Event()
stop_event      = threading.Event()
text_event      = threading.Event()
pending_text    = {"value": ""}


async def broadcast(message: dict):
    dead = []
    for ws in ws_clients:
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    for d in dead:
        ws_clients.remove(d)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    ws_clients.append(ws)
    await ws.send_json({"type": "init", "state": state})
    try:
        while True:
            raw  = await ws.receive_text()
            data = json.loads(raw)
            cmd  = data.get("cmd", "")
            if cmd == "start_recording":
                print("\n🖥️  Dashboard → start_recording")
                recording_event.set()
            elif cmd == "stop_recording":
                print("🖥️  Dashboard → stop_recording")
                stop_event.set()
            elif cmd == "submit_text":
                pending_text["value"] = data.get("text", "").strip()
                if pending_text["value"]:
                    print(f"\n🖥️  Dashboard → submit_text : {pending_text['value']}")
                    text_event.set()
            elif cmd == "reset":
                init_nodes(reset_load=True)
                state["placements"] = []
                state["stats"]      = {"total": 0, "success": 0, "fail": 0}
                clear_all()
                await broadcast({"type": "init", "state": state})
                print("🔄 Reset effectué")
    except WebSocketDisconnect:
        if ws in ws_clients:
            ws_clients.remove(ws)


@app.get("/")
async def dashboard():
    return HTMLResponse(DASHBOARD_HTML)


@app.get("/state")
async def get_state():
    return state


@app.get("/graph")
async def get_graph():
    live = {n["id"]: n for n in state["nodes"]}
    all_ibn = []
    for nd in state["nodes"]:
        lv = live.get(nd["id"], {})
        cc, cm, cd, cb = lv.get("cpu",0), lv.get("mem",0), lv.get("disk",0), lv.get("bw",0)
        uc, um, ud, ub = lv.get("cpu_used",0), lv.get("mem_used",0), lv.get("disk_used",0), lv.get("bw_used",0)
        all_ibn.append({
            "id": nd["id"], "label": nd["id"], "type": "ibnnode",
            "node_type": nd["type"], "active": lv.get("active", False),
            "lat": lv.get("lat", 0), "lat_min": lv.get("lat_min", 0), "lat_max": lv.get("lat_max", 0),
            "intents": lv.get("intents", []),
            "cap_cpu": cc, "used_cpu": uc, "pct_cpu": round(uc/cc*100) if cc else 0,
            "cap_mem": cm, "used_mem": um, "pct_mem": round(um/cm*100) if cm else 0,
            "cap_disk": cd, "used_disk": ud,
            "cap_bw":  cb, "used_bw":  ub, "pct_bw":  round(ub/cb*100) if cb else 0,
        })
    nodes_map = {n["id"]: n for n in all_ibn}
    edges = []
    if neo4j_driver:
        try:
            cypher = (
                "MATCH (i:Intention)-[r:PLACED_ON]->(n:IbnNode) "
                "RETURN i.id AS iid, i.description AS desc, "
                "i.success AS success, i.services AS services, "
                "i.voice_text AS voice_text, i.timestamp AS ts, "
                "n.id AS nid, r.latency AS lat, r.grouped AS grouped"
            )
            with neo4j_driver.session(database=NEO4J_DB) as session:
                result = session.run(cypher)
                for rec in result:
                    iid, nid = rec["iid"], rec["nid"]
                    if iid not in nodes_map:
                        nodes_map[iid] = {
                            "id": iid, "label": iid, "type": "intention",
                            "desc": rec["desc"], "success": rec["success"],
                            "services": rec["services"],
                            "voice_text": rec["voice_text"], "ts": rec["ts"]
                        }
                    edges.append({"from": iid, "to": nid, "lat": rec["lat"], "grouped": rec["grouped"]})
        except Exception as e:
            print(f"Graph Neo4j error: {e}")
    return JSONResponse({"nodes": list(nodes_map.values()), "edges": edges})
