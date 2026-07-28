import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.api.main import ServiceRegistry, create_app
from backend.app.projects import ProjectRegistry


class FakeDashboard:
    def snapshot(self):
        return {
            "graph": {"nodes": 10, "relationships": 12},
            "quality": {"blind_result_accuracy": 0.615},
        }


class FakeGraph:
    def graph_counts(self, project_id=None):
        if project_id == "empty-project":
            return {"nodes": 0, "relationships": 0}
        return {"nodes": 10, "relationships": 12}

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


class FakeProjectGraphLoader:
    def load(self, project_id, upload_id):
        return {
            "project_id": project_id,
            "upload_id": upload_id,
            "status": "loaded",
            "integrity": {
                "scoped_node_count": 3,
                "scoped_relationship_count": 2,
                "project_scope_applied": True,
            },
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
        self.temp = tempfile.TemporaryDirectory()
        self.projects = ProjectRegistry(
            Path(self.temp.name) / "projects.sqlite3"
        )
        self.client_context = TestClient(
            create_app(
                bundle_factory=lambda: self.bundle,
                project_registry=self.projects,
                project_graph_loader=FakeProjectGraphLoader(),
            )
        )
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        self.temp.cleanup()

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
        self.assertEqual(schema.json()["project_id"], "cip-dmd")
        self.assertEqual(schema.json()["schema_version"], "1.1")
        runtime = self.client.get("/api/v1/runtime")
        self.assertEqual(runtime.status_code, 200)
        self.assertEqual(runtime.json()["provider"], "gold")
        self.assertEqual(runtime.json()["transport"], "service")
        self.assertEqual(runtime.json()["active_project_id"], "cip-dmd")
        self.assertFalse(runtime.json()["ui_load_enabled"])

    def test_project_registry_contract_and_active_context(self):
        projects = self.client.get("/api/v1/projects")
        self.assertEqual(projects.status_code, 200)
        self.assertEqual(projects.json()[0]["project_id"], "cip-dmd")
        created = self.client.post(
            "/api/v1/projects",
            json={
                "project_id": "equipment-history",
                "name": "Equipment History",
                "domain_type": "maintenance",
                "dataset_name": "Synthetic Maintenance",
            },
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["status"], "draft")
        project_query = self.client.post(
            "/api/v1/query",
            json={
                "project_id": "equipment-history",
                "question": "장비를 보여줘.",
            },
        )
        self.assertEqual(project_query.status_code, 409)
        activated = self.client.post(
            "/api/v1/projects/equipment-history/activate"
        )
        self.assertTrue(activated.json()["is_active"])
        response = self.client.post(
            "/api/v1/query",
            json={
                "project_id": "equipment-history",
                "question": "장비를 보여줘.",
            },
        )
        self.assertEqual(response.status_code, 409)
        readiness = self.client.get(
            "/api/v1/projects/equipment-history/readiness"
        )
        self.assertEqual(readiness.status_code, 200)
        self.assertFalse(readiness.json()["can_query"])
        self.assertEqual(readiness.json()["next_action"], "upload")
        self.assertEqual(
            readiness.json()["checks"]["source"]["status"], "FAIL"
        )
        bypass = self.client.patch(
            "/api/v1/projects/equipment-history",
            json={"status": "ready"},
        )
        self.assertEqual(bypass.status_code, 422)

    def test_empty_custom_project_is_blocked_before_llm_query(self):
        created = self.client.post(
            "/api/v1/projects",
            json={
                "project_id": "empty-project",
                "name": "Empty",
                "domain_type": "maintenance",
                "dataset_name": "Empty data",
            },
        )
        self.assertEqual(created.status_code, 201)
        response = self.client.post(
            "/api/v1/query",
            json={
                "project_id": "empty-project",
                "question": "장비를 보여줘.",
            },
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn("readiness gate", response.json()["detail"])

    def test_graph_load_is_disabled_without_explicit_server_opt_in(self):
        response = self.client.post(
            "/api/v1/projects/cip-dmd/graph/load",
            json={
                "upload_id": "0" * 36,
                "confirm_project_id": "cip-dmd",
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("비활성화", response.json()["detail"])

    def test_successful_graph_load_requires_evaluation_before_ready(self):
        self.client.post(
            "/api/v1/projects",
            json={
                "project_id": "load-project",
                "name": "Load project",
                "domain_type": "maintenance",
                "dataset_name": "Load data",
            },
        )
        self.projects.transition(
            "load-project", "profiling", reason="test"
        )
        self.projects.transition(
            "load-project", "mapping_review", reason="test"
        )
        with patch.dict(
            "os.environ",
            {"P3_ENABLE_UI_LOAD": "1"},
        ):
            response = self.client.post(
                "/api/v1/projects/load-project/graph/load",
                json={
                    "upload_id": "0" * 36,
                    "confirm_project_id": "load-project",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.projects.require("load-project")["status"],
            "evaluation_required",
        )
        blocked = self.client.post(
            "/api/v1/query",
            json={
                "project_id": "load-project",
                "question": "장비를 보여줘.",
            },
        )
        self.assertEqual(blocked.status_code, 409)

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
        missing_project = self.client.get(
            "/api/v1/metrics",
            params={"project_id": "missing-project"},
        )
        self.assertEqual(missing_project.status_code, 404)

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

    def test_project_aware_registry_isolates_and_closes_bundles(self):
        created = {}

        def factory(project_id):
            bundle = FakeBundle()
            created[project_id] = bundle
            return bundle

        registry = ServiceRegistry(factory, project_aware=True)
        first = registry.get("first-project")
        second = registry.get("second-project")
        self.assertIsNot(first, second)
        self.assertIs(first, registry.get("first-project"))

        registry.close("first-project")
        self.assertTrue(first.closed)
        self.assertFalse(second.closed)
        registry.close()
        self.assertTrue(second.closed)


if __name__ == "__main__":
    unittest.main()
