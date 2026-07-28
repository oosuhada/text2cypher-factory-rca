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
    def __init__(self, *, wrong_count: bool = False):
        self.calls = []
        self.wrong_count = wrong_count

    def execute_query(self, query, **kwargs):
        self.calls.append((query, kwargs))
        return SimpleNamespace(records=[], summary=SimpleNamespace())

    def session(self, **kwargs):
        self.session_kwargs = kwargs
        return FakeSession(self)


class FakeResult:
    def __init__(self, record=None, counters=None):
        self._record = record
        self._summary = SimpleNamespace(
            counters=SimpleNamespace(
                **(
                    counters
                    or {
                        "nodes_created": 0,
                        "relationships_created": 0,
                        "properties_set": 0,
                        "labels_added": 0,
                    }
                )
            )
        )

    def consume(self):
        return self._summary

    def single(self):
        return self._record


class FakeTransaction:
    def __init__(self, driver):
        self.driver = driver

    def run(self, query, **kwargs):
        self.driver.calls.append((query, kwargs))
        if "UNWIND $rows" in query:
            is_relationship = "MERGE (source)-[rel:" in query
            count = len(kwargs["rows"])
            return FakeResult(
                counters={
                    "nodes_created": 0 if is_relationship else count,
                    "relationships_created": count if is_relationship else 0,
                    "properties_set": count,
                    "labels_added": 0,
                }
            )
        if "RETURN count(node) AS count" in query:
            expected = 1 if self.driver.wrong_count else 2
            return FakeResult({"count": expected})
        if "source.project_id IS NULL" in query:
            return FakeResult({"count": 0})
        if "RETURN count(rel) AS count" in query:
            return FakeResult({"count": 2})
        if "RETURN nodes, count(rel) AS relationships" in query:
            return FakeResult({"nodes": 4, "relationships": 2})
        raise AssertionError(f"Unexpected query: {query}")


class FakeSession:
    def __init__(self, driver):
        self.driver = driver

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute_write(self, callback, *args):
        return callback(FakeTransaction(self.driver), *args)


class GenericGraphLoaderTest(unittest.TestCase):
    def test_every_merge_and_match_is_scoped_by_project(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            datasets = DatasetWorkspace(root / "uploads")
            schemas = SchemaRegistry(root / "schemas")
            mappings = MappingWorkspace(root / "mappings", datasets, schemas)
            encoded = base64.b64encode(
                (
                    b"equipment_id,part_id,capacity,is_active\n"
                    b"EQ-1,P-1,10,true\n"
                    b"EQ-2,P-2,20,false\n"
                )
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
                        "properties": {
                            "equipment_id": "equipment_id",
                            "capacity": "capacity",
                            "is_active": "is_active",
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
                        "source_file": "events.csv",
                        "source_key": "equipment_id",
                        "target_key": "part_id",
                        "properties": {"capacity": "capacity"},
                        "property_types": {"capacity": "INTEGER"},
                    }
                ],
            }
            mappings.approve(
                "factory-demo", upload["upload_id"], mapping
            )
            driver = FakeDriver()
            result = GenericGraphLoader(
                datasets, mappings, batch_size=1
            ).load(
                driver, "factory-demo", upload["upload_id"]
            )
            self.assertTrue(result["integrity"]["project_scope_applied"])
            self.assertTrue(result["integrity"]["transactional"])
            self.assertEqual(
                result["integrity"]["expected"],
                result["integrity"]["actual"],
            )
            self.assertEqual(
                result["integrity"]["cross_project_relationship_count"],
                0,
            )
            self.assertEqual(driver.session_kwargs["default_access_mode"], "WRITE")
            data_calls = [
                (query, kwargs)
                for query, kwargs in driver.calls
                if "UNWIND $rows" in query
            ]
            self.assertEqual(len(data_calls), 6)
            for query, kwargs in data_calls:
                self.assertIn("project_id", query)
                self.assertEqual(kwargs["project_id"], "factory-demo")
            relationship_query = next(
                query for query, _ in data_calls if "`PROCESSED`" in query
            )
            self.assertIn("rel.`capacity`", relationship_query)
            equipment_rows = [
                kwargs["rows"][0]
                for query, kwargs in data_calls
                if "MERGE (node:`Equipment`" in query
            ]
            self.assertEqual(equipment_rows[0]["capacity"], 10)
            self.assertIs(equipment_rows[0]["is_active"], True)
            self.assertIs(equipment_rows[1]["is_active"], False)
            self.assertEqual(
                result["dry_run"]["relationships"]["PROCESSED"][
                    "projected_rows"
                ],
                2,
            )
            stored = GenericGraphLoader(
                datasets, mappings
            ).reports.get("factory-demo", upload["upload_id"])
            self.assertEqual(stored["status"], "loaded")
            self.assertTrue(Path(result["report_path"]).exists())

    def test_approved_normalized_file_hash_is_rechecked_before_load(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            datasets = DatasetWorkspace(root / "uploads")
            schemas = SchemaRegistry(root / "schemas")
            mappings = MappingWorkspace(root / "mappings", datasets, schemas)
            encoded = base64.b64encode(
                b"equipment_id\nEQ-1\n"
            ).decode()
            upload = datasets.profile_upload(
                "factory-demo",
                [{"filename": "equipment.csv", "content_base64": encoded}],
            )
            mapping = {
                "nodes": [
                    {
                        "label": "Equipment",
                        "source_file": "equipment.csv",
                        "identity": "equipment_id",
                        "properties": {
                            "equipment_id": "equipment_id"
                        },
                    }
                ],
                "relationships": [],
            }
            mappings.approve(
                "factory-demo", upload["upload_id"], mapping
            )
            source = (
                root
                / "uploads"
                / "factory-demo"
                / upload["upload_id"]
                / "source"
                / "equipment.csv"
            )
            source.write_text("equipment_id\nEQ-2\n", encoding="utf-8")
            driver = FakeDriver()
            with self.assertRaisesRegex(ValueError, "변경"):
                GenericGraphLoader(datasets, mappings).load(
                    driver, "factory-demo", upload["upload_id"]
                )
            self.assertEqual(driver.calls, [])
            report = GenericGraphLoader(
                datasets, mappings
            ).reports.get("factory-demo", upload["upload_id"])
            self.assertEqual(report["status"], "load_failed")
            self.assertTrue(report["rollback_expected"])

    def test_integrity_mismatch_marks_failed_and_aborts_transaction(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            datasets = DatasetWorkspace(root / "uploads")
            schemas = SchemaRegistry(root / "schemas")
            mappings = MappingWorkspace(root / "mappings", datasets, schemas)
            encoded = base64.b64encode(
                b"equipment_id\nEQ-1\nEQ-2\n"
            ).decode()
            upload = datasets.profile_upload(
                "factory-demo",
                [{"filename": "equipment.csv", "content_base64": encoded}],
            )
            mappings.approve(
                "factory-demo",
                upload["upload_id"],
                {
                    "nodes": [
                        {
                            "label": "Equipment",
                            "source_file": "equipment.csv",
                            "identity": "equipment_id",
                            "properties": {
                                "equipment_id": "equipment_id"
                            },
                        }
                    ],
                    "relationships": [],
                },
            )
            driver = FakeDriver(wrong_count=True)
            loader = GenericGraphLoader(datasets, mappings)
            with self.assertRaisesRegex(RuntimeError, "reconciliation"):
                loader.load(driver, "factory-demo", upload["upload_id"])
            report = loader.reports.get(
                "factory-demo", upload["upload_id"]
            )
            self.assertEqual(report["status"], "load_failed")
            self.assertEqual(report["error_type"], "RuntimeError")
