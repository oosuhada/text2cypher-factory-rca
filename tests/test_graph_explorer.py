import unittest

from frontend.graph_explorer import (
    bound_evidence,
    build_visual_spec,
    graph_performance_policy,
    merge_catalog_payload,
    selected_entity_details,
    shortest_path_ids,
    validate_project_scope,
)


class GraphExplorerTest(unittest.TestCase):
    def setUp(self):
        self.evidence = {
            "root_id": "part-1",
            "nodes": [
                {
                    "id": "part-1",
                    "label": "Part",
                    "properties": {"part_id": "P-1"},
                },
                {
                    "id": "run-1",
                    "label": "ProcessRun",
                    "properties": {"run_id": "R-1"},
                },
                {
                    "id": "equipment-1",
                    "label": "Equipment",
                    "properties": {"equipment_id": "EQ-1"},
                },
            ],
            "relationships": [
                {
                    "id": "underwent-1",
                    "source": "part-1",
                    "target": "run-1",
                    "type": "UNDERWENT",
                    "properties": {},
                },
                {
                    "id": "run-on-1",
                    "source": "run-1",
                    "target": "equipment-1",
                    "type": "RUN_ON",
                    "properties": {},
                },
            ],
        }

    def test_shortest_path_and_visual_highlight_share_entity_ids(self):
        node_ids, relationship_ids = shortest_path_ids(
            self.evidence, "part-1", "equipment-1"
        )
        self.assertEqual(
            node_ids, {"part-1", "run-1", "equipment-1"}
        )
        self.assertEqual(
            relationship_ids, {"underwent-1", "run-on-1"}
        )
        visual = build_visual_spec(
            self.evidence,
            identity_by_label={
                "Part": "part_id",
                "ProcessRun": "run_id",
                "Equipment": "equipment_id",
            },
            root_id="part-1",
            selected_node_ids=["equipment-1"],
            highlighted_node_ids=node_ids,
            highlighted_relationship_ids=relationship_ids,
        )
        selected = next(
            node for node in visual["nodes"] if node["id"] == "equipment-1"
        )
        self.assertEqual(selected["color"], "#7C3AED")
        self.assertTrue(
            all(edge["width"] == 4 for edge in visual["relationships"])
        )

    def test_browser_selection_maps_back_to_domain_entities(self):
        details = selected_entity_details(
            self.evidence,
            selected_node_ids=["run-1"],
            selected_relationship_ids=["run-on-1"],
        )
        self.assertEqual(details["nodes"][0]["label"], "ProcessRun")
        self.assertEqual(
            details["relationships"][0]["type"], "RUN_ON"
        )

    def test_neighborhood_merge_is_deduplicated(self):
        current = {
            "root": {"id": "part-1"},
            "nodes": self.evidence["nodes"][:2],
            "relationships": self.evidence["relationships"][:1],
            "depth": 1,
            "truncated": False,
        }
        incoming = {
            "root": {"id": "run-1"},
            "nodes": self.evidence["nodes"][1:],
            "relationships": self.evidence["relationships"],
            "depth": 2,
            "truncated": True,
        }
        merged = merge_catalog_payload(current, incoming)
        self.assertEqual(merged["node_count"], 3)
        self.assertEqual(merged["relationship_count"], 2)
        self.assertEqual(merged["root"]["id"], "part-1")
        self.assertTrue(merged["truncated"])

    def test_cross_project_entities_are_rejected(self):
        payload = {
            "nodes": [
                {
                    "id": "node-1",
                    "properties": {"project_id": "other-project"},
                }
            ],
            "relationships": [],
        }
        with self.assertRaisesRegex(
            ValueError, "프로젝트 범위를 벗어난"
        ):
            validate_project_scope(payload, "equipment-history")
        validate_project_scope(payload, "cip-dmd")

    def test_performance_boundaries_are_explicit(self):
        one_thousand = graph_performance_policy(1_000)
        ten_thousand = graph_performance_policy(10_000)
        over_ten_thousand = graph_performance_policy(10_001)
        self.assertEqual(one_thousand.renderer, "canvas")
        self.assertFalse(one_thousand.sampling_required)
        self.assertEqual(ten_thousand.renderer, "webgl")
        self.assertTrue(ten_thousand.sampling_required)
        self.assertEqual(over_ten_thousand.recommended_limit, 1_000)

    def test_large_graph_bound_preserves_root_and_selected_node(self):
        evidence = {
            "root_id": "node-0",
            "nodes": [
                {
                    "id": f"node-{index}",
                    "label": "Part",
                    "properties": {},
                }
                for index in range(20)
            ],
            "relationships": [
                {
                    "id": f"rel-{index}",
                    "source": f"node-{index}",
                    "target": f"node-{index + 1}",
                    "type": "NEXT",
                    "properties": {},
                }
                for index in range(19)
            ],
        }
        bounded = bound_evidence(
            evidence, 5, priority_node_ids=["node-19"]
        )
        kept = {node["id"] for node in bounded["nodes"]}
        self.assertIn("node-0", kept)
        self.assertIn("node-19", kept)
        self.assertEqual(bounded["node_count"], 5)
        self.assertEqual(bounded["sampled_out_node_count"], 15)
        self.assertTrue(bounded["truncated"])
