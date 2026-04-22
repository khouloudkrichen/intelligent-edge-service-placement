# core/rules.py - strict placement validation and workload-aware scoring

from data.dataset import nodes, latency_map, NODES_BY_ID
from core.nodes import get_node_state

MIN_FREE_PCT = 20

SCORE_WEIGHTS = {
    "headroom": 0.40,
    "fit": 0.30,
    "lat": 0.20,
    "type": 0.10,
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
    lats = latency_map.get(node_id, [50])
    avg_lat = round(sum(lats) / len(lats), 1)
    return {
        "node_id": node_id,
        "node_type": nd_s["type"],
        "free": free,
        "pct": pct,
        "cap": cap,
        "lat": avg_lat,
    }


def check_rule(node_info: dict, required: dict, qos_latency: float) -> tuple[bool, str]:
    free = node_info["free"]
    cap = node_info["cap"]
    lat = node_info["lat"]

    req_cpu = required.get("CPU", 0)
    req_mem = required.get("MEM", 0)
    req_disk = required.get("DISK", 0)
    req_bw = required.get("BW", 0)

    if free["CPU"] < req_cpu:
        return False, f"CPU insufficient ({free['CPU']} < {req_cpu})"

    cpu_after = free["CPU"] - req_cpu
    cpu_min_free = round(cap["CPU"] * MIN_FREE_PCT / 100, 1)
    if cpu_after < cpu_min_free:
        return False, f"CPU margin too low after placement ({cpu_after} < {cpu_min_free})"

    if free["MEM"] < req_mem:
        return False, f"MEM insufficient ({free['MEM']} < {req_mem})"
    if free["DISK"] < req_disk:
        return False, f"DISK insufficient ({free['DISK']} < {req_disk})"
    if free["BW"] < req_bw:
        return False, f"BW insufficient ({free['BW']} < {req_bw})"
    if lat > qos_latency:
        return False, f"Latency too high ({lat}ms > {qos_latency}ms)"

    return True, "OK"


def compute_score(node_info: dict, required: dict) -> float:
    """Rank eligible nodes.

    Light requests prefer the smallest valid node with enough headroom.
    Heavy requests prefer strong computing nodes and higher remaining capacity.
    """
    lat = node_info["lat"]
    cap = node_info["cap"]
    free = node_info["free"]
    size = workload_size(required)

    req_cpu = required.get("CPU", 0)
    req_mem = required.get("MEM", 0)
    req_bw = required.get("BW", 0)

    cpu_after_pct = ((free["CPU"] - req_cpu) / cap["CPU"] * 100) if cap["CPU"] else 0
    mem_after_pct = ((free["MEM"] - req_mem) / cap["MEM"] * 100) if cap["MEM"] else 0
    bw_after_pct = ((free["BW"] - req_bw) / cap["BW"] * 100) if cap["BW"] else 0
    headroom_score = max(0, min(100, (cpu_after_pct + mem_after_pct + bw_after_pct) / 3))

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

    lat_score = max(0, 100 - lat)
    type_score = 100
    if size == "light" and node_info["node_type"] == "gateway":
        type_score = 110
    elif size == "heavy" and node_info["node_type"] != "computing":
        type_score = 0
    elif size == "heavy" and cap["CPU"] < max(req_cpu * 1.25, 8):
        type_score = 25

    score = (
        headroom_score * SCORE_WEIGHTS["headroom"]
        + fit_score * SCORE_WEIGHTS["fit"]
        + lat_score * SCORE_WEIGHTS["lat"]
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
            score = compute_score(node_info, required)
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
