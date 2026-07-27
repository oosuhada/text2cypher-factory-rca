import base64
import tempfile
import unittest
from pathlib import Path

from backend.app.ingestion import DatasetWorkspace
from backend.app.mapping import MappingWorkspace
from backend.app.schema_registry import SchemaRegistry


class MappingWorkspaceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.datasets = DatasetWorkspace(root / "uploads")
        self.schemas = SchemaRegistry(root / "schemas")
        self.mappings = MappingWorkspace(
            root / "mappings", self.datasets, self.schemas
        )
        encoded = base64.b64encode(
            b"equipment_id,part_id,name\nEQ-1,P-1,Press\nEQ-2,P-2,Cutter\n"
        ).decode()
        self.upload = self.datasets.profile_upload(
            "factory-demo",
            [{"filename": "events.csv", "content_base64": encoded}],
        )
        self.mapping = {
            "title": "Factory demo",
            "nodes": [
                {
                    "label": "Equipment",
                    "source_file": "events.csv",
                    "identity": "equipment_id",
                    "properties": {
                        "equipment_id": "equipment_id",
                        "name": "name",
                    },
                },
                {
                    "label": "Part",
                    "source_file": "events.csv",
                    "identity": "part_id",
                    "properties": {"part_id": "part_id"},
                },
            ],
            "relationships": [
                {
                    "type": "PROCESSED",
                    "source": "Equipment",
                    "target": "Part",
                    "source_key": "equipment_id",
                    "target_key": "part_id",
                }
            ],
        }

    def tearDown(self):
        self.temp.cleanup()

    def test_preview_and_approve_create_versioned_manifest(self):
        preview = self.mappings.preview(
            "factory-demo", self.upload["upload_id"], self.mapping
        )
        self.assertEqual(preview["estimated_node_rows"]["Equipment"], 2)
        approved = self.mappings.approve(
            "factory-demo", self.upload["upload_id"], self.mapping
        )
        self.assertEqual(approved["status"], "approved")
        self.assertEqual(
            self.schemas.contract("factory-demo")["relationship_types"],
            ["PROCESSED"],
        )

    def test_missing_source_column_is_rejected(self):
        self.mapping["nodes"][0]["properties"][
            "equipment_id"
        ] = "missing"
        with self.assertRaisesRegex(ValueError, "원본 컬럼"):
            self.mappings.preview(
                "factory-demo", self.upload["upload_id"], self.mapping
            )

    def test_identity_is_graph_property_and_may_map_source_alias(self):
        self.mapping["nodes"][0]["identity"] = "id"
        self.mapping["nodes"][0]["properties"] = {
            "id": "equipment_id",
            "name": "name",
        }
        preview = self.mappings.preview(
            "factory-demo", self.upload["upload_id"], self.mapping
        )
        equipment = next(
            node
            for node in preview["manifest"]["nodes"]
            if node["label"] == "Equipment"
        )
        self.assertEqual(equipment["identity"], "id")
        self.assertEqual(equipment["properties"]["id"], "STRING")
