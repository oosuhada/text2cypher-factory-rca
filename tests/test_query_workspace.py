import unittest

from frontend.query_workspace import (
    example_questions,
    query_placeholder,
    query_context_versions,
    query_status_presentation,
    statement_history,
)


class QueryWorkspaceTest(unittest.TestCase):
    def test_examples_and_placeholder_are_project_scoped(self):
        cip_examples = example_questions("cip-dmd")
        equipment_examples = example_questions("equipment-history")
        self.assertTrue(any("완제품" in question for _, question in cip_examples))
        self.assertFalse(
            any("완제품" in question for _, question in equipment_examples)
        )
        self.assertTrue(
            all(
                "정비" in question or "중단" in question
                for _, question in equipment_examples
            )
        )
        self.assertIn(
            "EQ-PRESS-01",
            query_placeholder("equipment-history"),
        )
        self.assertIn("완제품", query_placeholder("cip-dmd"))

    def test_all_runtime_statuses_have_explicit_presentation(self):
        for status in (
            "success",
            "empty",
            "blocked",
            "failed",
            "needs_clarification",
        ):
            presentation = query_status_presentation(status)
            self.assertNotEqual(presentation["label"], status)
            self.assertTrue(presentation["description"])

    def test_response_metadata_wins_over_project_versions(self):
        versions = query_context_versions(
            {
                "project_id": "cip-dmd",
                "source_version": "source-old",
                "schema_version": "1.0",
                "prompt_version": "prompt-old",
                "evaluation_version": "eval-old",
            },
            {
                "metadata": {
                    "source_version": "source-2",
                    "schema_version": "1.1",
                    "prompt_version": "prompt-2",
                    "evaluation_version": "eval-2",
                }
            },
        )
        values = {row["label"]: row["value"] for row in versions}
        self.assertEqual(values["데이터"], "source-2")
        self.assertEqual(values["Schema"], "1.1")
        self.assertEqual(values["Prompt"], "prompt-2")
        self.assertEqual(values["Evaluation"], "eval-2")

    def test_statement_history_preserves_generate_and_correction(self):
        history = statement_history(
            {
                "cypher": "MATCH (n) RETURN n",
                "validation": {
                    "statement_history": [
                        {
                            "kind": "generated",
                            "attempt": 1,
                            "statement": "MATCH n RETURN n",
                        },
                        {
                            "kind": "corrected",
                            "attempt": 2,
                            "statement": "MATCH (n) RETURN n",
                        },
                    ]
                },
            }
        )
        self.assertEqual(
            [item["kind"] for item in history],
            ["generated", "corrected"],
        )


if __name__ == "__main__":
    unittest.main()
