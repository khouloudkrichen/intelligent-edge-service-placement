import unittest

from core.placement_cache import (
    node_state_fingerprint,
    normalize_command,
    placement_cache_key,
    placement_cache_value,
)


class PlacementCacheTests(unittest.TestCase):
    def setUp(self):
        self.nodes = [
            {
                "id": "g1",
                "cpu_used": 0,
                "mem_used": 0,
                "disk_used": 0,
                "bw_used": 0,
            },
            {
                "id": "n1",
                "cpu_used": 2,
                "mem_used": 4,
                "disk_used": 1,
                "bw_used": 80,
            },
        ]

    def test_normalizes_equivalent_commands(self):
        self.assertEqual(
            normalize_command("  Detect MOTOR anomalies! "),
            normalize_command("detect motor anomalies"),
        )

    def test_fingerprint_is_order_independent(self):
        self.assertEqual(
            node_state_fingerprint(self.nodes),
            node_state_fingerprint(list(reversed(self.nodes))),
        )

    def test_key_changes_when_resources_change(self):
        before = placement_cache_key("detect motor anomalies", self.nodes)
        changed = [dict(node) for node in self.nodes]
        changed[0]["cpu_used"] = 1
        after = placement_cache_key("detect motor anomalies", changed)
        self.assertNotEqual(before, after)

    def test_cached_value_is_minimal_and_serializable(self):
        value = placement_cache_value(
            intent_ids=["i46"],
            command_summary="detect motor anomalies",
            per_intention=[{"id": "i46", "status": "PLACED"}],
            node="n3",
            latency=70.0,
            services=["s5", "s6"],
            response="The services are already placed.",
        )
        self.assertEqual(value["intent_ids"], ["i46"])
        self.assertEqual(value["node"], "n3")
        self.assertNotIn("nodes", value)


if __name__ == "__main__":
    unittest.main()
