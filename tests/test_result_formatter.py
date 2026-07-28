import unittest

from backend.app.services.result_formatter import (
    build_evidence_graph,
    format_agent_result,
)


class ResultFormatterTest(unittest.TestCase):
    def test_success_response_uses_only_returned_values(self):
        state = {
            "question": "완제품 이력을 보여줘",
            "statement": "MATCH ...",
            "records": [
                {
                    "cylinder_id": "300002",
                    "component_id": "103504",
                    "component_type": "cylinder_bottom",
                    "process_runs": [
                        {
                            "run_id": "103504:saw:0",
                            "process_name": "saw",
                            "equipment": "Kasto SBA 2",
                            "anomaly_code": "0",
                            "anomaly_name": "Normal process",
                        }
                    ],
                    "quality_measurements": [
                        {
                            "measurement_id": (
                                "103504:cnc_milling_machine:"
                                "surface_roughness:0"
                            ),
                            "process_name": "cnc_milling_machine",
                            "feature": "surface_roughness",
                            "value": "4.3",
                            "qc_pass": False,
                        }
                    ],
                }
            ],
            "status": "success",
            "attempts": 1,
            "errors": [],
            "trace": [{"step": "execute_cypher"}],
            "elapsed_ms": 20,
        }
        result = format_agent_result(state)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["row_count"], 1)
        self.assertIn("300002", result["answer"])
        self.assertIn("103504", result["answer"])

        node_ids = {node["id"] for node in result["evidence"]["nodes"]}
        self.assertIn("Cylinder:300002", node_ids)
        self.assertIn("CylinderBottom:103504", node_ids)
        self.assertIn("ProcessRun:103504:saw:0", node_ids)
        self.assertIn("Equipment:Kasto SBA 2", node_ids)
        relationship_types = {
            relationship["type"]
            for relationship in result["evidence"]["relationships"]
        }
        self.assertTrue(
            {
                "ASSEMBLED_FROM",
                "UNDERWENT",
                "INSTANCE_OF",
                "RUN_ON",
                "CLASSIFIED_AS",
                "HAS_MEASUREMENT",
                "FOR_PROCESS",
            }.issubset(relationship_types)
        )

    def test_response_exposes_versioned_provenance_and_verification(self):
        statement_hash = "a" * 64
        result = format_agent_result(
            {
                "question": "전체 건수를 알려줘",
                "statement": "RETURN 1 AS count",
                "records": [{"count": 1}],
                "status": "success",
                "attempts": 1,
                "errors": [],
                "validated_statement_sha256": statement_hash,
                "metadata": {
                    "project_id": "equipment-history",
                    "schema_version": "1.0",
                    "prompt_version": "text2cypher-v1",
                },
                "trace": [
                    {
                        "step": "execute_cypher",
                        "executed": True,
                        "verified_statement_sha256": statement_hash,
                    }
                ],
                "elapsed_ms": 5,
            }
        )
        self.assertEqual(
            result["metadata"]["project_id"],
            "equipment-history",
        )
        self.assertEqual(
            result["evidence"]["provenance"]["schema_version"],
            "1.0",
        )
        self.assertTrue(result["validation"]["execution_verified"])

    def test_empty_response_has_no_evidence_or_invented_entity(self):
        result = format_agent_result(
            {
                "question": "없는 제품",
                "statement": "MATCH ...",
                "records": [],
                "status": "empty",
                "attempts": 1,
                "errors": [],
                "trace": [],
                "elapsed_ms": 10,
            }
        )
        self.assertEqual(
            result["answer"], "조건에 해당하는 데이터를 찾지 못했습니다."
        )
        self.assertEqual(result["evidence"]["nodes"], [])
        self.assertEqual(result["evidence"]["relationships"], [])

    def test_blocked_response_does_not_expose_evidence(self):
        result = format_agent_result(
            {
                "question": "삭제해줘",
                "statement": "",
                "records": [],
                "status": "blocked",
                "attempts": 0,
                "errors": ["WRITE_REQUEST"],
                "trace": [],
                "elapsed_ms": 0,
            }
        )
        self.assertEqual(result["status"], "blocked")
        self.assertIn("실행하지 않았습니다", result["answer"])
        self.assertEqual(result["evidence"]["node_count"], 0)

    def test_ambiguous_response_requests_specific_conditions(self):
        result = format_agent_result(
            {
                "question": "문제 있는 부품 찾아줘.",
                "statement": "",
                "records": [],
                "status": "needs_clarification",
                "attempts": 0,
                "errors": ["AMBIGUOUS_REQUEST"],
                "trace": [],
                "elapsed_ms": 0,
            }
        )
        self.assertEqual(result["status"], "needs_clarification")
        self.assertIn("부품 종류", result["answer"])
        self.assertEqual(result["evidence"]["node_count"], 0)

    def test_gold_unsupported_response_explains_provider_switch(self):
        result = format_agent_result(
            {
                "question": "새 질문",
                "statement": "",
                "records": [],
                "status": "unsupported",
                "attempts": 0,
                "errors": ["GOLD_UNSUPPORTED"],
                "trace": [],
                "elapsed_ms": 0,
            }
        )
        self.assertEqual(result["status"], "unsupported")
        self.assertIn("Vertex Gemini", result["answer"])

    def test_aggregate_rows_do_not_invent_relationships(self):
        evidence = build_evidence_graph(
            [
                {
                    "equipment": "DMC 50H",
                    "run_count": 846,
                    "anomaly_code": "2",
                }
            ]
        )
        self.assertEqual(evidence["relationship_count"], 0)
        self.assertEqual(
            {node["id"] for node in evidence["nodes"]},
            {"Equipment:DMC 50H", "AnomalyClass:2"},
        )

    def test_equipment_history_rows_build_relationship_evidence(self):
        evidence = build_evidence_graph(
            [
                {
                    "equipment_id": "EQ-PRESS-01",
                    "event_id": "ME-008",
                    "event_date": "2026-03-18",
                    "event_type": "replacement",
                    "component": "hydraulic_pump",
                    "cost_usd": 4200,
                    "technician_id": "T-01",
                    "technician_name": "Kim",
                }
            ]
        )
        self.assertEqual(
            {node["id"] for node in evidence["nodes"]},
            {
                "Equipment:EQ-PRESS-01",
                "MaintenanceEvent:ME-008",
                "Technician:T-01",
            },
        )
        self.assertEqual(
            {
                relationship["type"]
                for relationship in evidence["relationships"]
            },
            {"HAS_MAINTENANCE", "PERFORMED"},
        )

    def test_evidence_size_is_bounded(self):
        evidence = build_evidence_graph(
            [{"part_id": str(index)} for index in range(10)],
            max_nodes=3,
        )
        self.assertEqual(evidence["node_count"], 3)
        self.assertTrue(evidence["truncated"]["nodes"])


if __name__ == "__main__":
    unittest.main()
