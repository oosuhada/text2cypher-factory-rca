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

    def test_dry_run_isolates_data_quality_issues_and_maps_relationship_properties(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            datasets = DatasetWorkspace(root / "uploads")
            schemas = SchemaRegistry(root / "schemas")
            mappings = MappingWorkspace(
                root / "mappings", datasets, schemas
            )
            files = [
                {
                    "filename": "equipment.csv",
                    "content_base64": base64.b64encode(
                        (
                            b"equipment_id,capacity\n"
                            b"EQ-1,10\n"
                            b"EQ-1,11\n"
                            b",20\n"
                            b"EQ-2,not-a-number\n"
                            b"EQ-3,\n"
                        )
                    ).decode(),
                },
                {
                    "filename": "parts.csv",
                    "content_base64": base64.b64encode(
                        b"part_id\nP-1\n"
                    ).decode(),
                },
                {
                    "filename": "links.csv",
                    "content_base64": base64.b64encode(
                        (
                            b"equipment_id,part_id,sequence\n"
                            b"EQ-1,P-1,1\n"
                            b"EQ-404,P-1,2\n"
                            b"EQ-1,P-1,1\n"
                            b"EQ-1,,3\n"
                            b"EQ-1,P-1,\n"
                        )
                    ).decode(),
                },
            ]
            upload = datasets.profile_upload("factory-demo", files)
            mapping = {
                "nodes": [
                    {
                        "label": "Equipment",
                        "source_file": "equipment.csv",
                        "identity": "equipment_id",
                        "properties": {
                            "equipment_id": "equipment_id",
                            "capacity": "capacity",
                        },
                        "property_types": {"capacity": "INTEGER"},
                        "required_properties": [
                            "equipment_id",
                            "capacity",
                        ],
                    },
                    {
                        "label": "Part",
                        "source_file": "parts.csv",
                        "identity": "part_id",
                        "properties": {"part_id": "part_id"},
                    },
                ],
                "relationships": [
                    {
                        "type": "PROCESSED",
                        "source": "Equipment",
                        "target": "Part",
                        "source_file": "links.csv",
                        "source_key": "equipment_id",
                        "target_key": "part_id",
                        "properties": {"sequence": "sequence"},
                        "property_types": {"sequence": "INTEGER"},
                        "required_properties": ["sequence"],
                        "cardinality": "ONE_TO_MANY",
                    }
                ],
            }
            preview = mappings.preview(
                "factory-demo", upload["upload_id"], mapping
            )
            dry_run = preview["dry_run"]
            self.assertEqual(dry_run["status"], "WARN")
            self.assertEqual(
                dry_run["nodes"]["Equipment"]["projected_rows"], 1
            )
            self.assertEqual(
                dry_run["nodes"]["Equipment"]["duplicate_identity_count"], 1
            )
            self.assertEqual(
                dry_run["nodes"]["Equipment"]["missing_identity_count"], 1
            )
            self.assertEqual(
                dry_run["nodes"]["Equipment"]["type_error_count"], 1
            )
            self.assertEqual(
                dry_run["nodes"]["Equipment"][
                    "missing_required_property_count"
                ],
                1,
            )
            self.assertEqual(
                dry_run["relationships"]["PROCESSED"]["projected_rows"], 1
            )
            self.assertEqual(
                dry_run["relationships"]["PROCESSED"]["orphan_count"], 1
            )
            self.assertEqual(
                dry_run["relationships"]["PROCESSED"]["duplicate_count"], 1
            )
            self.assertEqual(
                dry_run["relationships"]["PROCESSED"]["missing_key_count"], 1
            )
            self.assertEqual(
                dry_run["relationships"]["PROCESSED"][
                    "missing_required_property_count"
                ],
                1,
            )
            relationship = preview["manifest"]["relationships"][0]
            self.assertEqual(
                relationship["properties"], {"sequence": "INTEGER"}
            )
            self.assertEqual(
                relationship["cardinality"], "ONE_TO_MANY"
            )
            self.assertEqual(
                dry_run["lineage"]["sources"][0]["filename"],
                "equipment.csv",
            )
