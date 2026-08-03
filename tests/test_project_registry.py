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
        with self.assertRaisesRegex(ValueError, "활성 프로젝트"):
            self.registry.update(
                "equipment-history", status="archived"
            )
        self.registry.activate("cip-dmd")
        archived = self.registry.update(
            "equipment-history", status="archived"
        )
        self.assertEqual(archived["status"], "archived")

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
