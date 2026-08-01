from pathlib import Path
import unittest

from backend.app.etl.extract import audit_quality_csvs, extract_records
from backend.app.etl.transform import transform_records
from backend.app.etl.validate import EXPECTED_COUNTS, validate_payload


class TransformTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        project_root = Path(__file__).resolve().parents[1]
        extracted = extract_records(
            project_root / "data" / "raw" / "cip_dmd"
        )
        cls.csv_audit = audit_quality_csvs(
            project_root / "data" / "raw" / "cip_dmd"
        )
        cls.payload = transform_records(extracted)

    def test_expected_counts(self):
        self.assertEqual(self.payload.counts(), EXPECTED_COUNTS)

    def test_payload_validation(self):
        result = validate_payload(self.payload)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["quarantined_count"], 35)

    def test_unique_ids(self):
        self.assertEqual(
            len({row["part_id"] for row in self.payload.parts}),
            len(self.payload.parts),
        )
        self.assertEqual(
            len({row["run_id"] for row in self.payload.process_runs}),
            len(self.payload.process_runs),
        )
        self.assertEqual(
            len(
                {
                    row["measurement_id"]
                    for row in self.payload.measurements
                }
            ),
            len(self.payload.measurements),
        )

    def test_normalized_process_names(self):
        names = {row["name"] for row in self.payload.processes}
        self.assertEqual(
            names,
            {"saw", "cnc_milling_machine", "cnc_lathe", "assembly"},
        )

    def test_equipment_and_anomaly_taxonomy(self):
        self.assertEqual(
            {row["equipment_id"] for row in self.payload.equipment},
            {"kasto-sba-2", "dmc-50h", "index-c65"},
        )
        self.assertEqual(
            {row["code"] for row in self.payload.anomaly_classes},
            {"0", "1", "2", "3"},
        )
        self.assertEqual(
            sum(not row["qc_pass"] for row in self.payload.measurements),
            443,
        )
        self.assertTrue(
            all(
                row["anomaly_code"] in {"0", "1", "2", "3"}
                for row in self.payload.process_runs
            )
        )

    def test_quality_csv_audit(self):
        self.assertEqual(len(self.csv_audit), 4)
        self.assertTrue(
            all(
                result["status"] == "PASS"
                for result in self.csv_audit.values()
            )
        )


if __name__ == "__main__":
    unittest.main()
