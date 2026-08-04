from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend.app.services.project_dashboard_service import (
    ProjectDashboardService,
)


class _Session:
    def __init__(self, queries):
        self.queries = queries

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def run(self, query, **parameters):
        self.queries.append((query, parameters))
        if "RETURN nodes" in query:
            return [{"nodes": 4, "relationships": 3}]
        if "UNWIND labels" in query:
            return [{"label": "Equipment", "count": 4}]
        return [{"relationship_type": "USED_BY", "count": 3}]


class _Driver:
    def __init__(self):
        self.queries = []

    def session(self, **_kwargs):
        return _Session(self.queries)


class ProjectDashboardServiceTest(unittest.TestCase):
    def test_every_graph_metric_is_scoped_to_project(self):
        with TemporaryDirectory() as temp_dir:
            driver = _Driver()
            snapshot = ProjectDashboardService(
                driver=driver,
                database="neo4j",
                project_id="equipment-history",
                audit_log_path=Path(temp_dir) / "audit.jsonl",
            ).snapshot()

        self.assertEqual(snapshot["project_id"], "equipment-history")
        self.assertEqual(snapshot["totals"]["nodes"], 4)
        self.assertTrue(snapshot["integrity"]["project_scoped"])
        self.assertEqual(len(driver.queries), 3)
        for query, parameters in driver.queries:
            self.assertIn("project_id", query)
            self.assertEqual(
                parameters["project_id"], "equipment-history"
            )
