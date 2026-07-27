from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

from backend.app.etl.validate import EXPECTED_COUNTS
from backend.app.services.data_intake_service import (
    DataIntakeService,
    REQUIRED_SOURCE_PATHS,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_ROOT = PROJECT_ROOT / "data" / "raw" / "cip_dmd"


def build_bundle(
    *,
    include_all: bool = True,
    unsafe_member: bool = False,
) -> bytes:
    target = BytesIO()
    paths = (
        REQUIRED_SOURCE_PATHS
        if include_all
        else REQUIRED_SOURCE_PATHS[:-1]
    )
    with zipfile.ZipFile(
        target,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for relative_path in paths:
            archive.writestr(
                f"CiP-DMD/{relative_path}",
                (CANONICAL_ROOT / relative_path).read_bytes(),
            )
        if unsafe_member:
            archive.writestr("../outside.txt", b"blocked")
    return target.getvalue()


class DataIntakeServiceTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        temporary_root = Path(self.temporary.name)
        self.mode_events = []
        self.service = DataIntakeService(
            PROJECT_ROOT,
            processed_root=temporary_root / "processed",
            intake_root=temporary_root / "intake",
            mode_switcher=self.mode_events.append,
        )

    def tearDown(self):
        self.temporary.cleanup()

    def test_stage_and_dry_run_fixed_bundle(self):
        staged = self.service.stage_archive(
            "cip-dmd.zip",
            build_bundle(),
        )
        self.assertEqual(staged["status"], "staged")
        self.assertTrue(staged["canonical_bundle_match"])
        self.assertEqual(
            len(staged["source_files"]),
            len(REQUIRED_SOURCE_PATHS),
        )

        dry_run = self.service.dry_run(staged["run_id"])
        self.assertEqual(dry_run["status"], "dry_run_pass")
        self.assertEqual(dry_run["validation"]["status"], "PASS")
        self.assertEqual(
            dry_run["validation"]["quarantined_count"],
            35,
        )
        self.assertIn("approval_token", dry_run)

        record = json.loads(
            (
                self.service.intake_root
                / staged["run_id"]
                / "run.json"
            ).read_text(encoding="utf-8")
        )
        self.assertNotIn("approval_token", record)
        self.assertTrue(record["approval_token_sha256"])
        self.assertEqual(len(self.service.list_runs()), 1)
        self.assertEqual(
            [event["event"] for event in self.service.recent_audit_events()],
            ["dry_run", "stage"],
        )

    def test_reference_archive_is_deterministic_and_stageable(self):
        first = self.service.build_reference_archive()
        second = self.service.build_reference_archive()
        self.assertEqual(first, second)
        staged = self.service.stage_archive("reference.zip", first)
        self.assertTrue(staged["canonical_bundle_match"])

    def test_missing_required_file_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "필수 파일 매핑 실패"):
            self.service.stage_archive(
                "incomplete.zip",
                build_bundle(include_all=False),
            )

    def test_zip_path_traversal_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "안전하지 않은 ZIP 경로"):
            self.service.stage_archive(
                "unsafe.zip",
                build_bundle(unsafe_member=True),
            )

    def test_invalid_approval_never_switches_database_mode(self):
        staged = self.service.stage_archive("bundle.zip", build_bundle())
        dry_run = self.service.dry_run(staged["run_id"])
        with self.assertRaisesRegex(RuntimeError, "승인 토큰"):
            self.service.load(
                staged["run_id"],
                approval_token="wrong-token",
                confirmation=f"LOAD {staged['run_id']}",
            )
        self.assertEqual(self.mode_events, [])
        self.assertNotEqual(dry_run["approval_token"], "wrong-token")

    def test_approved_load_restores_reader_mode(self):
        staged = self.service.stage_archive("bundle.zip", build_bundle())
        dry_run = self.service.dry_run(staged["run_id"])
        drivers = [Mock(), Mock(), Mock()]
        self.service._wait_for_driver = Mock(
            side_effect=[
                (drivers[0], "neo4j"),
                (drivers[1], "neo4j"),
                (drivers[2], "neo4j"),
            ]
        )
        with (
            patch(
                "backend.app.services.data_intake_service.graph_counts",
                side_effect=[
                    dict(EXPECTED_COUNTS),
                    dict(EXPECTED_COUNTS),
                ],
            ),
            patch(
                "backend.app.services.data_intake_service.load_payload",
                return_value={"parts": {"nodes_created": 0}},
            ),
        ):
            loaded = self.service.load(
                staged["run_id"],
                approval_token=dry_run["approval_token"],
                confirmation=f"LOAD {staged['run_id']}",
            )
        self.assertEqual(loaded["status"], "load_pass")
        self.assertTrue(loaded["reader_mode_restored"])
        self.assertEqual(self.mode_events, ["loader", "reader"])
        for driver in drivers:
            driver.close.assert_called_once()

    def test_load_failure_still_restores_reader_mode(self):
        staged = self.service.stage_archive("bundle.zip", build_bundle())
        dry_run = self.service.dry_run(staged["run_id"])
        drivers = [Mock(), Mock(), Mock()]
        self.service._wait_for_driver = Mock(
            side_effect=[
                (drivers[0], "neo4j"),
                (drivers[1], "neo4j"),
                (drivers[2], "neo4j"),
            ]
        )
        with (
            patch(
                "backend.app.services.data_intake_service.graph_counts",
                return_value=dict(EXPECTED_COUNTS),
            ),
            patch(
                "backend.app.services.data_intake_service.load_payload",
                side_effect=RuntimeError("simulated load error"),
            ),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "simulated load error",
            ):
                self.service.load(
                    staged["run_id"],
                    approval_token=dry_run["approval_token"],
                    confirmation=f"LOAD {staged['run_id']}",
                )
        self.assertEqual(self.mode_events, ["loader", "reader"])
        failed = self.service.list_runs()[0]
        self.assertEqual(failed["status"], "load_failed")


if __name__ == "__main__":
    unittest.main()
