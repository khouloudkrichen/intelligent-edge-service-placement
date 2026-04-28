# core/rules.py - strict placement validation and workload-aware scoring

from data.dataset import NODE_AVG_LATENCY, RESOURCE_KEYS, nodes, NODES_BY_ID
from core.nodes import get_node_state

MIN_FREE_PCT = 20

SCORE_WEIGHTS = {
    "latency": 0.35,
    "available": 0.25,
    "load_balance": 0.25,
    "fit": 0.10,
    "type": 0.05,
}


def workload_size(required: dict) -> str:
    cpu = required.get("CPU", 0)
    mem = required.get("MEM", 0)
    bw = required.get("BW", 0)
    if cpu >= 10 or mem >= 24 or bw >= 220:
        return "heavy"
    if cpu <= 3 and mem <= 8 and bw <= 100:
        return "light"
    return "medium"


def get_free_resources(node_id: str) -> dict | None:
    nd_s = get_node_state(node_id)
    nd_c = NODES_BY_ID.get(node_id)
    if not nd_s or not nd_c:
        return None

    cap = nd_c["capacity"]
    free = {
        "CPU": cap["CPU"] - nd_s["cpu_used"],
        "MEM": cap["MEM"] - nd_s["mem_used"],
        "DISK": cap["DISK"] - nd_s["disk_used"],
        "BW": cap["BW"] - nd_s["bw_used"],
    }
    pct = {
        "CPU": round(free["CPU"] / cap["CPU"] * 100) if cap["CPU"] else 0,
        "MEM": round(free["MEM"] / cap["MEM"] * 100) if cap["MEM"] else 0,
        "BW": round(free["BW"] / cap["BW"] * 100) if cap["BW"] else 0,
    }
    avg_lat = NODE_AVG_LATENCY.get(node_id, 50)
    return {
        "node_id": node_id,
        "node_type": nd_s["type"],
        "free": free,
        "pct": pct,
        "cap": cap,
        "lat": avg_lat,
    }


def hard_capacity_rejection(node_info: dict, required: dict) -> str | None:
    free = node_info["free"]
    for resource in RESOURCE_KEYS:
        need = required.get(resource, 0)
        if free.get(resource, 0) < need:
            return f"{resource} insufficient ({free.get(resource, 0)} < {need})"
    return None


def check_rule(node_info: dict, required: dict, qos_latency: float) -> tuple[bool, str]:
    free = node_info["free"]
    cap = node_info["cap"]
    lat = node_info["lat"]

    req_cpu = required.get("CPU", 0)
    hard_reason = hard_capacity_rejection(node_info, required)
    if hard_reason:
        return False, hard_reason

    cpu_after = free["CPU"] - req_cpu
    cpu_min_free = round(cap["CPU"] * MIN_FREE_PCT / 100, 1)
    if cpu_after < cpu_min_free:
        return False, f"CPU margin too low after placement ({cpu_after} < {cpu_min_free})"

    if lat > qos_latency:
        return False, f"Latency too high ({lat}ms > {qos_latency}ms)"

    return True, "OK"


def compute_score(node_info: dict, required: dict, qos_latency: float) -> float:
    """Rank eligible nodes.

    Light requests prefer the smallest valid node with enough headroom.
    Heavy requests prefer strong computing nodes and higher remaining capacity.
    """
    lat = node_info["lat"]
    cap = node_info["cap"]
    free = node_info["free"]
    state_node = get_node_state(node_info["node_id"]) or {}
    size = workload_size(required)

    req_cpu = required.get("CPU", 0)
    req_mem = required.get("MEM", 0)
    req_bw = required.get("BW", 0)

    cpu_after_pct = ((free["CPU"] - req_cpu) / cap["CPU"] * 100) if cap["CPU"] else 0
    mem_after_pct = ((free["MEM"] - req_mem) / cap["MEM"] * 100) if cap["MEM"] else 0
    bw_after_pct = ((free["BW"] - req_bw) / cap["BW"] * 100) if cap["BW"] else 0
    available_score = max(0, min(100, (cpu_after_pct + mem_after_pct + bw_after_pct) / 3))

    cpu_after_used_pct = ((state_node.get("cpu_used", 0) + req_cpu) / cap["CPU"] * 100) if cap["CPU"] else 100
    mem_after_used_pct = ((state_node.get("mem_used", 0) + req_mem) / cap["MEM"] * 100) if cap["MEM"] else 100
    bw_after_used_pct = ((state_node.get("bw_used", 0) + req_bw) / cap["BW"] * 100) if cap["BW"] else 100
    projected_load = (cpu_after_used_pct + mem_after_used_pct + bw_after_used_pct) / 3
    load_balance_score = max(0, min(100, 100 - projected_load))

    latency_score = max(0, min(100, 100 - (lat / qos_latency * 100))) if qos_latency else max(0, 100 - lat)

    demand_ratio = max(
        req_cpu / cap["CPU"] if cap["CPU"] else 1,
        req_mem / cap["MEM"] if cap["MEM"] else 1,
        req_bw / cap["BW"] if cap["BW"] else 1,
    )
    if size == "light":
        fit_score = max(0, 100 - abs(demand_ratio - 0.45) * 140)
    elif size == "heavy":
        fit_score = max(0, 100 - abs(demand_ratio - 0.60) * 90)
    else:
        fit_score = max(0, 100 - abs(demand_ratio - 0.50) * 110)

    type_score = 100
    if size == "light" and node_info["node_type"] == "gateway":
        type_score = 110
    elif size == "heavy" and node_info["node_type"] != "computing":
        type_score = 0
    elif size == "heavy" and cap["CPU"] < max(req_cpu * 1.25, 8):
        type_score = 25

    score = (
        latency_score * SCORE_WEIGHTS["latency"]
        + available_score * SCORE_WEIGHTS["available"]
        + load_balance_score * SCORE_WEIGHTS["load_balance"]
        + fit_score * SCORE_WEIGHTS["fit"]
        + type_score * SCORE_WEIGHTS["type"]
    )
    return round(score, 2)


def apply_rules(required: dict, qos_latency: float) -> dict:
    eligible = []
    rejected = []
    size = workload_size(required)

    for nd in nodes:
        node_info = get_free_resources(nd["id"])
        if not node_info:
            continue

        ok, reason = check_rule(node_info, required, qos_latency)
        if ok:
            score = compute_score(node_info, required, qos_latency)
            eligible.append({
                "node_id": nd["id"],
                "node_type": nd["type"],
                "score": score,
                "workload": size,
                "free": node_info["free"],
                "pct": node_info["pct"],
                "cap": node_info["cap"],
                "lat": node_info["lat"],
                "reason": "OK",
            })
        else:
            rejected.append({"node_id": nd["id"], "reason": reason})

    eligible.sort(key=lambda x: x["score"], reverse=True)
    best = eligible[0]["node_id"] if eligible else None

    print(f"\n   Placement rules: request={required}, qos={qos_latency}ms, workload={size}")
    print(f"   Candidates: {len(eligible)} eligible, {len(rejected)} rejected")
    if best:
        print(f"   Best node: {best.upper()} (score={eligible[0]['score']})")
        print("   Top eligible:")
        for n in eligible[:5]:
            print(
                f"      {n['node_id'].upper()} score={n['score']} "
                f"type={n['node_type']} free={n['free']} lat={n['lat']}ms"
            )
    else:
        print("   No node satisfies strict rules")
    if rejected:
        print("   Top rejected:")
        for n in rejected[:5]:
            print(f"      {n['node_id'].upper()} -> {n['reason']}")

    return {
        "eligible": eligible,
        "rejected": rejected,
        "best": best,
        "rule_fired": best is not None,
    }


def rules_summary(result: dict) -> str:
    lines = []
    if result["eligible"]:
        lines.append(f"Eligible nodes ({len(result['eligible'])}):")
        for n in result["eligible"][:5]:
            lines.append(
                f"  - {n['node_id'].upper()} score={n['score']} "
                f"CPU={n['free']['CPU']} MEM={n['free']['MEM']} "
                f"BW={n['free']['BW']} lat={n['lat']}ms"
            )
    else:
        lines.append("No eligible node under strict rules.")
        lines.append(f"Rejected nodes ({len(result['rejected'])}):")
        for n in result["rejected"][:5]:
            lines.append(f"  - {n['node_id'].upper()} -> {n['reason']}")
    return "\n".join(lines)
