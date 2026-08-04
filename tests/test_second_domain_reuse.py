import base64
import json
import tempfile
import unittest
from pathlib import Path

from backend.app.ingestion import DatasetWorkspace
from backend.app.mapping import MappingWorkspace
from backend.app.schema_registry import SchemaRegistry


ROOT = Path(__file__).resolve().parents[1]


class SecondDomainReuseTest(unittest.TestCase):
    def test_equipment_history_uses_same_upload_mapping_schema_pipeline(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            datasets = DatasetWorkspace(temp_root / "uploads")
            schemas = SchemaRegistry(temp_root / "schemas")
            mappings = MappingWorkspace(
                temp_root / "mappings", datasets, schemas
            )
            source = ROOT / "examples" / "equipment_history" / "events.csv"
            upload = datasets.profile_upload(
                "equipment-history",
                [{
                    "filename": "events.csv",
                    "content_base64": base64.b64encode(
                        source.read_bytes()
                    ).decode(),
                }],
            )
            mapping = json.loads(
                (
                    ROOT / "examples" / "equipment_history" / "mapping.json"
                ).read_text(encoding="utf-8")
            )
            approved = mappings.approve(
                "equipment-history", upload["upload_id"], mapping
            )
            self.assertEqual(upload["files"][0]["row_count"], 12)
            self.assertEqual(len(approved["manifest"]["nodes"]), 3)
            self.assertEqual(len(approved["manifest"]["relationships"]), 2)
            self.assertIn(
                "MaintenanceEvent", schemas.context("equipment-history")
            )

    def test_gold_queries_all_include_project_scope(self):
        import yaml

        payload = yaml.safe_load(
            (
                ROOT / "evaluation" / "equipment-history_gold.yml"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(len(payload["questions"]), 7)
        self.assertTrue(
            all(
                "project_id: 'equipment-history'" in row["gold_cypher"]
                for row in payload["questions"]
            )
        )
