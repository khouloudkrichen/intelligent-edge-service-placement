# core/rag.py - constrained RAG/LLM fallback for placement

from core.rules import get_free_resources
from core.nodes import state
from data.dataset import nodes
from services.llm import ollama_call


def _has_required_resources(info: dict, required: dict) -> bool:
    free = info["free"]
    return (
        free.get("CPU", 0) >= required.get("CPU", 0)
        and free.get("MEM", 0) >= required.get("MEM", 0)
        and free.get("BW", 0) >= required.get("BW", 0)
        and free.get("DISK", 0) >= required.get("DISK", 0)
    )


def _feasible_nodes(required: dict, qos_latency: float | None = None) -> list[dict]:
    feasible = []
    for nd in nodes:
        info = get_free_resources(nd["id"])
        if not info:
            continue
        if not _has_required_resources(info, required):
            continue
        if qos_latency is not None and info["lat"] > qos_latency:
            continue
        feasible.append(info)
    return feasible


def build_rag_context(required: dict, qos_latency: float, intent_desc: str) -> str:
    lines = []
    lines.append("=== INTENTION ===")
    lines.append(f"Description: {intent_desc}")
    lines.append(
        f"Required: CPU={required.get('CPU', 0)} MEM={required.get('MEM', 0)}G "
        f"BW={required.get('BW', 0)}Mbps DISK={required.get('DISK', 0)}G"
    )
    lines.append(f"Latency QoS max: {qos_latency}ms")
    lines.append("")
    lines.append("=== NODE STATE AT CURRENT INSTANT ===")
    lines.append(f"{'NODE':<6} {'TYPE':<10} {'CPU_F':<6} {'MEM_F':<6} {'BW_F':<6} {'LAT':<8} {'OK'}")
    lines.append("-" * 60)

    for nd in nodes:
        info = get_free_resources(nd["id"])
        if not info:
            continue
        ok = _has_required_resources(info, required) and info["lat"] <= qos_latency
        lines.append(
            f"{nd['id']:<6} {nd['type']:<10} "
            f"{info['free']['CPU']:<6} {info['free']['MEM']:<6} "
            f"{info['free']['BW']:<6} {info['lat']:<8} {ok}"
        )

    recent = state.get("placements", [])[:5]
    if recent:
        lines.append("")
        lines.append("=== RECENT PLACEMENTS ===")
        for p in recent:
            node = p.get("node") or (p.get("nodes") or ["?"])[0]
            status = "OK" if p.get("success") else "FAIL"
            lines.append(f"{status} {p.get('id', '?')} -> {node} ({p.get('lat', '?')}ms)")

    feasible = _feasible_nodes(required, qos_latency)
    lines.append("")
    lines.append("=== FEASIBLE COMPROMISE NODES ===")
    if feasible:
        for info in sorted(feasible, key=lambda x: (-x["free"]["CPU"], x["lat"]))[:5]:
            lines.append(
                f"- {info['node_id'].upper()} free={info['free']} "
                f"lat={info['lat']}ms type={info['node_type']}"
            )
    else:
        lines.append("None. The request must fail.")
    return "\n".join(lines)


def rag_llm_fallback(required: dict, qos_latency: float, intent_desc: str) -> dict:
    """Fallback used only after strict rules fail.

    It may relax the 20% CPU margin, but it still must respect CPU/MEM/DISK/BW
    and latency QoS. If no feasible node exists, the placement fails clearly.
    """
    print("\n   RAG fallback: checking feasible compromise nodes...")
    feasible = _feasible_nodes(required, qos_latency)
    if not feasible:
        print("   RAG failed: no node has enough resources within latency QoS")
        return {
            "node_id": None,
            "lat": None,
            "source": "rag_failed",
            "reason": "No node has enough CPU/MEM/DISK/BW within latency QoS",
        }

    context = build_rag_context(required, qos_latency, intent_desc)
    prompt = f"""You are an IBN placement engine. Strict placement rules failed.
Choose the best compromise node from the FEASIBLE nodes only.

{context}

OUTPUT: Only one node ID, for example n3.
BEST NODE:"""

    try:
        raw = ollama_call(prompt, max_tokens=5, temperature=0.0)
        node_id = raw.strip().lower().replace(":", "").split()[0] if raw.strip() else None
        valid_ids = {info["node_id"] for info in feasible}
        if node_id not in valid_ids:
            print(f"   LLM proposed '{node_id}', not feasible -> least loaded feasible")
            node_id = _least_loaded_node(required, qos_latency)

        if node_id:
            info = get_free_resources(node_id)
            print(f"   RAG selected {node_id.upper()} (lat={info['lat']}ms)")
            return {
                "node_id": node_id,
                "lat": info["lat"],
                "source": "rag_llm",
                "reason": "Feasible LLM compromise after strict margin failure",
            }
    except Exception as e:
        print(f"   RAG LLM error: {e}")

    node_id = _least_loaded_node(required, qos_latency)
    if node_id:
        info = get_free_resources(node_id)
        print(f"   RAG last resort -> {node_id.upper()} (lat={info['lat']}ms)")
        return {
            "node_id": node_id,
            "lat": info["lat"],
            "source": "rag_last_resort",
            "reason": "Least loaded feasible node",
        }

    return {"node_id": None, "lat": None, "source": "rag_failed", "reason": "No feasible node"}


def _least_loaded_node(required: dict, qos_latency: float | None = None) -> str | None:
    feasible = _feasible_nodes(required or {}, qos_latency)
    if not feasible:
        return None
    best = sorted(feasible, key=lambda info: (-info["free"]["CPU"], info["lat"]))[0]
    return best["node_id"]
