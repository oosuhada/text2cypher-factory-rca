import tempfile
import unittest
from pathlib import Path

import yaml

from backend.app.schema_registry import SchemaRegistry


class SchemaRegistryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.registry = SchemaRegistry(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def manifest(self):
        return {
            "project_id": "sample-project",
            "version": "1.0",
            "title": "Sample",
            "nodes": [
                {
                    "label": "Asset",
                    "identity": "asset_id",
                    "properties": {"asset_id": "STRING", "name": "STRING"},
                },
                {
                    "label": "Event",
                    "identity": "event_id",
                    "properties": {"event_id": "STRING"},
                },
            ],
            "relationships": [
                {
                    "type": "HAS_EVENT",
                    "source": "Asset",
                    "targets": ["Event"],
                }
            ],
        }

    def test_save_load_context_and_contract(self):
        saved = self.registry.save("sample-project", self.manifest())
        self.assertEqual(saved["version"], "1.0")
        context = self.registry.context("sample-project")
        self.assertIn("Asset {asset_id: STRING", context)
        self.assertIn("(:Asset)-[:HAS_EVENT]->(:Event)", context)
        contract = self.registry.contract("sample-project")
        self.assertEqual(
            contract["node_identities"][0]["identity_property"],
            "asset_id",
        )

    def test_invalid_relationship_and_identity_are_rejected(self):
        manifest = self.manifest()
        manifest["relationships"][0]["targets"] = ["Missing"]
        with self.assertRaisesRegex(ValueError, "target"):
            self.registry.save("sample-project", manifest)
        manifest = self.manifest()
        manifest["nodes"][0]["identity"] = "missing_id"
        with self.assertRaisesRegex(ValueError, "identity"):
            self.registry.save("sample-project", manifest)

    def test_checked_in_cip_manifest_is_valid(self):
        root = Path(__file__).resolve().parents[1] / "schemas"
        registry = SchemaRegistry(root)
        contract = registry.contract("cip-dmd")
        self.assertIn("ASSEMBLED_FROM", contract["relationship_types"])
        self.assertIn("QualityMeasurement", contract["schema_context"])
