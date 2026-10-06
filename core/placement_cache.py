"""Cache keys and payloads for replaying unchanged placement decisions."""

from __future__ import annotations

import hashlib
import json
import re

from config import DATASET_FILE


def normalize_command(text: str) -> str:
    lowered = (text or "").casefold()
    return re.sub(r"\s+", " ", re.sub(r"[^\w]+", " ", lowered)).strip()


def node_state_fingerprint(nodes: list[dict]) -> str:
    usage = [
        {
            "id": node.get("id"),
            "cpu_used": node.get("cpu_used", 0),
            "mem_used": node.get("mem_used", 0),
            "disk_used": node.get("disk_used", 0),
            "bw_used": node.get("bw_used", 0),
        }
        for node in sorted(nodes, key=lambda item: str(item.get("id", "")))
    ]
    raw = json.dumps(usage, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def placement_cache_key(summary: str, nodes: list[dict]) -> str:
    return (
        f"{DATASET_FILE}:"
        f"{normalize_command(summary)}:"
        f"{node_state_fingerprint(nodes)}"
    )


def placement_cache_value(
    *,
    intent_ids: list[str],
    command_summary: str,
    per_intention: list[dict],
    node: str | None,
    latency: float | None,
    services: list[str],
    response: str = "",
) -> dict:
    return {
        "intent_ids": list(intent_ids),
        "command_summary": command_summary,
        "per_intention": per_intention,
        "node": node,
        "lat": latency,
        "services": list(services),
        "response": response,
    }
