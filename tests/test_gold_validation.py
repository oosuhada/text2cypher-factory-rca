import os
from pathlib import Path
import socket
import unittest

from neo4j import GraphDatabase

from backend.app.etl.cli import password_from_keychain
from evaluation.gold_validation import (
    build_snapshot,
    compare_snapshot,
    load_gold_questions,
    load_snapshot,
    normalize_records,
)


def neo4j_credentials() -> tuple[str, str] | None:
    try:
        with socket.create_connection(("localhost", 7687), timeout=0.5):
            pass
    except OSError:
        return None
    username = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD") or password_from_keychain(username)
    return (username, password) if password else None


class GoldNormalizationTest(unittest.TestCase):
    def test_normalization_ignores_record_and_nested_list_order(self):
        first = [
            {"id": "2", "items": [{"value": 2}, {"value": 1}]},
            {"id": "1", "items": []},
        ]
        second = [
            {"items": [], "id": "1"},
            {"items": [{"value": 1}, {"value": 2}], "id": "2"},
        ]
        self.assertEqual(normalize_records(first), normalize_records(second))

    def test_comparison_reports_changed_rows(self):
        question = {
            "id": "QX",
            "category": "test",
            "question": "test",
            "expected_status": "success",
        }
        expected = build_snapshot(question, [{"count": 1}])
        actual = build_snapshot(question, [{"count": 2}])
        comparison = compare_snapshot(expected, actual)
        self.assertFalse(comparison["match"])
        self.assertEqual(comparison["missing_rows"], [{"count": 1}])
        self.assertEqual(comparison["unexpected_rows"], [{"count": 2}])

    def test_value_comparison_ignores_alias_and_allows_extra_evidence(self):
        question = {
            "id": "QX",
            "category": "test",
            "question": "test",
            "expected_status": "success",
        }
        expected = build_snapshot(
            question, [{"part_type": "cylinder", "part_count": 802}]
        )
        actual = build_snapshot(
            question,
            [
                {
                    "part_type": "cylinder",
                    "count": 802,
                    "source": "CiP-DMD",
                }
            ],
        )
        comparison = compare_snapshot(expected, actual)
        self.assertTrue(comparison["match"])
        self.assertTrue(comparison["semantic_match"])
        self.assertFalse(comparison["strict_match"])
        self.assertTrue(comparison["contract_only_mismatch"])

    def test_value_comparison_rejects_missing_or_wrong_values(self):
        question = {
            "id": "QX",
            "category": "test",
            "question": "test",
            "expected_status": "success",
        }
        expected = build_snapshot(
            question, [{"part_type": "cylinder", "part_count": 802}]
        )
        missing = build_snapshot(question, [{"count": 802}])
        wrong = build_snapshot(
            question, [{"part_type": "cylinder", "count": 803}]
        )
        self.assertFalse(compare_snapshot(expected, missing)["match"])
        self.assertFalse(compare_snapshot(expected, wrong)["match"])

    def test_all_fifteen_approved_snapshots_exist(self):
        project_root = Path(__file__).resolve().parents[1]
        questions = load_gold_questions(
            project_root / "evaluation" / "gold_questions.yml"
        )
        snapshots = [
            load_snapshot(
                project_root
                / "evaluation"
                / "gold_results"
                / f"{question['id']}.json"
            )
            for question in questions
        ]
        self.assertEqual(len(snapshots), 15)
        self.assertEqual(
            {snapshot["question_id"] for snapshot in snapshots},
            {f"Q{index}" for index in range(1, 16)},
        )


@unittest.skipUnless(
    neo4j_credentials(),
    "local Neo4j credentials are required for Gold result integration",
)
class GoldResultIntegrationTest(unittest.TestCase):
    def test_current_graph_matches_all_approved_gold_results(self):
        project_root = Path(__file__).resolve().parents[1]
        questions = load_gold_questions(
            project_root / "evaluation" / "gold_questions.yml"
        )
        username, password = neo4j_credentials()
        driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI", "neo4j://localhost:7687"),
            auth=(username, password),
        )
        mismatches = []
        try:
            for question in questions:
                records, _, _ = driver.execute_query(
                    question["gold_cypher"],
                    database_=os.getenv("NEO4J_DATABASE", "neo4j"),
                    routing_="r",
                )
                actual = build_snapshot(
                    question, [record.data() for record in records]
                )
                expected = load_snapshot(
                    project_root
                    / "evaluation"
                    / "gold_results"
                    / f"{question['id']}.json"
                )
                comparison = compare_snapshot(expected, actual)
                if not comparison["strict_match"]:
                    mismatches.append(comparison)
        finally:
            driver.close()
        self.assertEqual(mismatches, [])


if __name__ == "__main__":
    unittest.main()
