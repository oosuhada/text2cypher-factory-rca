from __future__ import annotations

import unittest

from scripts.cross_surface_release_gate import (
    run_gate,
    validate_critical_ux,
    validate_react_architecture,
    validate_streamlit_architecture,
)


class CrossSurfaceReleaseGateTest(unittest.TestCase):
    def test_streamlit_architecture_contract(self):
        result = validate_streamlit_architecture()
        self.assertLessEqual(result["entrypoint_lines"], 150)
        self.assertEqual(result["workspace_modules"], 10)
        self.assertEqual(result["legacy_redirects"], 10)
        self.assertEqual(result["automatic_sidebar"], 0)

    def test_react_architecture_contract(self):
        result = validate_react_architecture()
        self.assertLessEqual(result["query_orchestrator_lines"], 150)
        self.assertGreaterEqual(result["query_modules"], 6)

    def test_critical_ux_contract(self):
        result = validate_critical_ux()
        self.assertEqual(result["product_surface_boundary"], "PASS")
        self.assertEqual(result["evidence_default"], "table")
        self.assertEqual(result["expert_review"], "collapsed")

    def test_full_gate(self):
        self.assertEqual(run_gate()["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
