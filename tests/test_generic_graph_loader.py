import base64
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from backend.app.etl.generic_loader import GenericGraphLoader
from backend.app.ingestion import DatasetWorkspace
from backend.app.mapping import MappingWorkspace
from backend.app.schema_registry import SchemaRegistry


class FakeDriver:
    def __init__(self):
        self.calls = []

    def execute_query(self, query, **kwargs):
        self.calls.append((query, kwargs))
        if "RETURN nodes" in query:
            return SimpleNamespace(
                records=[{"nodes": 2, "relationships": 1}]
            )
        return SimpleNamespace(records=[], summary=SimpleNamespace())


class GenericGraphLoaderTest(unittest.TestCase):
    def test_every_merge_and_match_is_scoped_by_project(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            datasets = DatasetWorkspace(root / "uploads")
            schemas = SchemaRegistry(root / "schemas")
            mappings = MappingWorkspace(root / "mappings", datasets, schemas)
            encoded = base64.b64encode(
                b"equipment_id,part_id\nEQ-1,P-1\nEQ-2,P-2\n"
            ).decode()
            upload = datasets.profile_upload(
                "factory-demo",
                [{"filename": "events.csv", "content_base64": encoded}],
            )
            mapping = {
                "nodes": [
                    {
                        "label": "Equipment",
                        "source_file": "events.csv",
                        "identity": "equipment_id",
                        "properties": {"equipment_id": "equipment_id"},
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
                        "source_file": "events.csv",
                        "source_key": "equipment_id",
                        "target_key": "part_id",
                    }
                ],
            }
            mappings.approve(
                "factory-demo", upload["upload_id"], mapping
            )
            driver = FakeDriver()
            result = GenericGraphLoader(datasets, mappings).load(
                driver, "factory-demo", upload["upload_id"]
            )
            self.assertTrue(result["integrity"]["project_scope_applied"])
            for query, kwargs in driver.calls:
                self.assertIn("project_id", query)
                self.assertEqual(kwargs["project_id"], "factory-demo")
            self.assertIn("`PROCESSED`", driver.calls[2][0])
