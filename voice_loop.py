# voice_loop.py - main voice/text processing loop

import asyncio
import threading
import time

import sounddevice as sd

from config import SAMPLE_RATE, SERVER_PORT
from core.detection import detect_multiple_intentions
from core.nodes import state
from core.placement import apply_placement, select_node, total_resources
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


def _history_item(intent: dict, results: list, text: str) -> dict:
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
        "source": placed[0].get("source", "?"),
        "skipped": [r.get("service") for r in failed],
    }


def process_text_command(text: str, lang: str, loop):
    text = (text or "").strip()
    if not text:
        loop.run_until_complete(broadcast({"type": "no_intent", "text": ""}))
        return

    print(f"\nText pipeline input [{lang.upper()}]: {text}")
    state["last_text"] = text
    loop.run_until_complete(broadcast({"type": "transcript", "text": text, "lang": lang}))

    detected = detect_multiple_intentions(text)
    if not detected:
        msg = "Aucune intention IBN détectée. Réessayez." if lang == "fr" else "No IBN intention detected. Please try again."
        print(f"\n{msg}")
        speak(msg, lang)
        loop.run_until_complete(broadcast({"type": "no_intent", "text": text}))
        return

    print(f"\n{len(detected)} intention(s) detected:")
    for intent in detected:
        print("\n" + "-" * 45)
        print(f"   {intent['id']} - {intent['description']}")
        print(f"   Services: {', '.join(intent['services'])}")
        state["last_intent"] = intent["id"]

        req = total_resources(intent["services"])
        print(f"   Resources: CPU={req['CPU']} MEM={req['MEM']} BW={req['BW']}Mbps")

        results = select_node(
            req,
            intent["QoS"]["latency"],
            intent["services"],
            intent_desc=intent["description"],
        )
        placed = [r for r in results if r.get("node")]
        failed = [r for r in results if not r.get("node")]
        status = _placement_status(results)

        state["stats"]["total"] += 1
        if placed:
            state["stats"]["success"] += 1
            apply_placement(intent, results)
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

        history = _history_item(intent, results, text)
        state["placements"].insert(0, history)
        record_analytics_snapshot()
        write_voice_placement(intent, results, text)

    state["placements"] = state["placements"][:20]

    response = generate_response(text, detected, state["placements"][:len(detected)], lang)
    print(f"\nResponse: {response}")
    speak(response, lang)

    loop.run_until_complete(broadcast({
        "type": "placement",
        "intents": [i["id"] for i in detected],
        "intent": detected[0]["id"],
        "node": state["last_node"],
        "lat": state["placements"][0].get("lat") if state["placements"] else 0,
        "services": [s for i in detected for s in i["services"]],
        "nodes": state["nodes"],
        "placements": state["placements"],
        "stats": state["stats"],
    }))


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
