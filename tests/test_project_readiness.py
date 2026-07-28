from pathlib import Path
import tempfile
import unittest

from backend.app.ingestion import DatasetWorkspace
from backend.app.mapping import MappingWorkspace
from backend.app.projects import ProjectReadinessService, ProjectRegistry
from backend.app.schema_registry import SchemaRegistry


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ProjectReadinessServiceTest(unittest.TestCase):
    def _service(
        self,
        root: Path,
        projects: ProjectRegistry,
        *,
        nodes: int = 10,
    ) -> ProjectReadinessService:
        datasets = DatasetWorkspace(root / "uploads")
        schemas = SchemaRegistry(PROJECT_ROOT / "schemas")
        mappings = MappingWorkspace(root / "mappings", datasets, schemas)
        return ProjectReadinessService(
            PROJECT_ROOT,
            projects,
            schemas,
            datasets,
            mappings,
            graph_counter=lambda _project_id: {
                "nodes": nodes,
                "relationships": 12,
            },
        )

    def test_draft_project_reports_missing_gates_without_starting_agent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            projects = ProjectRegistry(root / "projects.sqlite3")
            projects.create(
                project_id="empty-project",
                name="Empty",
                domain_type="maintenance",
                dataset_name="Empty",
            )
            report = self._service(root, projects).inspect("empty-project")
            self.assertFalse(report["can_query"])
            self.assertFalse(report["eligible_for_ready"])
            self.assertEqual(report["next_action"], "upload")
            self.assertEqual(report["checks"]["source"]["status"], "FAIL")

    def test_matching_versions_promote_only_from_evaluation_required(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            projects = ProjectRegistry(root / "projects.sqlite3")
            projects.create(
                project_id="equipment-history",
                name="Equipment History",
                domain_type="maintenance",
                dataset_name="Synthetic Maintenance",
                schema_version="1.0",
                source_type="neo4j",
                source_version="synthetic-equipment-history-v1",
                status="evaluation_required",
                _bootstrap=True,
            )
            for artifact_type, version in (
                ("source", "synthetic-equipment-history-v1"),
                ("connector", "connector-v1"),
                ("integrity", "load-v1"),
                ("read_only", "reader-v1"),
            ):
                projects.record_artifact(
                    "equipment-history",
                    artifact_type,
                    version=version,
                )
            service = self._service(root, projects)
            before = service.inspect("equipment-history")
            self.assertTrue(before["eligible_for_ready"])
            self.assertFalse(before["can_query"])
            self.assertEqual(before["next_action"], "activate")

            after = service.promote("equipment-history")
            self.assertTrue(after["can_query"])
            self.assertEqual(after["lifecycle_status"], "ready")
            project = projects.require("equipment-history")
            self.assertEqual(project["prompt_version"], "text2cypher-v1")
            self.assertEqual(project["gold_version"], "1.0")
            self.assertEqual(project["evaluation_version"], "1.0")

    def test_version_mismatch_blocks_promotion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            projects = ProjectRegistry(root / "projects.sqlite3")
            projects.create(
                project_id="equipment-history",
                name="Equipment History",
                domain_type="maintenance",
                dataset_name="Synthetic Maintenance",
                schema_version="1.0",
                source_type="neo4j",
                source_version="stale-source",
                status="evaluation_required",
                _bootstrap=True,
            )
            for artifact_type in (
                "source",
                "connector",
                "integrity",
                "read_only",
            ):
                projects.record_artifact(
                    "equipment-history",
                    artifact_type,
                    version="stale-source",
                )
            service = self._service(root, projects)
            report = service.inspect("equipment-history")
            self.assertEqual(report["checks"]["schema"]["status"], "FAIL")
            with self.assertRaisesRegex(ValueError, "readiness gate"):
                service.promote("equipment-history")
