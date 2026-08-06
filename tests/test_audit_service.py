import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend.app.services.audit_service import AuditService


class AuditServiceTest(unittest.TestCase):
    def test_timeline_reconstructs_runs_and_redacts_sensitive_fields(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            processed = root / "data" / "processed"
            processed.mkdir(parents=True)
            (processed / "query_audit.jsonl").write_text(
                json.dumps(
                    {
                        "run_id": "query-1",
                        "timestamp": "2026-07-28T00:00:00+00:00",
                        "question": "장비 이력을 보여줘",
                        "cypher": "MATCH (n) RETURN n LIMIT 1",
                        "project_id": "cip-dmd",
                        "provider": "gemini",
                        "status": "success",
                        "authorization": "Bearer secret",
                        "api_key": "secret",
                        "system_prompt": "never expose",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            etl_root = processed / "etl_runs"
            etl_root.mkdir()
            (etl_root / "etl_20260728T000000Z.json").write_text(
                json.dumps(
                    {
                        "started_at": "2026-07-27T23:00:00+00:00",
                        "finished_at": "2026-07-27T23:01:00+00:00",
                        "mode": "load",
                        "status": "PASS",
                        "validation": {"counts": {"nodes": 10}},
                    }
                ),
                encoding="utf-8",
            )
            evaluation = root / "evaluation" / "results"
            evaluation.mkdir(parents=True)
            (evaluation / "latest.json").write_text(
                json.dumps(
                    {
                        "evaluated_at": "2026-07-27T22:00:00+00:00",
                        "evaluation_fingerprint": "abc123",
                        "question_count": 26,
                        "provider": "gemini",
                    }
                ),
                encoding="utf-8",
            )
            service = AuditService(root)
            job = service.jobs.create(
                "cip-dmd", "generic_graph_load", message="queued"
            )
            service.jobs.update(
                job["job_id"],
                status="succeeded",
                current_step="complete",
                progress=100,
                message="done",
            )
            events = service.events("cip-dmd")
            query = service.run("cip-dmd", "query-1")

        self.assertEqual(
            {event["event_type"] for event in events},
            {"query", "etl", "evaluation"},
        )
        self.assertEqual(query["question"], "장비 이력을 보여줘")
        self.assertEqual(query["cypher"], "MATCH (n) RETURN n LIMIT 1")
        self.assertNotIn("authorization", query)
        self.assertNotIn("api_key", query)
        self.assertNotIn("system_prompt", query)

    def test_search_and_project_scope_are_enforced(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            project_root = (
                root
                / "data"
                / "processed"
                / "projects"
                / "equipment-history"
            )
            project_root.mkdir(parents=True)
            (project_root / "query_audit.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "timestamp": "2026-07-28T00:00:00+00:00",
                                "question": "펌프 정비",
                                "status": "success",
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {
                                "timestamp": "2026-07-28T00:01:00+00:00",
                                "question": "다른 질문",
                                "project_id": "another-project",
                                "status": "success",
                            },
                            ensure_ascii=False,
                        ),
                    ]
                ),
                encoding="utf-8",
            )
            service = AuditService(root)
            events = service.events(
                "equipment-history", event_type="query", search="펌프"
            )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["project_id"], "equipment-history")


if __name__ == "__main__":
    unittest.main()
