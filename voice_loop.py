# ═══════════════════════════════════════════════════════
# voice_loop.py — Boucle vocale principale
# ═══════════════════════════════════════════════════════

import time, threading, asyncio
import sounddevice as sd

from config                 import SAMPLE_RATE, SERVER_PORT
from core.nodes             import state
from core.detection         import detect_multiple_intentions
from core.placement         import total_resources, select_node, apply_placement
from services.transcription import transcribe
from services.tts           import speak
from services.neo4j_writer  import write_voice_placement
from services.llm           import ollama_call
from api.server             import broadcast, recording_event, stop_event


def generate_response(text: str, detected: list, placements: list, lang: str) -> str:
    if not detected:
        return ("Aucune intention détectée. Veuillez réessayer."
                if lang == "fr" else "No intention detected. Please try again.")
    summary = []
    for i, intent in enumerate(detected):
        p    = placements[i] if i < len(placements) else None
        node = (p.get("node") or (p.get("nodes") or ["?"])[0]) if p and p.get("success") else None
        lat  = p.get("lat", "?") if p else "?"
        line = (f"- {intent['description']} → nœud {node} ({lat}ms)"
                if node else f"- {intent['description']} → ÉCHEC")
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
        for prefix in ["here's a short response:", "here is a short response:",
                        "short response:", "response:"]:
            if answer.lower().startswith(prefix):
                answer = answer[len(prefix):].strip()
        answer = answer.replace("\n", " ").strip()
        if answer:
            print(f"   💬 Ollama réponse : {answer[:100]}...")
            return answer
    except Exception as e:
        print(f"   ⚠️  Ollama response error : {e}")

    parts = [f"{p.get('id','?')} on {(p.get('node') or (p.get('nodes') or ['?'])[0])}"
             for p in placements if p.get("success")]
    if lang == "fr":
        return (f"{len(parts)} service(s) déployé(s) : {', '.join(parts)}."
                if parts else "Impossible de placer les services.")
    return (f"{len(parts)} service(s) deployed: {', '.join(parts)}."
            if parts else "Cannot place services. Insufficient resources.")


def voice_loop():
    print("\n" + "═"*55)
    print("  IBN Voice — Placement de services")
    print(f"  Dashboard : http://localhost:{SERVER_PORT}")
    print("═"*55)
    print("\n💡 Démarrer l'enregistrement :")
    print("   • Appuie sur ENTRÉE dans ce terminal")
    print("   • OU clique sur 🎤 Parler dans le dashboard\n")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    while True:
        try:
            recording_event.clear()
            stop_event.clear()
            print("\n⏎  Appuie sur ENTRÉE ou clique 🎤 sur le dashboard...")

            def wait_keyboard_start():
                try:
                    input()
                    recording_event.set()
                except Exception:
                    pass

            threading.Thread(target=wait_keyboard_start, daemon=True).start()
            recording_event.wait()

            state["listening"] = True
            loop.run_until_complete(broadcast({"type": "listening", "listening": True}))

            print("🎤 Enregistrement... (ENTRÉE ou ⏹ Stop pour arrêter)")
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

            print("⏳ Transcription...")
            text, lang = transcribe(audio)

            if not text:
                print("❌ Aucun texte détecté")
                loop.run_until_complete(broadcast({"type": "no_intent", "text": ""}))
                continue

            print(f"\n🗣️  [{lang.upper()}] : {text}")
            state["last_text"] = text
            loop.run_until_complete(broadcast({"type": "transcript", "text": text, "lang": lang}))

            detected = detect_multiple_intentions(text)

            if not detected:
                msg = ("Aucune intention IBN détectée. Réessayez."
                       if lang == "fr" else "No IBN intention detected. Please try again.")
                print(f"\nℹ️  {msg}")
                speak(msg, lang)
                loop.run_until_complete(broadcast({"type": "no_intent", "text": text}))
                continue

            print(f"\n🎯 {len(detected)} intention(s) détectée(s) :")

            for intent in detected:
                print(f"\n{'─'*45}")
                print(f"   📌 {intent['id']} — {intent['description']}")
                print(f"   Services  : {', '.join(intent['services'])}")
                state["last_intent"] = intent["id"]

                req = total_resources(intent["services"])
                print(f"   Ressources: CPU={req['CPU']} MEM={req['MEM']} BW={req['BW']}Mbps")

                results    = select_node(req, intent["QoS"]["latency"], intent["services"],
                                          intent_desc=intent["description"])
                placed     = [r for r in results if r["node"]]
                failed     = [r for r in results if not r["node"]]
                is_grouped = len(results) == 1 and results[0].get("grouped")
                placement_status = (
                    "FAILED" if not placed else
                    "PARTIAL" if failed or any(r.get("status") == "PARTIAL" for r in results) else
                    "DEGRADED" if any(r.get("status") == "DEGRADED" for r in results) else
                    "PLACED"
                )
                success    = placement_status != "FAILED"
                state["stats"]["total"] += 1

                if success:
                    state["stats"]["success"] += 1
                    apply_placement(intent, results)

                    if is_grouped:
                        node_id = placed[0]["node"]
                        lat     = placed[0]["lat"]
                        source  = placed[0].get("source", "?")
                        state["last_node"] = node_id
                        src_icon = "📋" if source == "rules" else "🤖" if "llm" in source else "🆘"
                        print(f"   ✅ [{placement_status} {src_icon} {source}] → {node_id.upper()} ({lat}ms)")
                        if placed[0].get("tolerance"):
                            print(f"   Tolérance dégradée : {placed[0]['tolerance']}")
                    else:
                        parts = [f"{r['service']}→{r['node'].upper()}({r['lat']}ms)[{r.get('status','?')}/{r.get('source','?')}]"
                                 for r in placed]
                        print(f"   ✅ {placement_status} distribué : {', '.join(parts)}")
                        if failed:
                            print(f"   ⚠️  Services ignorés : {[r['service'] for r in failed]}")

                    placement = {
                        "id":      intent["id"],
                        "desc":    intent["description"][:50],
                        "services":intent["services"],
                        "node":    placed[0]["node"] if is_grouped else None,
                        "nodes":   [r["node"] for r in placed],
                        "lat":     placed[0]["lat"],
                        "success": True,
                        "status":  placement_status,
                        "skipped": [r["service"] for r in failed],
                        "grouped": is_grouped,
                        "time":    time.strftime("%H:%M:%S"),
                        "text":    text,
                        "source":  placed[0].get("source", "?"),
                    }
                    state["placements"].insert(0, placement)
                    write_voice_placement(intent, results, text)

                else:
                    state["stats"]["fail"] += 1
                    print(f"   ❌ Aucun nœud disponible")
                    state["placements"].insert(0, {
                        "id":      intent["id"],
                        "desc":    intent["description"][:50],
                        "services":intent["services"],
                        "node":    None,
                        "success": False,
                        "status":  "FAILED",
                        "time":    time.strftime("%H:%M:%S"),
                        "text":    text,
                    })

            state["placements"] = state["placements"][:20]

            response = generate_response(
                text, detected, state["placements"][:len(detected)], lang
            )
            print(f"\n🔊 {response}")
            speak(response, lang)

            loop.run_until_complete(broadcast({
                "type":      "placement",
                "intents":   [i["id"] for i in detected],
                "intent":    detected[0]["id"],
                "node":      state["last_node"],
                "lat":       state["placements"][0].get("lat") if state["placements"] else 0,
                "services":  [s for i in detected for s in i["services"]],
                "nodes":     state["nodes"],
                "placements":state["placements"],
                "stats":     state["stats"],
            }))

        except KeyboardInterrupt:
            print("\n\n👋 Arrêt vocal")
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.close()
            except Exception:
                pass
            break

        except Exception as e:
            print(f"\n❌ Erreur : {e}")
            continue
