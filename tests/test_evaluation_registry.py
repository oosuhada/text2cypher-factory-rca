import os
from pathlib import Path
import socket
import unittest

from neo4j import GraphDatabase
import yaml

from backend.app.etl.cli import password_from_keychain
from evaluation.gold_validation import (
    build_snapshot,
    compare_snapshot,
    load_snapshot,
)
from evaluation.registry import EvaluationRegistry


ROOT = Path(__file__).resolve().parents[1]


def neo4j_credentials() -> tuple[str, str] | None:
    try:
        with socket.create_connection(("localhost", 7687), timeout=0.5):
            pass
    except OSError:
        return None
    username = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD") or password_from_keychain(username)
    return (username, password) if password else None


class EvaluationRegistryTest(unittest.TestCase):
    def setUp(self):
        self.registry = EvaluationRegistry(
            ROOT / "evaluation", ROOT / "schemas"
        )

    def test_both_projects_have_versioned_gold_and_blind_contracts(self):
        cip = self.registry.load("cip-dmd")
        equipment = self.registry.load("equipment-history")
        self.assertEqual(cip["schema_version"], "1.1")
        self.assertEqual(equipment["schema_version"], "1.0")
        self.assertEqual(
            len(
                yaml.safe_load(
                    Path(equipment["gold"]["questions_path"]).read_text(
                        encoding="utf-8"
                    )
                )["questions"]
            ),
            15,
        )
        self.assertEqual(
            len(
                yaml.safe_load(
                    Path(equipment["blind"]["questions_path"]).read_text(
                        encoding="utf-8"
                    )
                )["questions"]
            ),
            20,
        )
        self.assertEqual(len(cip["fingerprint"]), 64)
        self.assertEqual(
            cip["fingerprint"],
            self.registry.load("cip-dmd")["fingerprint"],
        )

    def test_schema_version_drift_is_rejected(self):
        manifest = yaml.safe_load(
            (
                ROOT
                / "evaluation"
                / "projects"
                / "cip-dmd"
                / "manifest.yml"
            ).read_text(encoding="utf-8")
        )
        manifest["schema_version"] = "0.0"
        with self.assertRaisesRegex(ValueError, "schema_version"):
            self.registry.validate(
                manifest, expected_project_id="cip-dmd"
            )


@unittest.skipUnless(
    neo4j_credentials(),
    "local Neo4j credentials are required for equipment snapshot regression",
)
class EquipmentEvaluationIntegrationTest(unittest.TestCase):
    def test_current_graph_matches_equipment_gold_and_blind_snapshots(self):
        registry = EvaluationRegistry(
            ROOT / "evaluation", ROOT / "schemas"
        )
        config = registry.load("equipment-history")
        username, password = neo4j_credentials()
        driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI", "neo4j://localhost:7687"),
            auth=(username, password),
        )
        mismatches = []
        try:
            for split in ("gold", "blind"):
                questions = yaml.safe_load(
                    Path(config[split]["questions_path"]).read_text(
                        encoding="utf-8"
                    )
                )["questions"]
                snapshot_root = Path(
                    config[split]["snapshots_path"]
                )
                for question in questions:
                    if not question.get("gold_cypher"):
                        continue
                    records, _, _ = driver.execute_query(
                        question["gold_cypher"],
                        database_=os.getenv(
                            "NEO4J_DATABASE", "neo4j"
                        ),
                        routing_="r",
                    )
                    actual = build_snapshot(
                        question, [record.data() for record in records]
                    )
                    comparison = compare_snapshot(
                        load_snapshot(
                            snapshot_root / f"{question['id']}.json"
                        ),
                        actual,
                    )
                    if not comparison["strict_match"]:
                        mismatches.append(comparison)
        finally:
            driver.close()
        self.assertEqual(mismatches, [])
