import unittest

from fastapi.testclient import TestClient

from backend.app.api.main import create_app


class FakeDashboard:
    def snapshot(self):
        return {
            "graph": {"nodes": 10, "relationships": 12},
            "quality": {"blind_result_accuracy": 0.615},
        }


class FakeGraph:
    def search_nodes(self, label, query, limit):
        if label == "Anything":
            raise ValueError("지원하지 않는 노드 라벨입니다: Anything")
        return {
            "label": label,
            "query": query,
            "identity_property": "part_id",
            "nodes": [
                {
                    "id": "node-1",
                    "labels": [label],
                    "properties": {
                        "part_id": "300002",
                        "part_type": "cylinder",
                    },
                }
            ],
            "count": 1,
        }

    def subgraph(self, label, identity, depth, limit):
        return {
            "root": {
                "id": "node-1",
                "labels": [label],
                "properties": {"part_id": identity},
            },
            "nodes": [
                {
                    "id": "node-1",
                    "labels": [label],
                    "properties": {"part_id": identity},
                }
            ],
            "relationships": [],
            "node_count": 1,
            "relationship_count": 0,
            "depth": depth,
            "truncated": False,
        }


class FakeFeedback:
    def __init__(self):
        self.events = []

    def record_review(self, **payload):
        event = {
            "review_id": "review-1",
            "timestamp": "2026-07-27T12:00:00+00:00",
            "query_fingerprint": "a" * 64,
            **payload,
        }
        self.events.append(event)
        return event

    def summary(self):
        return {
            "total_reviews": len(self.events),
            "unique_queries_reviewed": len(self.events),
            "decision_counts": {
                "verified": sum(
                    event["decision"] == "verified"
                    for event in self.events
                ),
                "disputed": 0,
                "needs_followup": 0,
            },
            "recent": list(reversed(self.events)),
            "storage": "append-only-jsonl",
        }


class FakeBundle:
    provider = "gold"
    model_name = "gold-lookup"

    def __init__(self):
        self.dashboard = FakeDashboard()
        self.graph = FakeGraph()
        self.feedback = FakeFeedback()
        self.closed = False

    def query_with_fallback(self, question):
        return {
            "question": question,
            "answer": "조회 결과 1행입니다.",
            "status": "success",
            "cypher": "MATCH (part:Part) RETURN part LIMIT 1",
            "rows": [{"part_id": "300002"}],
            "row_count": 1,
            "evidence": {
                "nodes": [],
                "relationships": [],
                "node_count": 0,
                "relationship_count": 0,
            },
            "validation": {
                "attempts": 1,
                "errors": [],
                "trace": [],
                "elapsed_ms": 1,
            },
            "usage": {},
            "caveat": None,
            "provider": self.provider,
        }

    def close(self):
        self.closed = True


class ApiContractTest(unittest.TestCase):
    def setUp(self):
        self.bundle = FakeBundle()
        self.client_context = TestClient(
            create_app(bundle_factory=lambda: self.bundle)
        )
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)

    def test_live_and_schema_do_not_require_database_queries(self):
        live = self.client.get("/api/v1/health/live")
        self.assertEqual(live.status_code, 200)
        self.assertEqual(live.json(), {"status": "alive"})
        self.assertEqual(
            live.headers["x-content-type-options"], "nosniff"
        )
        self.assertEqual(live.headers["x-frame-options"], "DENY")
        self.assertEqual(live.headers["cache-control"], "no-store")

        schema = self.client.get("/api/v1/graph/schema")
        self.assertEqual(schema.status_code, 200)
        self.assertIn("Part", {
            row["label"] for row in schema.json()["node_identities"]
        })
        self.assertIn(
            "ASSEMBLED_FROM", schema.json()["relationship_types"]
        )

    def test_query_contract_exposes_cypher_rows_and_evidence(self):
        response = self.client.post(
            "/api/v1/query",
            json={"question": "완제품 300002를 보여줘."},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["row_count"], 1)
        self.assertTrue(body["cypher"].startswith("MATCH"))
        self.assertIn("evidence", body)

    def test_query_rejects_empty_input(self):
        response = self.client.post(
            "/api/v1/query", json={"question": ""}
        )
        self.assertEqual(response.status_code, 422)
        whitespace = self.client.post(
            "/api/v1/query", json={"question": "   "}
        )
        self.assertEqual(whitespace.status_code, 422)

    def test_metrics_and_bounded_subgraph_contracts(self):
        metrics = self.client.get("/api/v1/metrics")
        self.assertEqual(metrics.status_code, 200)
        self.assertEqual(metrics.json()["graph"]["nodes"], 10)

        subgraph = self.client.get(
            "/api/v1/graph/subgraph",
            params={
                "label": "Cylinder",
                "identity": "300002",
                "depth": 2,
            },
        )
        self.assertEqual(subgraph.status_code, 200)
        self.assertEqual(subgraph.json()["node_count"], 1)

        invalid = self.client.get(
            "/api/v1/graph/subgraph",
            params={"label": "Anything", "identity": "x"},
        )
        self.assertEqual(invalid.status_code, 422)

    def test_search_nodes_by_partial_value(self):
        response = self.client.get(
            "/api/v1/graph/search",
            params={"label": "Cylinder", "q": "3000"},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["identity_property"], "part_id")
        self.assertEqual(
            body["nodes"][0]["properties"]["part_id"], "300002"
        )

        invalid = self.client.get(
            "/api/v1/graph/search",
            params={"label": "Anything", "q": "x"},
        )
        self.assertEqual(invalid.status_code, 422)

        whitespace = self.client.get(
            "/api/v1/graph/search",
            params={"label": "Cylinder", "q": "   "},
        )
        self.assertEqual(whitespace.status_code, 422)

    def test_domain_expert_feedback_is_recorded_and_summarized(self):
        response = self.client.post(
            "/api/v1/feedback",
            json={
                "question": "완제품 300002의 공정 이력을 보여줘.",
                "cypher": "MATCH (part:Part) RETURN part LIMIT 1",
                "query_status": "success",
                "provider": "gemini",
                "row_count": 1,
                "decision": "verified",
                "reviewer": "quality-engineer",
                "note": "원장과 대조 완료",
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["decision"], "verified")

        summary = self.client.get("/api/v1/feedback/summary")
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.json()["total_reviews"], 1)
        self.assertEqual(
            summary.json()["decision_counts"]["verified"], 1
        )

        invalid = self.client.post(
            "/api/v1/feedback",
            json={
                "question": "질문",
                "decision": "approved",
            },
        )
        self.assertEqual(invalid.status_code, 422)

    def test_bundle_is_closed_on_shutdown(self):
        separate_bundle = FakeBundle()
        with TestClient(
            create_app(bundle_factory=lambda: separate_bundle)
        ) as client:
            client.post(
                "/api/v1/query",
                json={"question": "완제품 300002를 보여줘."},
            )
            self.assertFalse(separate_bundle.closed)
        self.assertTrue(separate_bundle.closed)


if __name__ == "__main__":
    unittest.main()
