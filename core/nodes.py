# ═══════════════════════════════════════════════════════
# core/nodes.py — État global des nœuds + helpers
# ═══════════════════════════════════════════════════════

from data.dataset import nodes, latency_map, NODES_BY_ID

# ── État partagé ────────────────────────────────────────
state = {
    "nodes":      [],
    "placements": [],
    "listening":  False,
    "last_text":  "",
    "last_intent":"",
    "last_node":  "",
    "stats": {"total": 0, "success": 0, "fail": 0},
}


def init_nodes(reset_load: bool = True):
    """Initialise (ou réinitialise) la liste des nœuds dans state."""
    if not reset_load and state["nodes"]:
        return
    state["nodes"] = []
    for nd in nodes:
        lats = latency_map.get(nd["id"], [50])
        state["nodes"].append({
            "id":        nd["id"],
            "type":      nd["type"],
            "cpu":       nd["capacity"]["CPU"],
            "mem":       nd["capacity"]["MEM"],
            "disk":      nd["capacity"]["DISK"],
            "bw":        nd["capacity"]["BW"],
            "cpu_used":  0,
            "mem_used":  0,
            "disk_used": 0,
            "bw_used":   0,
            "lat":       round(sum(lats) / len(lats), 1),
            "lat_min":   round(min(lats), 1),
            "lat_max":   round(max(lats), 1),
            "intents":   [],
            "active":    False,
        })


def get_node_state(node_id: str) -> dict | None:
    return next((n for n in state["nodes"] if n["id"] == node_id), None)


def get_available(node_id: str) -> dict | None:
    nd_s = get_node_state(node_id)
    nd_c = NODES_BY_ID.get(node_id)
    if not nd_s or not nd_c:
        return None
    return {
        "CPU":  nd_c["capacity"]["CPU"]  - nd_s["cpu_used"],
        "MEM":  nd_c["capacity"]["MEM"]  - nd_s["mem_used"],
        "DISK": nd_c["capacity"]["DISK"] - nd_s["disk_used"],
        "BW":   nd_c["capacity"]["BW"]   - nd_s["bw_used"],
    }


# Initialisation au démarrage
init_nodes()