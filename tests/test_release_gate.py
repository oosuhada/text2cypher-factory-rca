from pathlib import Path
import tempfile
import unittest

from scripts.release_gate import (
    scan_secrets,
    validate_openapi,
    validate_release_documents,
    validate_traceability,
)


class ReleaseGateTest(unittest.TestCase):
    def test_openapi_and_required_documents_are_complete(self):
        openapi = validate_openapi()
        self.assertGreaterEqual(openapi["paths"], 10)
        self.assertGreaterEqual(openapi["schemas"], 2)
        self.assertGreaterEqual(validate_release_documents(), 8)

    def test_p3_traceability_has_no_incomplete_requirement(self):
        self.assertGreaterEqual(validate_traceability(), 30)

    def test_secret_scanner_detects_known_key_shape(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.txt"
            path.write_text(
                "token=" + "sk-" + ("x" * 32),
                encoding="utf-8",
            )
            findings = scan_secrets([path])
        self.assertEqual(len(findings), 1)
        self.assertTrue(findings[0].startswith("openai-key:"))
