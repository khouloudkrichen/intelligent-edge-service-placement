# ═══════════════════════════════════════════════════════
# api/server.py — FastAPI + WebSocket + routes
# ═══════════════════════════════════════════════════════

import asyncio
import json
import math
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter, strftime

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from api.dashboard         import DASHBOARD_HTML
from app.models.schemas    import ChatRequest, ChatResponse
from config                import OLLAMA_WARMUP_TIMEOUT_SECONDS
from core.nodes            import state, init_nodes
from services.cache        import get_cache
from services.neo4j_writer import neo4j_driver, NEO4J_DB, clear_all

BASE_DIR = Path(__file__).resolve().parents[1]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await warm_up_services()
    yield


app = FastAPI(title="IBN Voice Dashboard", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

@app.get("/chat/history/{section}")
async def get_chat_history(section: str):
    """Récupère l'historique d'une section."""
    return state["chat_history"].get(section, [])


@app.post("/chat/history/{section}")
async def add_chat_message(section: str, request: Request):
    """Ajoute un message à l'historique d'une section."""
    body = await request.json()
    if section not in state["chat_history"]:
        state["chat_history"][section] = []
    state["chat_history"][section].append({
        "role":    body.get("role", "user"),
        "content": body.get("content", ""),
        "time":    strftime("%H:%M:%S"),
    })
    # Garder max 50 messages par section
    state["chat_history"][section] = state["chat_history"][section][-50:]
    return {"ok": True}


@app.delete("/chat/history/{section}")
async def clear_chat_history(section: str):
    """Efface l'historique d'une section."""
    state["chat_history"][section] = []
    return {"ok": True}

ws_clients: list[WebSocket] = []
CHATBOT_HTML = BASE_DIR / "static" / "chatbot.html"
ANALYTICS_HTML = BASE_DIR / "static" / "analytics.html"
CHATBOT_DATASET = BASE_DIR / "app" / "data" / "industry5_dataset.json"
CHATBOT_STORAGE = BASE_DIR / "app" / "data"
CHATBOT_LOG = BASE_DIR / "logs" / "chat_logs.jsonl"
_chat_services = {"rag": None, "logger": None}
analytics_history: list[dict] = []
_warm_up_complete = False


def _chat_cache_key(language: str, message: str) -> str:
    return f"{language}:{message.strip().casefold()}"


def _chat_response_from_dataset_item(rag_service, item: dict, language: str, question: str, confidence: float = 1.0) -> dict:
    return {
        "answer": rag_service._answer_for_language(item, language),
        "category": item.get("category"),
        "risk": item.get("risk_level"),
        "follow_up": rag_service._follow_up_for_language(item, language),
        "confidence": round(confidence, 2),
        "language": language,
        "suggestions": [],
        "source": "dataset",
        "fallback_used": False,
        "matched_question": question,
    }


def _preload_chatbot_response_cache(rag_service) -> None:
    cache = get_cache()
    loaded = 0
    for item in rag_service.dataset:
        for language, question in (
            ("en", item.get("question_en", "")),
            ("fr", item.get("question_fr", "")),
        ):
            if not question:
                continue
            response_data = _chat_response_from_dataset_item(
                rag_service,
                item,
                language,
                question,
                confidence=1.0,
            )
            cache.set_json("chatbot_responses", _chat_cache_key(language, question), response_data)
            loaded += 1
    print(f"Warm-up: chatbot response cache preloaded ({loaded} dataset questions)")


def get_chat_logger():
    if _chat_services["logger"] is None:
        from app.services.logger_service import ChatLogger

        _chat_services["logger"] = ChatLogger(CHATBOT_LOG)
    return _chat_services["logger"]


def get_chat_services():
    if _chat_services["rag"] is not None:
        return _chat_services["rag"], _chat_services["logger"]
    try:
        from app.services.rag_service import RAGService
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Chatbot dependencies are missing or failed to import: {e}",
        )
    _chat_services["rag"] = RAGService(
        dataset_path=CHATBOT_DATASET,
        storage_dir=CHATBOT_STORAGE,
    )
    _chat_services["logger"] = get_chat_logger()
    return _chat_services["rag"], _chat_services["logger"]


def _warm_up_placement_engine():
    from core.placement import resources_for_intention, select_node
    from data.dataset import intentions

    if not intentions:
        return
    intent = min(intentions, key=lambda item: len(item.get("services", [])))
    required = resources_for_intention(intent)
    select_node(
        required,
        intent["QoS"]["latency"],
        intent.get("services", []),
        intent_desc=intent.get("description", ""),
    )
    print(f"Warm-up: placement engine ready ({intent['id']}, state unchanged)")


def _warm_up_ollama():
    from services.llm import ollama_call

    try:
        ollama_call(
            "Reply OK.",
            max_tokens=1,
            temperature=0.0,
            timeout=OLLAMA_WARMUP_TIMEOUT_SECONDS,
        )
        print("Warm-up: Ollama request completed")
    except Exception as exc:
        print(f"Warm-up: Ollama unavailable, continuing without it ({exc})")


async def warm_up_services():
    global _warm_up_complete
    if _warm_up_complete:
        return
    started = perf_counter()
    print("Warm-up started")
    get_cache()

    try:
        await asyncio.to_thread(get_chat_services)
        rag_service, _ = get_chat_services()
        await asyncio.to_thread(_preload_chatbot_response_cache, rag_service)
        print("Warm-up: RAG dataset, embeddings and FAISS index ready")
    except Exception as exc:
        print(f"Warm-up: RAG service unavailable, lazy retry will remain enabled ({exc})")

    try:
        await asyncio.to_thread(_warm_up_placement_engine)
    except Exception as exc:
        print(f"Warm-up: placement engine failed, continuing ({exc})")

    await asyncio.to_thread(_warm_up_ollama)
    elapsed_ms = round((perf_counter() - started) * 1000, 2)
    _warm_up_complete = True
    print(f"Warm-up completed ({elapsed_ms}ms)")


def _pct(used: float, total: float) -> float:
    return round((used / total * 100), 1) if total else 0.0


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 1) if values else 0.0


def _stddev(values: list[float]) -> float:
    if not values:
        return 0.0
    avg = sum(values) / len(values)
    return math.sqrt(sum((v - avg) ** 2 for v in values) / len(values))


def build_analytics_snapshot() -> dict:
    nodes = state.get("nodes", [])
    placements = state.get("placements", [])
    service_counts = {n["id"]: 0 for n in nodes}
    placement_counts = {n["id"]: 0 for n in nodes}
    latency_samples = {n["id"]: [] for n in nodes}
    placement_time_samples = {n["id"]: [] for n in nodes}
    processing_time_samples = {n["id"]: [] for n in nodes}

    for item in placements:
        if not item.get("success"):
            continue
        services = item.get("services") or []
        item_time = item.get("time_ms") or item.get("placement_time_ms")
        command_time = item.get("command_total_time_ms")
        if item.get("node"):
            node_id = item["node"]
            placement_counts[node_id] = placement_counts.get(node_id, 0) + 1
            service_counts[node_id] = service_counts.get(node_id, 0) + len(services)
            if item.get("lat") is not None:
                latency_samples.setdefault(node_id, []).append(item["lat"])
            if item_time is not None:
                placement_time_samples.setdefault(node_id, []).append(item_time)
            if command_time is not None:
                processing_time_samples.setdefault(node_id, []).append(command_time)
            continue
        for node_id, _service in zip(item.get("nodes") or [], services):
            placement_counts[node_id] = placement_counts.get(node_id, 0) + 1
            service_counts[node_id] = service_counts.get(node_id, 0) + 1
            if item.get("lat") is not None:
                latency_samples.setdefault(node_id, []).append(item["lat"])
            if item_time is not None:
                placement_time_samples.setdefault(node_id, []).append(item_time)
            if command_time is not None:
                processing_time_samples.setdefault(node_id, []).append(command_time)

    node_rows = []
    totals = {"CPU": 0, "MEM": 0, "DISK": 0, "BW": 0}
    used = {"CPU": 0, "MEM": 0, "DISK": 0, "BW": 0}
    free = {"CPU": 0, "MEM": 0, "DISK": 0, "BW": 0}

    for n in nodes:
        cpu_total, mem_total, disk_total, bw_total = n.get("cpu", 0), n.get("mem", 0), n.get("disk", 0), n.get("bw", 0)
        cpu_used, mem_used, disk_used, bw_used = n.get("cpu_used", 0), n.get("mem_used", 0), n.get("disk_used", 0), n.get("bw_used", 0)
        for key, total_val, used_val in [
            ("CPU", cpu_total, cpu_used),
            ("MEM", mem_total, mem_used),
            ("DISK", disk_total, disk_used),
            ("BW", bw_total, bw_used),
        ]:
            totals[key] += total_val
            used[key] += used_val
            free[key] += max(total_val - used_val, 0)

        node_rows.append({
            "id": n["id"],
            "type": n.get("type", ""),
            # CPU usage % = used_cpu / total_cpu * 100
            "cpu_pct": _pct(cpu_used, cpu_total),
            # MEM usage % = used_mem / total_mem * 100
            "mem_pct": _pct(mem_used, mem_total),
            "disk_pct": _pct(disk_used, disk_total),
            "bw_pct": _pct(bw_used, bw_total),
            "cpu_used": cpu_used,
            "cpu_total": cpu_total,
            "mem_used": mem_used,
            "mem_total": mem_total,
            "disk_used": disk_used,
            "disk_total": disk_total,
            "bw_used": bw_used,
            "bw_total": bw_total,
            "placements": placement_counts.get(n["id"], 0),
            "services": service_counts.get(n["id"], 0),
            "avg_latency": _avg(latency_samples.get(n["id"]) or [n.get("lat", 0)]),
            "avg_placement_time_ms": _avg(placement_time_samples.get(n["id"]) or []),
            "avg_processing_time_ms": _avg(processing_time_samples.get(n["id"]) or []),
        })

    cpu_values = [n["cpu_pct"] for n in node_rows]
    # Load balance score = 100 - 2 * standard deviation of node CPU usage.
    # A flatter CPU distribution gives a score closer to 100.
    load_balance_score = round(max(0, min(100, 100 - (_stddev(cpu_values) * 2))), 1)

    cluster_pct = {k: _pct(used[k], totals[k]) for k in totals}
    remaining_pct = {
        k: round(100 - cluster_pct[k], 1)
        for k in cluster_pct
    }
    # Scalability headroom = minimum remaining percentage across CPU, MEM, DISK, BW.
    scalability_headroom = round(min(remaining_pct.values()), 1) if remaining_pct else 0.0

    profiles = {
        # Conservative synthetic service profiles used only for capacity estimation.
        "small": {"CPU": 1, "MEM": 1, "DISK": 1, "BW": 5},
        "medium": {"CPU": 2, "MEM": 2, "DISK": 5, "BW": 20},
        "large": {"CPU": 4, "MEM": 4, "DISK": 10, "BW": 50},
    }
    additional_capacity = {}
    for size, req in profiles.items():
        count = 0
        for n in nodes:
            node_free = {
                "CPU": max(n.get("cpu", 0) - n.get("cpu_used", 0), 0),
                "MEM": max(n.get("mem", 0) - n.get("mem_used", 0), 0),
                "DISK": max(n.get("disk", 0) - n.get("disk_used", 0), 0),
                "BW": max(n.get("bw", 0) - n.get("bw_used", 0), 0),
            }
            count += min(int(node_free[k] // req[k]) for k in req)
        additional_capacity[size] = count

    overloaded_nodes = [
        n["id"] for n in node_rows
        if max(n["cpu_pct"], n["mem_pct"], n["disk_pct"], n["bw_pct"]) >= 85
    ]
    near_saturation = scalability_headroom <= 20
    no_feasible_node = additional_capacity["small"] == 0
    warnings = {
        "balanced": load_balance_score >= 75 and not overloaded_nodes,
        "overloaded_node": overloaded_nodes,
        "near_saturation": near_saturation,
        "no_feasible_node": no_feasible_node,
    }

    latency_timeline = [
        {
            "time": p.get("time", ""),
            "latency": p.get("lat") or 0,
            "id": p.get("id", ""),
        }
        for p in reversed(placements)
        if p.get("success") and p.get("lat") is not None
    ][-20:]

    placement_time_history = []
    seen_commands = set()
    for p in reversed(placements):
        total_time = p.get("command_total_time_ms")
        if total_time is None:
            continue
        command_key = p.get("command_id") or f"{p.get('text', '')}:{p.get('time', '')}"
        if command_key in seen_commands:
            continue
        seen_commands.add(command_key)
        placement_time_history.append({
            "command_id": command_key,
            "time": p.get("time", ""),
            "text": p.get("text", ""),
            "total_time_ms": total_time,
            "command_total_time_ms": total_time,
            "classification_time_ms": p.get("classification_time_ms"),
            "placement_algorithm_time_ms": p.get("placement_algorithm_time_ms"),
            "neo4j_time_ms": p.get("neo4j_time_ms"),
            "websocket_prepare_time_ms": p.get("websocket_prepare_time_ms"),
            "timing": p.get("timing") or {},
        })
    placement_time_history = placement_time_history[-30:]
    command_times = [p["total_time_ms"] for p in placement_time_history]

    timed_nodes = [
        {"id": n["id"], "avg_placement_time_ms": n["avg_placement_time_ms"]}
        for n in node_rows
        if n["avg_placement_time_ms"] > 0
    ]
    fastest_node = min(timed_nodes, key=lambda n: n["avg_placement_time_ms"], default=None)
    slowest_node = max(timed_nodes, key=lambda n: n["avg_placement_time_ms"], default=None)

    snapshot = {
        "time": strftime("%H:%M:%S"),
        "nodes": node_rows,
        "cluster": {
            "total_capacity": totals,
            "used_capacity": used,
            "free_capacity": free,
            "usage_pct": cluster_pct,
            "remaining_pct": remaining_pct,
        },
        "load_balance_score": load_balance_score,
        "scalability_headroom_pct": scalability_headroom,
        "additional_services": additional_capacity,
        "warnings": warnings,
        "latency_timeline": latency_timeline,
        "placement_time_history": placement_time_history,
        "processing_time_history": placement_time_history,
        "latest_placement_time_ms": command_times[-1] if command_times else 0,
        "avg_placement_time_ms": _avg(command_times),
        "latest_processing_time_ms": command_times[-1] if command_times else 0,
        "avg_processing_time_ms": _avg(command_times),
        "fastest_node": fastest_node,
        "slowest_node": slowest_node,
        "history": analytics_history[-30:],
    }
    return snapshot


def record_analytics_snapshot():
    snapshot = build_analytics_snapshot()
    analytics_history.append({
        "time": snapshot["time"],
        "load_balance_score": snapshot["load_balance_score"],
        "scalability_headroom_pct": snapshot["scalability_headroom_pct"],
        "avg_latency": _avg([n["avg_latency"] for n in snapshot["nodes"]]),
        "avg_placement_time_ms": snapshot["avg_placement_time_ms"],
        "latest_placement_time_ms": snapshot["latest_placement_time_ms"],
        "avg_processing_time_ms": snapshot["avg_processing_time_ms"],
        "latest_processing_time_ms": snapshot["latest_processing_time_ms"],
        "cpu_pct": snapshot["cluster"]["usage_pct"]["CPU"],
        "mem_pct": snapshot["cluster"]["usage_pct"]["MEM"],
        "bw_pct": snapshot["cluster"]["usage_pct"]["BW"],
    })
    del analytics_history[:-60]
    return snapshot

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
                analytics_history.clear()
                record_analytics_snapshot()
                clear_all()
                await broadcast({"type": "init", "state": state})
                print("🔄 Reset effectué")
    except WebSocketDisconnect:
        if ws in ws_clients:
            ws_clients.remove(ws)


@app.get("/")
async def dashboard():
    return HTMLResponse(
        content=DASHBOARD_HTML,
        media_type="text/html; charset=utf-8",
    )


@app.get("/chatbot")
async def chatbot_page():
    if not CHATBOT_HTML.exists():
        raise HTTPException(status_code=404, detail="Chatbot frontend not found")
    return HTMLResponse(
        CHATBOT_HTML.read_text(encoding="utf-8"),
        media_type="text/html; charset=utf-8",
    )


@app.get("/analytics")
async def analytics_page():
    if not ANALYTICS_HTML.exists():
        raise HTTPException(status_code=404, detail="Analytics frontend not found")
    return FileResponse(ANALYTICS_HTML, media_type="text/html; charset=utf-8")


@app.get("/api/analytics")
async def analytics_data():
    return JSONResponse(record_analytics_snapshot())


@app.post("/chat", response_model=ChatResponse)
async def chatbot_chat(request: ChatRequest):
    try:
        from app.services.language_service import detect_language
        from app.services.ollama_service import OLLAMA_MODEL, generate_with_ollama
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Chatbot dependencies are missing or failed to import: {e}",
        )

    user_message = request.message.strip()
    language = detect_language(user_message)
    cache_key = _chat_cache_key(language, user_message)
    cached_response = get_cache().get_json("chatbot_responses", cache_key)
    if cached_response is not None:
        chat_logger = get_chat_logger()
        chat_logger.log_chat(
            user_message=user_message,
            detected_language=language,
            confidence=cached_response["confidence"],
            source=cached_response["source"],
            ollama_model=OLLAMA_MODEL if cached_response["source"] == "ollama" else None,
            matched_question=cached_response.get("matched_question"),
            category=cached_response.get("category"),
            risk=cached_response.get("risk"),
            fallback_used=cached_response["fallback_used"],
        )
        return ChatResponse(**cached_response)

    rag_service, chat_logger = get_chat_services()
    response_data, meta = rag_service.answer(user_message, language)

    if not meta["dataset_match"]:
        response_data["answer"] = generate_with_ollama(user_message)
        response_data["category"] = "General"
        response_data["risk"] = "LOW"
        response_data["follow_up"] = ""
        response_data["suggestions"] = []
        response_data["source"] = "ollama"
        response_data["fallback_used"] = True
        response_data["matched_question"] = meta["matched_question"]
    else:
        response_data["source"] = "dataset"
        response_data["fallback_used"] = False
        response_data["matched_question"] = meta["matched_question"]

    print("CHAT USER:", user_message)
    print("CHAT CONFIDENCE:", response_data["confidence"])
    print("CHAT SOURCE:", response_data["source"])
    print("CHAT MATCHED_QUESTION:", response_data["matched_question"])

    chat_logger.log_chat(
        user_message=user_message,
        detected_language=language,
        confidence=response_data["confidence"],
        source=response_data["source"],
        ollama_model=OLLAMA_MODEL if response_data["source"] == "ollama" else None,
        matched_question=meta["matched_question"],
        category=response_data["category"],
        risk=response_data["risk"],
        fallback_used=response_data["fallback_used"],
    )

    if not str(response_data["answer"]).startswith("Ollama fallback failed:"):
        get_cache().set_json("chatbot_responses", cache_key, response_data)

    return ChatResponse(**response_data)


@app.post("/chat/stream")
async def chatbot_chat_stream(request: ChatRequest):
    """Stream Ollama output while keeping dataset and Redis responses immediate."""
    try:
        from app.services.language_service import detect_language
        from app.services.ollama_service import OLLAMA_MODEL, stream_with_ollama
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Chatbot dependencies are missing or failed to import: {exc}",
        )

    user_message = request.message.strip()
    language = detect_language(user_message)
    cache_key = _chat_cache_key(language, user_message)

    def event(payload: dict) -> bytes:
        return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")

    def generate():
        cached_response = get_cache().get_json("chatbot_responses", cache_key)
        if cached_response is not None:
            yield event({"type": "complete", "data": cached_response})
            return

        rag_service, chat_logger = get_chat_services()
        response_data, meta = rag_service.answer(user_message, language)

        if meta["dataset_match"]:
            response_data["source"] = "dataset"
            response_data["fallback_used"] = False
            response_data["matched_question"] = meta["matched_question"]
            get_cache().set_json("chatbot_responses", cache_key, response_data)
            chat_logger.log_chat(
                user_message=user_message,
                detected_language=language,
                confidence=response_data["confidence"],
                source="dataset",
                ollama_model=None,
                matched_question=meta["matched_question"],
                category=response_data["category"],
                risk=response_data["risk"],
                fallback_used=False,
            )
            yield event({"type": "complete", "data": response_data})
            return

        response_data.update({
            "answer": "",
            "category": "General",
            "risk": "LOW",
            "follow_up": "",
            "suggestions": [],
            "source": "ollama",
            "fallback_used": True,
            "matched_question": meta["matched_question"],
        })
        yield event({"type": "meta", "data": response_data})

        chunks = []
        for chunk in stream_with_ollama(user_message):
            chunks.append(chunk)
            yield event({"type": "chunk", "text": chunk})

        response_data["answer"] = "".join(chunks).strip()
        failed = response_data["answer"].startswith("Ollama fallback failed:")
        if not failed:
            get_cache().set_json("chatbot_responses", cache_key, response_data)
        chat_logger.log_chat(
            user_message=user_message,
            detected_language=language,
            confidence=response_data["confidence"],
            source="ollama",
            ollama_model=OLLAMA_MODEL,
            matched_question=meta["matched_question"],
            category=response_data["category"],
            risk=response_data["risk"],
            fallback_used=True,
        )
        yield event({"type": "complete", "data": response_data})

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/state")
async def get_state():
    return state


@app.get("/graph")
async def get_graph(request: Request):
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        return HTMLResponse(
            content="<script>window.location.href='/#graph';</script>",
            media_type="text/html; charset=utf-8",
        )

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
    placement_lookup = {}
    for item in state.get("placements", []):
        for node_id in ([item.get("node")] if item.get("node") else item.get("nodes") or []):
            if not node_id:
                continue
            placement_lookup.setdefault((item.get("id"), node_id), item)
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
                    timing = placement_lookup.get((iid, nid), {})
                    timing_payload = timing.get("timing") or {}
                    placement_time_ms = timing.get("time_ms") or timing.get("placement_time_ms")
                    if iid not in nodes_map:
                        nodes_map[iid] = {
                            "id": iid, "label": iid, "type": "intention",
                            "desc": rec["desc"], "success": rec["success"],
                            "services": rec["services"],
                            "voice_text": rec["voice_text"], "ts": rec["ts"],
                            "placement_time_ms": placement_time_ms,
                            "command_total_time_ms": timing.get("command_total_time_ms"),
                            "classification_time_ms": timing.get("classification_time_ms"),
                            "placement_algorithm_time_ms": timing.get("placement_algorithm_time_ms"),
                            "neo4j_time_ms": timing.get("neo4j_time_ms"),
                            "websocket_prepare_time_ms": timing.get("websocket_prepare_time_ms"),
                            "timing": timing_payload,
                        }
                    edges.append({
                        "from": iid,
                        "to": nid,
                        "lat": rec["lat"],
                        "grouped": rec["grouped"],
                        "placement_time_ms": placement_time_ms,
                        "command_total_time_ms": timing.get("command_total_time_ms"),
                        "classification_time_ms": timing.get("classification_time_ms"),
                        "placement_algorithm_time_ms": timing.get("placement_algorithm_time_ms"),
                        "neo4j_time_ms": timing.get("neo4j_time_ms"),
                        "websocket_prepare_time_ms": timing.get("websocket_prepare_time_ms"),
                        "timing": timing_payload,
                    })
        except Exception as e:
            print(f"Graph Neo4j error: {e}")
    return JSONResponse({"nodes": list(nodes_map.values()), "edges": edges})
