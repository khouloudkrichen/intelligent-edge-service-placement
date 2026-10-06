# core/placement.py - placement engine with graceful degradation

import random
import time
import json

from data.dataset import (
    INTENTION_REQUIREMENTS,
    NODE_AVG_LATENCY,
    SERVICE_REQUIREMENTS,
    SERVICES_BY_ID,
    nodes,
    latency_map,
)
from core.nodes import get_node_state, get_available
from services.cache import get_cache

PLACED = "PLACED"
DEGRADED = "DEGRADED"
PARTIAL = "PARTIAL"
FAILED = "FAILED"

DEGRADED_LATENCY_FACTOR = 1.25
DEGRADED_BW_FACTOR = 0.85

# Lower number means higher priority. Heavy visual/optional services are later.
SERVICE_PRIORITY = {
    "s1": 1,  # voice converter
    "s2": 1,  # protocol/status/logs
    "s5": 2,  # error detector
    "s6": 2,  # anomaly analyzer
    "s4": 3,  # content display
    "s3": 4,  # AR generator, usually heavy/optional
}


def total_resources(service_ids: list) -> dict:
    total = {"CPU": 0, "MEM": 0, "DISK": 0, "BW": 0}
    for sid in service_ids:
        req = SERVICE_REQUIREMENTS.get(sid)
        if req:
            for r in total:
                total[r] += req.get(r, 0)
    return total


def resources_for_intention(intent: dict) -> dict:
    cache_key = json.dumps(
        {"id": intent.get("id"), "services": intent.get("services", [])},
        sort_keys=True,
    )
    cached = get_cache().get_json("intention_resources", cache_key)
    if cached is not None:
        return dict(cached)
    required = INTENTION_REQUIREMENTS.get(intent.get("id"))
    resources = dict(required) if required else total_resources(intent.get("services", []))
    get_cache().set_json("intention_resources", cache_key, resources)
    return resources


def service_priority(service_id: str) -> int:
    return SERVICE_PRIORITY.get(service_id, 9)


def priority_services(service_ids: list) -> list:
    return sorted(service_ids, key=lambda sid: (service_priority(sid), sid))


def _result(service, node, lat, grouped, source, status, **extra):
    return {
        "service": service,
        "node": node,
        "lat": lat,
        "grouped": grouped,
        "source": source,
        "status": status,
        **extra,
    }


def _overall_status(results: list) -> str:
    placed = [r for r in results if r.get("node")]
    if not placed:
        return FAILED
    if len(placed) < len(results):
        return PARTIAL
    if any(r.get("status") == DEGRADED for r in placed):
        return DEGRADED
    return PLACED


def best_node_for(required: dict, qos_latency: float) -> tuple:
    best_node, best_lat = None, 9999.0
    for nd in nodes:
        avail = get_available(nd["id"])
        if not avail:
            continue
        if not all(avail.get(r, 0) >= required[r] for r in required):
            continue
        avg_lat = NODE_AVG_LATENCY.get(nd["id"])
        if avg_lat is None:
            continue
        if avg_lat <= qos_latency and avg_lat < best_lat:
            best_lat = avg_lat
            best_node = nd["id"]
    return best_node, round(best_lat, 1) if best_node else None


def apply_service_to_node(node_id: str, req: dict):
    nd = get_node_state(node_id)
    if not nd:
        raise ValueError(f"Cannot apply placement: unknown node {node_id}")

    available = {
        "CPU": nd["cpu"] - nd["cpu_used"],
        "MEM": nd["mem"] - nd["mem_used"],
        "DISK": nd["disk"] - nd["disk_used"],
        "BW": nd["bw"] - nd["bw_used"],
    }
    missing = [r for r in req if available.get(r, 0) < req[r]]
    if missing:
        raise ValueError(
            f"Cannot apply placement on {node_id}: insufficient {missing}, "
            f"available={available}, required={req}"
        )

    nd["cpu_used"] += req["CPU"]
    nd["mem_used"] += req["MEM"]
    nd["disk_used"] += req["DISK"]
    nd["bw_used"] += req["BW"]
    nd["active"] = True
    lats = latency_map.get(node_id, [50])
    nd["lat"] = round(sum(lats) / len(lats) + random.uniform(-2, 4), 1)


def select_node(required: dict, qos_latency: float, service_ids: list, intent_desc: str = "") -> list:
    from core.rules import apply_rules

    scoring_start = time.perf_counter()
    ordered_services = priority_services(service_ids)
    print(f"\n   Placement request: services={service_ids}, priority={ordered_services}")
    print(f"   Required={required}, qos={qos_latency}ms")

    print("   Step 1 - strict grouped placement")
    strict_group = apply_rules(required, qos_latency)
    print(f"   Timing scoring strict grouped: {round((time.perf_counter() - scoring_start) * 1000, 2)}ms")
    if strict_group["rule_fired"]:
        top = strict_group["eligible"][0]
        best = strict_group["best"]
        print(f"   Status {PLACED}: strict grouped -> {best.upper()} (score={top['score']})")
        return [_result("ALL", best, top["lat"], True, "rules", PLACED)]

    print("   Strict grouped failed; reasons:")
    for r in strict_group["rejected"][:5]:
        print(f"      {r['node_id'].upper()} -> {r['reason']}")

    print("   Step 2 - strict distributed placement")
    distributed_start = time.perf_counter()
    distributed = _distributed_place(ordered_services, qos_latency, degraded=False)
    print(f"   Timing scoring strict distributed: {round((time.perf_counter() - distributed_start) * 1000, 2)}ms")
    distributed_status = _overall_status(distributed)
    if distributed_status == PLACED:
        print(f"   Status {PLACED}: all services placed with strict distributed rules")
        return distributed

    print("   Strict distributed failed; unresolved services:")
    for r in distributed:
        if not r.get("node"):
            print(f"      skipped {r['service']} -> {r.get('reason', 'no strict node')}")

    print("   Step 3 - degraded grouped placement")
    degraded_group_start = time.perf_counter()
    degraded_group = _degraded_grouped(required, qos_latency)
    print(f"   Timing scoring degraded grouped: {round((time.perf_counter() - degraded_group_start) * 1000, 2)}ms")
    if degraded_group:
        print(
            f"   Status {DEGRADED}: grouped placement accepted with tolerance "
            f"{degraded_group.get('tolerance')}"
        )
        return [degraded_group]

    print("   Step 4 - degraded distributed placement")
    degraded_dist_start = time.perf_counter()
    degraded_distributed = _distributed_place(ordered_services, qos_latency, degraded=True)
    print(f"   Timing scoring degraded distributed: {round((time.perf_counter() - degraded_dist_start) * 1000, 2)}ms")
    degraded_status = _overall_status(degraded_distributed)
    if degraded_status in {PLACED, DEGRADED}:
        print(f"   Status {DEGRADED}: all services placed with degraded tolerance")
        return [{**r, "status": DEGRADED if r.get("node") else FAILED} for r in degraded_distributed]

    print("   Step 5 - partial priority placement")
    partial = degraded_distributed
    placed = [r for r in partial if r.get("node")]
    skipped = [r for r in partial if not r.get("node")]
    if placed:
        print(f"   Status {PARTIAL}: deployed critical feasible services first")
        print(f"   Skipped services in PARTIAL mode: {[r['service'] for r in skipped]}")
        return [{**r, "status": PARTIAL if r.get("node") else FAILED} for r in partial]

    print(f"   Status {FAILED}: no meaningful service could be deployed")
    return [_result(sid, None, None, False, "failed", FAILED, reason="No feasible strict/degraded placement")
            for sid in ordered_services]


def _distributed_place(service_ids: list, qos_latency: float, degraded: bool) -> list:
    from core.rules import apply_rules

    results = []
    reserved_by_node = {}
    for svc_id in service_ids:
        svc_req = SERVICE_REQUIREMENTS.get(svc_id)
        if not svc_req:
            results.append(_result(svc_id, None, None, False, "unknown_service", FAILED, reason="Unknown service"))
            continue

        req = dict(svc_req)
        print(f"   Service {svc_id} priority={service_priority(svc_id)} required={req}")
        if degraded:
            chosen = _find_degraded_node(req, qos_latency, reserved_by_node)
            if chosen:
                node_id, lat, tolerance, allocated = chosen
                _reserve(reserved_by_node, node_id, allocated)
                print(f"      degraded -> {node_id.upper()} ({lat}ms), tolerance={tolerance}")
                results.append(_result(
                    svc_id, node_id, lat, False, "degraded_distributed", DEGRADED,
                    tolerance=tolerance, allocated=allocated,
                ))
            else:
                results.append(_result(
                    svc_id, None, None, False, "failed", FAILED,
                    reason="No node can host service even with degradation",
                ))
            continue

        rules = apply_rules(req, qos_latency)
        if not rules["rule_fired"]:
            results.append(_result(
                svc_id, None, None, False, "failed", FAILED,
                reason="No strict node for service",
            ))
            continue

        chosen = _first_reservable(rules["eligible"], req, reserved_by_node)
        if not chosen:
            results.append(_result(
                svc_id, None, None, False, "failed_capacity", FAILED,
                reason="Strict candidates overcommitted by previous service reservations",
            ))
            continue

        _reserve(reserved_by_node, chosen["node_id"], req)
        results.append(_result(
            svc_id, chosen["node_id"], chosen["lat"], False, "rules_distributed", PLACED,
        ))

    return results


def _degraded_grouped(required: dict, qos_latency: float) -> dict | None:
    chosen = _find_degraded_node(required, qos_latency, reserved_by_node={})
    if not chosen:
        print(
            f"   Degraded grouped failed: tolerance latency<=x{DEGRADED_LATENCY_FACTOR}, "
            f"bandwidth>={int(DEGRADED_BW_FACTOR * 100)}%, hard CPU/MEM/DISK still required"
        )
        return None
    node_id, lat, tolerance, allocated = chosen
    return _result(
        "ALL", node_id, lat, True, "degraded_rules", DEGRADED,
        tolerance=tolerance, allocated=allocated,
    )


def _find_degraded_node(required: dict, qos_latency: float, reserved_by_node: dict) -> tuple | None:
    candidates = []
    for nd in nodes:
        state_node = get_node_state(nd["id"])
        if not state_node:
            continue

        reserved = reserved_by_node.get(nd["id"], {"CPU": 0, "MEM": 0, "DISK": 0, "BW": 0})
        free = {
            "CPU": state_node["cpu"] - state_node["cpu_used"] - reserved["CPU"],
            "MEM": state_node["mem"] - state_node["mem_used"] - reserved["MEM"],
            "DISK": state_node["disk"] - state_node["disk_used"] - reserved["DISK"],
            "BW": state_node["bw"] - state_node["bw_used"] - reserved["BW"],
        }
        hard_ok = (
            free["CPU"] >= required.get("CPU", 0)
            and free["MEM"] >= required.get("MEM", 0)
            and free["DISK"] >= required.get("DISK", 0)
        )
        if not hard_ok:
            continue

        required_bw = required.get("BW", 0)
        bw_ok = free["BW"] >= required_bw
        bw_degraded_ok = free["BW"] >= required_bw * DEGRADED_BW_FACTOR
        if not (bw_ok or bw_degraded_ok):
            continue

        lat = NODE_AVG_LATENCY.get(nd["id"], 50)
        lat_ok = lat <= qos_latency
        lat_degraded_ok = lat <= qos_latency * DEGRADED_LATENCY_FACTOR
        if not (lat_ok or lat_degraded_ok):
            continue

        tolerance = []
        allocated = dict(required)
        penalty = 0
        if not lat_ok:
            tolerance.append(f"latency {lat}ms <= {round(qos_latency * DEGRADED_LATENCY_FACTOR, 1)}ms")
            penalty += 25
        if not bw_ok:
            tolerance.append(f"bandwidth {free['BW']} >= {round(required_bw * DEGRADED_BW_FACTOR, 1)}")
            allocated["BW"] = free["BW"]
            penalty += 35

        cpu_after = free["CPU"] - required.get("CPU", 0)
        score = cpu_after * 10 + free["MEM"] + free["BW"] / 10 - lat / 3 - penalty
        candidates.append((score, nd["id"], lat, tolerance or ["none"], allocated))

    if not candidates:
        return None
    candidates.sort(reverse=True)
    score, node_id, lat, tolerance, allocated = candidates[0]
    print(f"   Degraded candidates considered: {[(c[1].upper(), round(c[0], 2), c[3]) for c in candidates[:5]]}")
    return node_id, lat, tolerance, allocated


def _first_reservable(eligible: list, req: dict, reserved_by_node: dict) -> dict | None:
    for candidate in eligible:
        node_id = candidate["node_id"]
        nd = get_node_state(node_id)
        reserved = reserved_by_node.get(node_id, {"CPU": 0, "MEM": 0, "DISK": 0, "BW": 0})
        available = {
            "CPU": nd["cpu"] - nd["cpu_used"] - reserved["CPU"],
            "MEM": nd["mem"] - nd["mem_used"] - reserved["MEM"],
            "DISK": nd["disk"] - nd["disk_used"] - reserved["DISK"],
            "BW": nd["bw"] - nd["bw_used"] - reserved["BW"],
        }
        if all(available[k] >= req[k] for k in req):
            return candidate
    return None


def _reserve(reserved_by_node: dict, node_id: str, req: dict):
    used = reserved_by_node.setdefault(node_id, {"CPU": 0, "MEM": 0, "DISK": 0, "BW": 0})
    for k in used:
        used[k] += req[k]


def apply_placement(intent: dict, results: list):
    for r in results:
        if not r["node"]:
            continue
        if r.get("grouped"):
            apply_service_to_node(r["node"], r.get("allocated") or total_resources(intent["services"]))
        else:
            svc_id = r.get("service")
            svc_req = SERVICE_REQUIREMENTS.get(svc_id)
            if svc_req:
                apply_service_to_node(r["node"], r.get("allocated") or svc_req)

        nd = get_node_state(r["node"])
        if nd and intent["id"] not in nd["intents"]:
            nd["intents"].append(intent["id"])


def place_intention_batch(intents: list[dict]) -> list[dict]:
    """Plan and apply all intentions from one command in sequence.

    Each returned item keeps the existing per-intention placement result shape,
    so WebSocket/history/UI payloads stay compatible.
    """
    batch_start = time.perf_counter()
    batch_results = []

    print(f"\n   Batch placement: {len(intents)} intention(s)")
    for intent in intents:
        item_start = time.perf_counter()
        required = resources_for_intention(intent)
        print(
            f"   Batch item {intent['id']}: cached resources="
            f"CPU={required['CPU']} MEM={required['MEM']} "
            f"DISK={required['DISK']} BW={required['BW']}"
        )

        scoring_start = time.perf_counter()
        results = select_node(
            required,
            intent["QoS"]["latency"],
            intent["services"],
            intent_desc=intent["description"],
        )
        scoring_ms = round((time.perf_counter() - scoring_start) * 1000, 2)

        placed = [r for r in results if r.get("node")]
        placement_ms = 0.0
        if placed:
            placement_start = time.perf_counter()
            apply_placement(intent, results)
            placement_ms = round((time.perf_counter() - placement_start) * 1000, 2)

        total_ms = round((time.perf_counter() - item_start) * 1000, 2)
        print(
            f"   Timing {intent['id']}: scoring={scoring_ms}ms, "
            f"placement={placement_ms}ms, total={total_ms}ms"
        )
        batch_results.append({
            "intent": intent,
            "required": required,
            "results": results,
            "placed": placed,
            "failed": [r for r in results if not r.get("node")],
            "scoring_ms": scoring_ms,
            "placement_ms": placement_ms,
            "total_ms": total_ms,
        })

    print(f"   Timing batch placement total: {round((time.perf_counter() - batch_start) * 1000, 2)}ms")
    return batch_results
