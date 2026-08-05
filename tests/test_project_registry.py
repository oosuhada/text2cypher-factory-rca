import tempfile
import unittest
from pathlib import Path

from backend.app.projects import ProjectRegistry


class ProjectRegistryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.registry = ProjectRegistry(
            Path(self.temp.name) / "projects.sqlite3"
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_default_create_activate_and_persist(self):
        default = self.registry.ensure_default()
        self.assertEqual(default["project_id"], "cip-dmd")
        self.assertTrue(self.registry.active()["is_active"])
        reopened = ProjectRegistry(self.registry.path)
        self.assertEqual(reopened.active_project_id(), "cip-dmd")

    def test_multiple_projects_are_isolated_and_archiving_active_is_blocked(self):
        self.registry.ensure_default()
        second = self.registry.create(
            project_id="equipment-history",
            name="Equipment History",
            domain_type="maintenance",
            dataset_name="Synthetic Maintenance",
        )
        self.assertFalse(second["is_active"])
        activated = self.registry.activate("equipment-history")
        self.assertTrue(activated["is_active"])
        profiled = self.registry.transition(
            "equipment-history", "profiling", reason="test_profile"
        )
        self.assertEqual(profiled["status"], "profiling")
        mapped = self.registry.transition(
            "equipment-history",
            "mapping_review",
            reason="test_mapping_review",
        )
        self.assertEqual(mapped["status"], "mapping_review")
        with self.assertRaisesRegex(ValueError, "활성 프로젝트"):
            self.registry.update(
                "equipment-history", status="archived"
            )
        self.registry.activate("cip-dmd")
        archived = self.registry.update(
            "equipment-history", status="archived"
        )
        self.assertEqual(archived["status"], "archived")

    def test_state_machine_and_versioned_artifacts_prevent_ready_bypass(self):
        with self.assertRaisesRegex(ValueError, "draft 상태"):
            self.registry.create(
                project_id="unsafe-ready",
                name="Unsafe",
                domain_type="maintenance",
                dataset_name="data",
                status="ready",
            )
        self.registry.create(
            project_id="safe-project",
            name="Safe",
            domain_type="maintenance",
            dataset_name="data",
        )
        with self.assertRaisesRegex(ValueError, "허용되지 않는 상태 전이"):
            self.registry.transition(
                "safe-project", "ready", reason="bypass"
            )
        self.registry.record_artifact(
            "safe-project",
            "schema",
            version="1.0",
            fingerprint="a" * 64,
            metadata={"source_version": "v1"},
        )
        artifacts = self.registry.artifacts("safe-project")
        self.assertEqual(artifacts["schema"]["version"], "1.0")
        self.assertEqual(
            self.registry.transition_history("safe-project")[-1][
                "to_status"
            ],
            "draft",
        )

    def test_invalid_and_duplicate_ids_are_rejected(self):
        with self.assertRaises(ValueError):
            self.registry.create(
                project_id="../bad",
                name="Bad",
                domain_type="x",
                dataset_name="x",
            )
        self.registry.ensure_default()
        with self.assertRaisesRegex(ValueError, "이미 존재"):
            self.registry.create(
                project_id="cip-dmd",
                name="Duplicate",
                domain_type="x",
                dataset_name="x",
            )

    def test_favorite_is_persisted_without_changing_lifecycle(self):
        self.registry.ensure_default()
        updated = self.registry.update("cip-dmd", favorite=True)
        self.assertEqual(updated["favorite"], 1)
        self.assertEqual(updated["status"], "ready")
        reopened = ProjectRegistry(self.registry.path)
        self.assertEqual(reopened.require("cip-dmd")["favorite"], 1)
