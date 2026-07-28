import unittest

from evaluation.reporting import render_metrics_markdown


class EvaluationReportingTest(unittest.TestCase):
    def test_markdown_contains_versions_metrics_matrix_and_failures(self):
        status = {
            "labels": ["success", "empty"],
            "confusion_matrix": {
                "success": {"success": 1, "empty": 1},
                "empty": {"success": 0, "empty": 1},
            },
            "accuracy": 2 / 3,
            "macro_precision": 0.75,
            "macro_recall": 0.75,
            "macro_f1": 0.733333,
            "per_class": {},
        }
        metrics = {
            "result_accuracy": 0.8,
            "strict_result_accuracy": 0.6,
            "execution_success_rate": 1.0,
            "status_classification": status,
            "failure_counts": {"wrong_value_or_rowset": 2},
        }
        report = {
            "project_id": "factory-demo",
            "dataset": "Factory Demo",
            "provider": "gemini",
            "model": "gemini-test",
            "evaluation_version": "1.0",
            "schema_version": "2.0",
            "source_version": "source-v3",
            "prompt_version": "prompt-v4",
            "evaluation_fingerprint": "abc123",
            "evaluated_at": "2026-01-01T00:00:00+00:00",
            "comparison": [
                {"variant": "self_correction", **metrics}
            ],
            "variants": {
                "self_correction": {"metrics": metrics}
            },
        }
        markdown = render_metrics_markdown(report)
        self.assertIn("Schema / source: 2.0 / source-v3", markdown)
        self.assertIn("상태 Macro F1", markdown)
        self.assertIn("혼동행렬", markdown)
        self.assertIn("wrong_value_or_rowset", markdown)
