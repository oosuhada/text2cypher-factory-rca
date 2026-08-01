import json
from pathlib import Path
import tempfile
import unittest

from backend.app.services.dashboard_service import (
    summarize_status_classification,
)
from backend.app.services.diagnostics import latest_successful_etl
from frontend.app_services import ServiceBundle
from frontend.data_preflight import inspect_uploaded_source


class UploadPreflightTest(unittest.TestCase):
    def test_json_metadata_with_part_id_passes(self):
        result = inspect_uploaded_source(
            "meta_data.json",
            json.dumps(
                [{"part_id": "1001", "quality_data": []}]
            ).encode(),
        )
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["record_count"], 1)

    def test_csv_with_part_id_family_passes(self):
        result = inspect_uploaded_source(
            "quality_data.csv",
            b"part_id_cylinder_bottom;pressure\n1001;10.0\n",
        )
        self.assertEqual(result["status"], "PASS")
        self.assertIn("part_id_cylinder_bottom", result["columns"])

    def test_invalid_or_unmapped_upload_never_passes(self):
        malformed = inspect_uploaded_source("meta_data.json", b"{broken")
        unmapped = inspect_uploaded_source(
            "quality_data.csv", b"value;pressure\n1;10\n"
        )
        self.assertEqual(malformed["status"], "FAIL")
        self.assertEqual(unmapped["status"], "REVIEW")


class DemoReadinessTest(unittest.TestCase):
    def test_latest_successful_load_ignores_dry_run(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs = root / "etl_runs"
            runs.mkdir()
            (runs / "etl_20260101T000000Z.json").write_text(
                json.dumps({"mode": "load", "status": "PASS"}),
                encoding="utf-8",
            )
            (runs / "etl_20260102T000000Z.json").write_text(
                json.dumps({"mode": "dry-run", "status": "PASS"}),
                encoding="utf-8",
            )
            latest = latest_successful_etl(root)
            self.assertEqual(latest["mode"], "load")

    def test_status_confusion_matrix_and_macro_f1(self):
        report = {
            "variants": {
                "self_correction": {
                    "questions": [
                        {
                            "expected_status": "success",
                            "actual_status": "success",
                        },
                        {
                            "expected_status": "empty",
                            "actual_status": "success",
                        },
                        {
                            "expected_status": "blocked",
                            "actual_status": "blocked",
                        },
                    ]
                }
            }
        }
        summary = summarize_status_classification(report)
        self.assertEqual(summary["accuracy"], 2 / 3)
        empty = next(
            row for row in summary["per_class"] if row["status"] == "empty"
        )
        self.assertEqual(empty["recall"], 0)

    def test_service_bundle_uses_gold_fallback_for_fixed_demo(self):
        class FailingQuery:
            def query(self, question):
                raise RuntimeError("network unavailable")

        class GoldQuery:
            def query(self, question):
                return {
                    "status": "success",
                    "answer": "조회 결과",
                    "question": question,
                }

        bundle = ServiceBundle(
            driver=None,
            query=FailingQuery(),
            fallback_query=GoldQuery(),
            dashboard=None,
            provider="gemini",
            model_name="gemini-test",
        )
        result = bundle.query_with_fallback("고정 질문")
        self.assertEqual(result["status"], "success")
        self.assertIn("Gold", result["answer"])
        self.assertIn("network unavailable", result["fallback_reason"])


if __name__ == "__main__":
    unittest.main()
