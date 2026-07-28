import base64
import tempfile
import unittest
from pathlib import Path

from backend.app.ingestion import DatasetWorkspace


class DatasetWorkspaceTest(unittest.TestCase):
    def test_profiles_and_persists_project_scoped_csv(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = DatasetWorkspace(Path(temp))
            payload = base64.b64encode(
                b"equipment_id,temperature,status\nEQ-1,42.5,ok\nEQ-2,,fail\n"
            ).decode()
            result = workspace.profile_upload(
                "equipment-history",
                [{"filename": "events.csv", "content_base64": payload}],
            )
            self.assertEqual(result["files"][0]["row_count"], 2)
            columns = {
                row["name"]: row for row in result["files"][0]["columns"]
            }
            self.assertTrue(columns["equipment_id"]["identity_candidate"])
            self.assertEqual(columns["temperature"]["inferred_type"], "FLOAT")
            self.assertEqual(columns["temperature"]["missing_count"], 1)
            self.assertEqual(
                result["files"][0]["profile_version"], "1.0"
            )
            self.assertEqual(
                result["files"][0]["quality"]["missing_cell_count"], 1
            )
            self.assertEqual(
                workspace.get("equipment-history", result["upload_id"])["status"],
                "profiled",
            )
            self.assertEqual(len(workspace.list("equipment-history")), 1)

    def test_rejects_unsafe_or_unsupported_upload(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = DatasetWorkspace(Path(temp))
            payload = base64.b64encode(b"x\n1\n").decode()
            with self.assertRaisesRegex(ValueError, "안전하지 않은"):
                workspace.profile_upload(
                    "demo-project",
                    [{"filename": "../x.csv", "content_base64": payload}],
                )
            with self.assertRaisesRegex(ValueError, "CSV와 JSON"):
                workspace.profile_upload(
                    "demo-project",
                    [{"filename": "x.exe", "content_base64": payload}],
                )
            self.assertEqual(workspace.list("demo-project"), [])

    def test_failed_multi_file_upload_is_rolled_back(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = DatasetWorkspace(Path(temp))
            valid = base64.b64encode(b"id\n1\n").decode()
            with self.assertRaisesRegex(ValueError, "base64"):
                workspace.profile_upload(
                    "demo-project",
                    [
                        {
                            "filename": "valid.csv",
                            "content_base64": valid,
                        },
                        {
                            "filename": "broken.csv",
                            "content_base64": "***",
                        },
                    ],
                )
            project_root = Path(temp) / "demo-project"
            self.assertEqual(list(project_root.glob("*")), [])
