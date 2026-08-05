import os
from pathlib import Path
import socket
import unittest

from neo4j import GraphDatabase

from backend.app.agent.examples import GoldExampleStore
from backend.app.etl.cli import password_from_keychain
from backend.app.security.read_only import validate_read_only
from evaluation.evaluator import (
    VARIANTS,
    classification_metrics,
    evaluate_question,
    load_blind_questions,
    summarize_results,
)
from evaluation.gold_validation import (
    build_snapshot,
    compare_snapshot,
    load_gold_questions,
    load_snapshot,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def neo4j_credentials() -> tuple[str, str] | None:
    try:
        with socket.create_connection(("localhost", 7687), timeout=0.5):
            pass
    except OSError:
        return None
    username = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD") or password_from_keychain(username)
    return (username, password) if password else None


class ConditionalModel:
    def generate(self, question, schema, few_shot_examples):
        del question, schema
        return (
            "RETURN 1 AS count"
            if few_shot_examples
            else "RETURN 2 AS count"
        )

    def correct(self, question, schema, statement, errors):
        del question, schema, statement, errors
        return "RETURN 1 AS count"


class CorrectingModel:
    def generate(self, question, schema, few_shot_examples):
        del question, schema, few_shot_examples
        return "RETURN BROKEN"

    def correct(self, question, schema, statement, errors):
        del question, schema, statement, errors
        return "RETURN 1 AS count"


class EvaluationGraph:
    def explain(self, statement):
        return ["EXPLAIN_ERROR: invalid"] if "BROKEN" in statement else []

    def execute(self, statement):
        return [{"count": 1 if "RETURN 1" in statement else 2}]


class BlindEvaluationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.questions = load_blind_questions(
            PROJECT_ROOT / "evaluation" / "blind_questions.yml"
        )
        cls.examples = GoldExampleStore(
            PROJECT_ROOT / "evaluation" / "gold_questions.yml"
        )

    def test_dataset_has_26_unique_questions_not_equal_to_gold(self):
        gold = load_gold_questions(
            PROJECT_ROOT / "evaluation" / "gold_questions.yml"
        )
        self.assertEqual(len(self.questions), 26)
        self.assertTrue(
            {question["question"] for question in self.questions}.isdisjoint(
                {question["question"] for question in gold}
            )
        )

    def test_all_query_scenarios_have_read_only_gold_and_snapshot(self):
        query_questions = [
            question
            for question in self.questions
            if question.get("gold_cypher")
        ]
        self.assertEqual(len(query_questions), 23)
        for question in query_questions:
            with self.subTest(question_id=question["id"]):
                self.assertEqual(
                    validate_read_only(question["gold_cypher"]), []
                )
                snapshot = load_snapshot(
                    PROJECT_ROOT
                    / "evaluation"
                    / "blind_results"
                    / f"{question['id']}.json"
                )
                self.assertEqual(snapshot["question_id"], question["id"])

    def test_few_shot_variant_improves_wrong_baseline_result(self):
        question = {
            "id": "BT",
            "category": "test",
            "difficulty": "easy",
            "question": "테스트 질문",
            "expected_status": "success",
        }
        expected = build_snapshot(question, [{"count": 1}])
        baseline = evaluate_question(
            question,
            expected,
            ConditionalModel(),
            EvaluationGraph(),
            self.examples,
            VARIANTS[0],
        )
        few_shot = evaluate_question(
            question,
            expected,
            ConditionalModel(),
            EvaluationGraph(),
            self.examples,
            VARIANTS[1],
        )
        self.assertFalse(baseline["result_match"])
        self.assertEqual(
            baseline["failure_type"], "wrong_value_or_rowset"
        )
        self.assertTrue(few_shot["result_match"])

    def test_self_correction_recovers_invalid_query(self):
        question = {
            "id": "BT",
            "category": "test",
            "difficulty": "easy",
            "question": "테스트 질문",
            "expected_status": "success",
        }
        expected = build_snapshot(question, [{"count": 1}])
        result = evaluate_question(
            question,
            expected,
            CorrectingModel(),
            EvaluationGraph(),
            self.examples,
            VARIANTS[2],
        )
        self.assertTrue(result["result_match"])
        self.assertTrue(result["correction_attempted"])
        self.assertTrue(result["correction_succeeded"])
        self.assertEqual(result["attempts"], 2)

    def test_metric_summary_uses_applicable_denominators(self):
        summary = summarize_results(
            [
                {
                    "expected_status": "success",
                    "actual_status": "success",
                    "execution_success": True,
                    "result_match": True,
                    "strict_result_match": True,
                    "contract_variance": False,
                    "difference_type": "exact",
                    "schema_compliant": True,
                    "read_only_compliant": True,
                    "execution_verified": True,
                    "empty_handled": None,
                    "correction_succeeded": None,
                    "evidence_displayed": True,
                    "elapsed_ms": 10,
                    "failure_type": None,
                },
                {
                    "expected_status": "success",
                    "actual_status": "failed",
                    "execution_success": False,
                    "result_match": False,
                    "strict_result_match": False,
                    "contract_variance": False,
                    "difference_type": "wrong_value_or_rowset",
                    "schema_compliant": False,
                    "read_only_compliant": True,
                    "execution_verified": None,
                    "empty_handled": None,
                    "correction_succeeded": None,
                    "evidence_displayed": False,
                    "elapsed_ms": 30,
                    "failure_type": "wrong_value_or_rowset",
                },
            ]
        )
        self.assertEqual(summary["result_accuracy"], 0.5)
        self.assertEqual(summary["read_only_compliance_rate"], 1.0)
        self.assertEqual(summary["unverified_execution_count"], 0)
        self.assertEqual(summary["average_elapsed_ms"], 20)
        self.assertEqual(
            summary["failure_counts"], {"wrong_value_or_rowset": 1}
        )

    def test_status_classification_builds_precision_recall_f1_and_matrix(self):
        metrics = classification_metrics(
            [
                {
                    "expected_status": "success",
                    "actual_status": "success",
                },
                {
                    "expected_status": "success",
                    "actual_status": "empty",
                },
                {
                    "expected_status": "empty",
                    "actual_status": "empty",
                },
                {
                    "expected_status": "blocked",
                    "actual_status": "blocked",
                },
            ]
        )
        self.assertEqual(
            metrics["confusion_matrix"]["success"]["empty"], 1
        )
        self.assertEqual(
            metrics["per_class"]["success"]["precision"], 1.0
        )
        self.assertEqual(
            metrics["per_class"]["success"]["recall"], 0.5
        )
        self.assertEqual(metrics["accuracy"], 0.75)


@unittest.skipUnless(
    neo4j_credentials(),
    "local Neo4j credentials are required for Blind answer regression",
)
class BlindExpectedIntegrationTest(unittest.TestCase):
    def test_current_graph_matches_all_blind_answer_snapshots(self):
        questions = load_blind_questions(
            PROJECT_ROOT / "evaluation" / "blind_questions.yml"
        )
        username, password = neo4j_credentials()
        driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI", "neo4j://localhost:7687"),
            auth=(username, password),
        )
        mismatches = []
        try:
            for question in questions:
                if not question.get("gold_cypher"):
                    continue
                records, _, _ = driver.execute_query(
                    question["gold_cypher"],
                    database_=os.getenv("NEO4J_DATABASE", "neo4j"),
                    routing_="r",
                )
                actual = build_snapshot(
                    question, [record.data() for record in records]
                )
                expected = load_snapshot(
                    PROJECT_ROOT
                    / "evaluation"
                    / "blind_results"
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
