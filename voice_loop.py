# voice_loop.py - main voice/text processing loop

import asyncio
import threading
import time

import sounddevice as sd

from config import SAMPLE_RATE, SERVER_PORT
from core.detection import detect_multiple_intentions
from core.nodes import state
from core.placement import place_intention_batch
from services.llm import ollama_call
from services.neo4j_writer import write_voice_placement
from services.transcription import transcribe
from services.tts import speak
from api.server import (
    broadcast,
    pending_text,
    record_analytics_snapshot,
    recording_event,
    stop_event,
    text_event,
)


def generate_response(text: str, detected: list, placements: list, lang: str) -> str:
    if not detected:
        return (
            "Aucune intention détectée. Veuillez réessayer."
            if lang == "fr"
            else "No intention detected. Please try again."
        )

    summary = []
    for i, intent in enumerate(detected):
        p = placements[i] if i < len(placements) else None
        node = (p.get("node") or (p.get("nodes") or ["?"])[0]) if p and p.get("success") else None
        lat = p.get("lat", "?") if p else "?"
        status = p.get("status", "PLACED") if p else "FAILED"
        line = (
            f"- {intent['description']} -> node {node} ({lat}ms, {status})"
            if node
            else f"- {intent['description']} -> FAILED"
        )
        summary.append(line)

    response_lang = "French" if lang == "fr" else "English"
    prompt = f"""You are an IBN assistant for industrial technicians wearing VR glasses.
Technician said: "{text}"
Services deployed:
{chr(10).join(summary)}
Write a SHORT response (2 sentences max) in {response_lang}.
Confirm what was deployed and on which node. Be professional.
Do NOT start with preambles like "Here's a short response".
Response:"""
    try:
        answer = ollama_call(prompt)
        for prefix in ["here's a short response:", "here is a short response:", "short response:", "response:"]:
            if answer.lower().startswith(prefix):
                answer = answer[len(prefix):].strip()
        answer = answer.replace("\n", " ").strip()
        if answer:
            print(f"   Ollama response: {answer[:100]}...")
            return answer
    except Exception as e:
        print(f"   Ollama response error: {e}")

    parts = [
        f"{p.get('id', '?')} on {(p.get('node') or (p.get('nodes') or ['?'])[0])} ({p.get('status', 'PLACED')})"
        for p in placements
        if p.get("success")
    ]
    if lang == "fr":
        return f"{len(parts)} service(s) déployé(s) : {', '.join(parts)}." if parts else "Impossible de placer les services."
    return f"{len(parts)} service(s) deployed: {', '.join(parts)}." if parts else "Cannot place services."


def _placement_status(results: list) -> str:
    placed = [r for r in results if r.get("node")]
    failed = [r for r in results if not r.get("node")]
    if not placed:
        return "FAILED"
    if failed or any(r.get("status") == "PARTIAL" for r in results):
        return "PARTIAL"
    if any(r.get("status") == "DEGRADED" for r in results):
        return "DEGRADED"
    return "PLACED"


def _history_item(
    intent: dict,
    results: list,
    text: str,
    command_id: str = "",
    time_ms: float = 0.0,
) -> dict:
    placed = [r for r in results if r.get("node")]
    failed = [r for r in results if not r.get("node")]
    is_grouped = len(results) == 1 and results[0].get("grouped")
    if not placed:
        return {
            "id": intent["id"],
            "desc": intent["description"][:50],
            "services": intent["services"],
            "node": None,
            "nodes": [],
            "lat": None,
            "success": False,
            "status": "FAILED",
            "grouped": False,
            "time": time.strftime("%H:%M:%S"),
            "text": text,
            "command_id": command_id,
            "time_ms": time_ms,
            "placement_time_ms": time_ms,
            "command_total_time_ms": None,
            "source": "failed",
            "skipped": [r.get("service") for r in failed],
        }

    return {
        "id": intent["id"],
        "desc": intent["description"][:50],
        "services": intent["services"],
        "node": placed[0]["node"] if is_grouped else None,
        "nodes": [r["node"] for r in placed],
        "lat": placed[0]["lat"],
        "success": True,
        "status": _placement_status(results),
        "grouped": is_grouped,
        "time": time.strftime("%H:%M:%S"),
        "text": text,
        "command_id": command_id,
        "time_ms": time_ms,
        "placement_time_ms": time_ms,
        "command_total_time_ms": None,
        "source": placed[0].get("source", "?"),
        "skipped": [r.get("service") for r in failed],
    }


def _seconds(ms: float) -> float:
    return round((ms or 0.0) / 1000, 3)


def process_text_command(text: str, lang: str, loop):
    command_start = time.perf_counter()
    text = (text or "").strip()
    if not text:
        loop.run_until_complete(broadcast({"type": "no_intent", "text": ""}))
        return

    print(f"\nText pipeline input [{lang.upper()}]: {text}")
    state["last_text"] = text
    command_id = f"cmd-{int(time.time() * 1000)}"
    loop.run_until_complete(broadcast({"type": "transcript", "text": text, "lang": lang}))

    detection_start = time.perf_counter()
    detected = detect_multiple_intentions(text)
    detection_ms = round((time.perf_counter() - detection_start) * 1000, 2)
    print(f"Timing detection: {detection_ms}ms")
    if not detected:
        msg = "Aucune intention IBN détectée. Réessayez." if lang == "fr" else "No IBN intention detected. Please try again."
        print(f"\n{msg}")
        print(f"Timing detection only: {detection_ms}ms")
        websocket_prepare_start = time.perf_counter()
        websocket_prepare_ms = 0.0
        total_elapsed_ms = round((time.perf_counter() - command_start) * 1000, 2)
        payload = {
            "type": "no_intent",
            "text": text,
            "total_time_ms": total_elapsed_ms,
            "command_total_time_ms": total_elapsed_ms,
            "command_total_time_s": _seconds(total_elapsed_ms),
            "classification_time_ms": detection_ms,
            "classification_time_s": _seconds(detection_ms),
            "placement_algorithm_time_ms": 0.0,
            "placement_algorithm_time_s": 0.0,
            "neo4j_time_ms": 0.0,
            "neo4j_time_s": 0.0,
            "websocket_prepare_time_ms": websocket_prepare_ms,
            "websocket_prepare_time_s": _seconds(websocket_prepare_ms),
            "timing": {
                "command_total_time_ms": total_elapsed_ms,
                "command_total_time_s": _seconds(total_elapsed_ms),
                "classification_time_ms": detection_ms,
                "classification_time_s": _seconds(detection_ms),
                "placement_algorithm_time_ms": 0.0,
                "placement_algorithm_time_s": 0.0,
                "neo4j_time_ms": 0.0,
                "neo4j_time_s": 0.0,
                "websocket_prepare_time_ms": websocket_prepare_ms,
                "websocket_prepare_time_s": _seconds(websocket_prepare_ms),
            },
        }
        websocket_prepare_ms = round((time.perf_counter() - websocket_prepare_start) * 1000, 2)
        total_elapsed_ms = round((time.perf_counter() - command_start) * 1000, 2)
        payload.update({
            "total_time_ms": total_elapsed_ms,
            "command_total_time_ms": total_elapsed_ms,
            "command_total_time_s": _seconds(total_elapsed_ms),
            "websocket_prepare_time_ms": websocket_prepare_ms,
            "websocket_prepare_time_s": _seconds(websocket_prepare_ms),
        })
        payload["timing"].update({
            "command_total_time_ms": total_elapsed_ms,
            "command_total_time_s": _seconds(total_elapsed_ms),
            "websocket_prepare_time_ms": websocket_prepare_ms,
            "websocket_prepare_time_s": _seconds(websocket_prepare_ms),
        })
        loop.run_until_complete(broadcast(payload))
        speak(msg, lang)
        return

    print(f"\n{len(detected)} intention(s) detected:")
    placement_batch_start = time.perf_counter()
    batch_plan = place_intention_batch(detected)
    placement_batch_ms = round((time.perf_counter() - placement_batch_start) * 1000, 2)
    print(f"Timing placement batch: {placement_batch_ms}ms")

    command_history_items = []
    per_intention_times = []
    neo4j_ms = 0.0
    for planned in batch_plan:
        intent = planned["intent"]
        req = planned["required"]
        results = planned["results"]
        placed = planned["placed"]
        failed = planned["failed"]
        print("\n" + "-" * 45)
        print(f"   {intent['id']} - {intent['description']}")
        print(f"   Services: {', '.join(intent['services'])}")
        state["last_intent"] = intent["id"]

        print(f"   Resources: CPU={req['CPU']} MEM={req['MEM']} BW={req['BW']}Mbps")
        status = _placement_status(results)

        state["stats"]["total"] += 1
        if placed:
            state["stats"]["success"] += 1
            state["last_node"] = placed[0]["node"]
            if len(results) == 1 and results[0].get("grouped"):
                print(f"   OK [{status}/{placed[0].get('source', '?')}] -> {placed[0]['node'].upper()} ({placed[0]['lat']}ms)")
                if placed[0].get("tolerance"):
                    print(f"   Degraded tolerance: {placed[0]['tolerance']}")
            else:
                parts = [
                    f"{r['service']}->{r['node'].upper()}({r['lat']}ms)[{r.get('status', '?')}/{r.get('source', '?')}]"
                    for r in placed
                ]
                print(f"   OK {status} distributed: {', '.join(parts)}")
                if failed:
                    print(f"   Skipped services: {[r.get('service') for r in failed]}")
        else:
            state["stats"]["fail"] += 1
            print("   FAILED: no node available")

        intention_elapsed_ms = planned["total_ms"]
        history = _history_item(intent, results, text, command_id, intention_elapsed_ms)
        command_history_items.append(history)
        per_intention_times.append({
            "id": intent["id"],
            "node": history.get("node") or (history.get("nodes") or [None])[0],
            "nodes": history.get("nodes") or [],
            "time_ms": intention_elapsed_ms,
            "time_s": _seconds(intention_elapsed_ms),
            "latency_ms": history.get("lat"),
            "status": history.get("status", "FAILED"),
            "services": intent["services"],
        })
        print(
            f"   Placement execution time: {intention_elapsed_ms}ms "
            f"(scoring={planned['scoring_ms']}ms, apply={planned['placement_ms']}ms)"
        )
        neo4j_start = time.perf_counter()
        write_voice_placement(intent, results, text)
        neo4j_ms += (time.perf_counter() - neo4j_start) * 1000

    neo4j_ms = round(neo4j_ms, 2)
    for history in command_history_items:
        history["classification_time_ms"] = detection_ms
        history["classification_time_s"] = _seconds(detection_ms)
        history["placement_algorithm_time_ms"] = placement_batch_ms
        history["placement_algorithm_time_s"] = _seconds(placement_batch_ms)
        history["neo4j_time_ms"] = neo4j_ms
        history["neo4j_time_s"] = _seconds(neo4j_ms)
        history["per_intention_time_s"] = _seconds(history.get("time_ms") or 0)
        state["placements"].insert(0, history)

    state["placements"] = state["placements"][:20]

    websocket_prepare_start = time.perf_counter()
    total_elapsed_ms = round((time.perf_counter() - command_start) * 1000, 2)
    websocket_prepare_ms = round((time.perf_counter() - websocket_prepare_start) * 1000, 2)
    timing = {
        "command_total_time_ms": total_elapsed_ms,
        "command_total_time_s": _seconds(total_elapsed_ms),
        "classification_time_ms": detection_ms,
        "classification_time_s": _seconds(detection_ms),
        "placement_algorithm_time_ms": placement_batch_ms,
        "placement_algorithm_time_s": _seconds(placement_batch_ms),
        "neo4j_time_ms": neo4j_ms,
        "neo4j_time_s": _seconds(neo4j_ms),
        "websocket_prepare_time_ms": websocket_prepare_ms,
        "websocket_prepare_time_s": _seconds(websocket_prepare_ms),
    }
    for history in command_history_items:
        history["command_total_time_ms"] = total_elapsed_ms
        history["command_total_time_s"] = _seconds(total_elapsed_ms)
        history["websocket_prepare_time_ms"] = websocket_prepare_ms
        history["websocket_prepare_time_s"] = _seconds(websocket_prepare_ms)
        history["timing"] = dict(timing)

    payload = {
        "type": "placement_result",
        "command_id": command_id,
        "command_text": text,
        "intents": [i["id"] for i in detected],
        "intentions": [i["id"] for i in detected],
        "total_time_ms": total_elapsed_ms,
        "command_total_time_ms": total_elapsed_ms,
        "command_total_time_s": _seconds(total_elapsed_ms),
        "classification_time_ms": detection_ms,
        "classification_time_s": _seconds(detection_ms),
        "placement_algorithm_time_ms": placement_batch_ms,
        "placement_algorithm_time_s": _seconds(placement_batch_ms),
        "neo4j_time_ms": neo4j_ms,
        "neo4j_time_s": _seconds(neo4j_ms),
        "websocket_prepare_time_ms": websocket_prepare_ms,
        "websocket_prepare_time_s": _seconds(websocket_prepare_ms),
        "timing": timing,
        "per_intention": per_intention_times,
        "intent": detected[0]["id"],
        "node": state["last_node"],
        "lat": state["placements"][0].get("lat") if state["placements"] else 0,
        "services": [s for i in detected for s in i["services"]],
        "nodes": state["nodes"],
        "placements": state["placements"],
        "stats": state["stats"],
    }
    websocket_prepare_ms = round((time.perf_counter() - websocket_prepare_start) * 1000, 2)
    total_elapsed_ms = round((time.perf_counter() - command_start) * 1000, 2)
    timing.update({
        "command_total_time_ms": total_elapsed_ms,
        "command_total_time_s": _seconds(total_elapsed_ms),
        "websocket_prepare_time_ms": websocket_prepare_ms,
        "websocket_prepare_time_s": _seconds(websocket_prepare_ms),
    })
    payload.update({
        "total_time_ms": total_elapsed_ms,
        "command_total_time_ms": total_elapsed_ms,
        "command_total_time_s": _seconds(total_elapsed_ms),
        "websocket_prepare_time_ms": websocket_prepare_ms,
        "websocket_prepare_time_s": _seconds(websocket_prepare_ms),
        "timing": timing,
    })
    for history in command_history_items:
        history["command_total_time_ms"] = total_elapsed_ms
        history["command_total_time_s"] = _seconds(total_elapsed_ms)
        history["websocket_prepare_time_ms"] = websocket_prepare_ms
        history["websocket_prepare_time_s"] = _seconds(websocket_prepare_ms)
        history["timing"] = dict(timing)
    record_analytics_snapshot()
    print(
        f"Timing summary: total={total_elapsed_ms}ms, classification={detection_ms}ms, "
        f"placement_algorithm={placement_batch_ms}ms, neo4j={neo4j_ms}ms, "
        f"websocket_prepare={websocket_prepare_ms}ms"
    )
    loop.run_until_complete(broadcast(payload))

    response = generate_response(text, detected, state["placements"][:len(detected)], lang)
    print(f"\nResponse: {response}")
    speak(response, lang)


def _wait_for_start_or_text():
    while not recording_event.is_set() and not text_event.is_set():
        time.sleep(0.05)


def voice_loop():
    print("\n" + "=" * 55)
    print("  IBN Voice - Placement de services")
    print(f"  Dashboard : http://localhost:{SERVER_PORT}")
    print("=" * 55)
    print("\nDémarrer l'enregistrement :")
    print("   - Appuie sur ENTREE dans ce terminal")
    print("   - OU clique sur Parler dans le dashboard")
    print("   - OU envoie une commande texte depuis le dashboard\n")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    while True:
        try:
            recording_event.clear()
            stop_event.clear()
            print("\nAppuie sur ENTREE, clique Parler, ou envoie un texte...")

            def wait_keyboard_start():
                try:
                    input()
                    recording_event.set()
                except Exception:
                    pass

            threading.Thread(target=wait_keyboard_start, daemon=True).start()
            _wait_for_start_or_text()

            if text_event.is_set():
                text = pending_text.get("value", "").strip()
                pending_text["value"] = ""
                text_event.clear()
                process_text_command(text, "en", loop)
                continue

            state["listening"] = True
            loop.run_until_complete(broadcast({"type": "listening", "listening": True}))

            print("Recording... (ENTREE or Stop button to stop)")
            audio = sd.rec(int(60 * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1)

            stop_event.clear()

            def wait_keyboard_stop():
                try:
                    input()
                    stop_event.set()
                except Exception:
                    pass

            threading.Thread(target=wait_keyboard_stop, daemon=True).start()
            stop_event.wait()
            sd.stop()
            state["listening"] = False

            loop.run_until_complete(broadcast({"type": "recording_stopped"}))

            print("Transcription...")
            text, lang = transcribe(audio)
            if not text:
                print("No text detected")
                loop.run_until_complete(broadcast({"type": "no_intent", "text": ""}))
                continue

            process_text_command(text, lang, loop)

        except KeyboardInterrupt:
            print("\nStopping voice/text loop")
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.close()
            except Exception:
                pass
            break
        except Exception as e:
            print(f"\nError: {e}")
            loop.run_until_complete(broadcast({"type": "no_intent", "text": ""}))
            continue
