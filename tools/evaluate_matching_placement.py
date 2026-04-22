import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("IBN_SKIP_OLLAMA", "1")

from core.detection import detect_multiple_intentions, rank_intentions
from core.nodes import init_nodes, state
from core.placement import total_resources, select_node, apply_placement


SAMPLES = [
    "retrieve machine status",
    "show AR instructions for belt replacement",
    "detect hydraulic leak",
    "perform full diagnostics after maintenance",
    "perform full diagnostics after maintenance",
    "hello can you help me",
]


def run_sample(text: str):
    print("\n" + "=" * 80)
    print(f"TEXT: {text}")
    ranked = rank_intentions(text, limit=3)
    print("TOP MATCHES:")
    for r in ranked:
        print(
            f"  {r['id']} score={r['score']} conf={r['confidence']} "
            f"desc={r['intent']['description']}"
        )

    detected = detect_multiple_intentions(text)
    if not detected:
        print("RESULT: no reliable intention")
        return

    for intent in detected:
        req = total_resources(intent["services"])
        print(f"\nINTENT: {intent['id']} services={intent['services']} req={req}")
        results = select_node(req, intent["QoS"]["latency"], intent["services"], intent["description"])
        status = (
            "FAILED" if not any(r.get("node") for r in results) else
            "PARTIAL" if any(not r.get("node") or r.get("status") == "PARTIAL" for r in results) else
            "DEGRADED" if any(r.get("status") == "DEGRADED" for r in results) else
            "PLACED"
        )
        print(f"STATUS: {status}")
        print(f"PLACEMENT: {results}")
        if any(r.get("node") for r in results):
            apply_placement(intent, results)


def main():
    init_nodes(reset_load=True)
    state["placements"] = []
    state["stats"] = {"total": 0, "success": 0, "fail": 0}
    for text in SAMPLES:
        run_sample(text)


if __name__ == "__main__":
    main()
