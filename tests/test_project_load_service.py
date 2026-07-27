import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.app.services.project_load_service import (
    ProjectGraphLoadService,
)


class _Driver:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class _Loader:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    def load(self, driver, project_id, upload_id):
        self.calls.append((driver, project_id, upload_id))
        if self.fail:
            raise RuntimeError("load failed")
        return {
            "project_id": project_id,
            "upload_id": upload_id,
            "status": "loaded",
            "integrity": {
                "scoped_node_count": 3,
                "scoped_relationship_count": 2,
                "project_scope_applied": True,
            },
        }


class ProjectGraphLoadServiceTest(unittest.TestCase):
    def test_homebrew_mode_uses_direct_bolt_connection(self):
        with tempfile.TemporaryDirectory() as temp:
            service = ProjectGraphLoadService(
                Path(temp),
                _Loader(),
                mode_control="homebrew",
            )
            with patch.dict(
                "os.environ",
                {
                    "NEO4J_URI": "neo4j://localhost:7687",
                    "NEO4J_PASSWORD": "test-secret",
                },
                clear=False,
            ):
                uri, database, username, password = (
                    service._neo4j_settings()
                )
        self.assertEqual(uri, "bolt://localhost:7687")
        self.assertEqual(database, "neo4j")
        self.assertEqual(username, "neo4j")
        self.assertEqual(password, "test-secret")

    def test_homebrew_mode_is_restored_after_success(self):
        with tempfile.TemporaryDirectory() as temp:
            modes = []
            drivers = [_Driver(), _Driver()]
            service = ProjectGraphLoadService(
                Path(temp),
                _Loader(),
                mode_switcher=modes.append,
                mode_control="homebrew",
            )
            with patch.object(
                service,
                "_wait_for_driver",
                side_effect=drivers,
            ):
                result = service.load("factory-demo", "upload-1")
        self.assertEqual(modes, ["loader", "reader"])
        self.assertTrue(result["reader_mode_restored"])
        self.assertTrue(all(driver.closed for driver in drivers))

    def test_homebrew_mode_is_restored_after_load_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            modes = []
            drivers = [_Driver(), _Driver()]
            service = ProjectGraphLoadService(
                Path(temp),
                _Loader(fail=True),
                mode_switcher=modes.append,
                mode_control="homebrew",
            )
            with patch.object(
                service,
                "_wait_for_driver",
                side_effect=drivers,
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "load failed"
                ):
                    service.load("factory-demo", "upload-1")
        self.assertEqual(modes, ["loader", "reader"])
        self.assertTrue(all(driver.closed for driver in drivers))

    def test_writable_server_mode_does_not_restart_database(self):
        with tempfile.TemporaryDirectory() as temp:
            modes = []
            driver = _Driver()
            service = ProjectGraphLoadService(
                Path(temp),
                _Loader(),
                mode_switcher=modes.append,
                mode_control="none",
            )
            with patch.object(
                service,
                "_wait_for_driver",
                return_value=driver,
            ):
                result = service.load("factory-demo", "upload-1")
        self.assertEqual(modes, [])
        self.assertFalse(result["reader_mode_restored"])
        self.assertTrue(driver.closed)
