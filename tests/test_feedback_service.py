import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend.app.services.feedback_service import FeedbackService


class FeedbackServiceTest(unittest.TestCase):
    def test_record_review_is_append_only_and_summarized(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "expert_feedback.jsonl"
            service = FeedbackService(path)
            first = service.record_review(
                question="완제품 300002의 공정 이력을 보여줘.",
                cypher="MATCH (part:Part) RETURN part",
                query_status="success",
                provider="gemini",
                row_count=1,
                decision="verified",
                reviewer="quality-engineer",
                note="원장과 대조 완료",
            )
            second = service.record_review(
                question="완제품 300002의 공정 이력을 보여줘.",
                cypher="MATCH (part:Part) RETURN part",
                query_status="success",
                provider="gemini",
                row_count=1,
                decision="needs_followup",
                note="설비 이력 추가 확인",
            )
            summary = service.summary()
            lines = path.read_text(encoding="utf-8").splitlines()

        self.assertEqual(len(lines), 2)
        self.assertEqual(first["query_fingerprint"], second["query_fingerprint"])
        self.assertEqual(summary["total_reviews"], 2)
        self.assertEqual(summary["unique_queries_reviewed"], 1)
        self.assertEqual(summary["decision_counts"]["verified"], 1)
        self.assertEqual(summary["decision_counts"]["needs_followup"], 1)
        self.assertEqual(summary["recent"][0]["review_id"], second["review_id"])

    def test_invalid_decision_and_bounds_are_rejected(self):
        with TemporaryDirectory() as directory:
            service = FeedbackService(
                Path(directory) / "expert_feedback.jsonl"
            )
            with self.assertRaises(ValueError):
                service.record_review(
                    question="질문",
                    cypher="",
                    query_status="success",
                    provider="gold",
                    row_count=0,
                    decision="approved",
                )
            with self.assertRaises(ValueError):
                service.recent(limit=0)

    def test_recent_skips_malformed_audit_lines(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "expert_feedback.jsonl"
            path.write_text(
                "\n".join(
                    [
                        "{malformed",
                        json.dumps(
                            {
                                "review_id": "valid",
                                "decision": "verified",
                            }
                        ),
                    ]
                ),
                encoding="utf-8",
            )
            events = FeedbackService(path).recent()
        self.assertEqual(events, [{"review_id": "valid", "decision": "verified"}])


if __name__ == "__main__":
    unittest.main()
