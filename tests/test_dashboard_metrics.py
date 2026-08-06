import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend.app.services.dashboard_service import (
    filter_runtime_events,
    load_query_audit,
    summarize_runtime,
)
from backend.app.services.query_service import QueryService


class FakeAgent:
    def invoke(self, question):
        return {
            "question": question,
            "statement": "MATCH (part:Part) RETURN part LIMIT 1",
            "records": [{"part_id": "300002"}],
            "status": "success",
            "attempts": 2,
            "errors": [],
            "trace": [
                {"step": "generate_cypher"},
                {"step": "correct_cypher"},
                {"step": "execute_cypher"},
            ],
            "elapsed_ms": 42,
        }


class DashboardMetricsTest(unittest.TestCase):
    def test_query_service_appends_audit_event(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "query_audit.jsonl"
            service = QueryService(
                FakeAgent(),
                audit_log_path=path,
                provider="gold",
            )
            service.query("완제품을 보여줘")
            events = load_query_audit(path)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["status"], "success")
        self.assertEqual(events[0]["elapsed_ms"], 42)
        self.assertTrue(events[0]["corrected"])
        self.assertEqual(events[0]["provider"], "gold")

    def test_runtime_summary_uses_only_corrected_queries_for_rate(self):
        events = [
            {
                "status": "success",
                "elapsed_ms": 100,
                "corrected": False,
            },
            {"status": "empty", "elapsed_ms": 200, "corrected": True},
            {"status": "blocked", "elapsed_ms": 0, "corrected": True},
        ]
        summary = summarize_runtime(events)
        self.assertEqual(summary["query_count"], 3)
        self.assertAlmostEqual(summary["success_rate"], 2 / 3)
        self.assertEqual(summary["average_elapsed_ms"], 100)
        self.assertEqual(summary["correction_count"], 2)
        self.assertEqual(summary["correction_success_rate"], 0.5)

    def test_audit_loader_skips_malformed_lines_and_obeys_limit(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "query_audit.jsonl"
            path.write_text(
                "\n".join(
                    [
                        json.dumps({"status": "success"}),
                        "{malformed",
                        json.dumps({"status": "empty"}),
                    ]
                ),
                encoding="utf-8",
            )
            events = load_query_audit(path, limit=2)

        self.assertEqual(events, [{"status": "empty"}])

    def test_runtime_filters_share_provider_status_project_and_time_scope(self):
        events = [
            {
                "timestamp": "2026-07-27T00:00:00+00:00",
                "project_id": "cip-dmd",
                "provider": "gemini",
                "status": "success",
            },
            {
                "timestamp": "2025-01-01T00:00:00+00:00",
                "project_id": "cip-dmd",
                "provider": "gemini",
                "status": "success",
            },
            {
                "timestamp": "2026-07-27T00:00:00+00:00",
                "project_id": "other",
                "provider": "gemini",
                "status": "success",
            },
        ]
        filtered = filter_runtime_events(
            events,
            providers=["gemini"],
            statuses=["success"],
            days=30,
            project_id="cip-dmd",
        )
        self.assertEqual(filtered, [events[0]])

    def test_runtime_summary_reports_latency_provider_and_errors(self):
        summary = summarize_runtime(
            [
                {
                    "status": "success",
                    "provider": "gemini",
                    "elapsed_ms": 10,
                    "error_count": 0,
                },
                {
                    "status": "failed",
                    "provider": "gemini",
                    "elapsed_ms": 90,
                    "error_count": 2,
                },
            ]
        )
        self.assertEqual(summary["median_elapsed_ms"], 50)
        self.assertEqual(summary["p95_elapsed_ms"], 90)
        self.assertEqual(
            summary["provider_counts"],
            [{"provider": "gemini", "count": 2}],
        )
        self.assertEqual(summary["error_count"], 2)
        self.assertEqual(summary["error_rate"], 1)


if __name__ == "__main__":
    unittest.main()
