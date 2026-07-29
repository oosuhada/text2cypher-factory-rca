from __future__ import annotations

import unittest

from scripts.product_user_release_gate import (
    load_baseline,
    run_gate,
    validate_accessibility_contracts,
    validate_fixture_contracts,
    validate_internal_console,
    validate_product_routes,
)


class ProductUserReleaseGateTest(unittest.TestCase):
    def setUp(self):
        self.baseline = load_baseline()

    def test_product_route_and_navigation_contract(self):
        result = validate_product_routes(self.baseline)
        self.assertEqual(result["entrypoints"], 1)
        self.assertEqual(result["navigation_items"], 4)
        self.assertEqual(result["forbidden_copy_source_hits"], 0)
        self.assertEqual(len(result["routes"]), 5)

    def test_internal_console_contract(self):
        result = validate_internal_console(self.baseline)
        self.assertEqual(result["navigation_groups"], 1)
        self.assertEqual(result["production_workspaces"], 9)
        self.assertEqual(result["demo_workspaces"], 9)
        self.assertEqual(result["automatic_sidebar_items"], 0)

    def test_accessibility_contract(self):
        result = validate_accessibility_contracts(self.baseline)
        self.assertEqual(result["status"], "PASS")
        self.assertIn("focus-visible", result["contracts"])
        self.assertIn("form-label", result["contracts"])

    def test_fixture_and_core_journey_contract(self):
        result = validate_fixture_contracts(self.baseline)
        self.assertGreaterEqual(result["long_project_name_characters"], 60)
        self.assertGreaterEqual(result["large_result_rows"], 100)
        self.assertEqual(result["critical_journeys"], 8)

    def test_automatic_pass_does_not_claim_manual_ready(self):
        result = run_gate()
        self.assertEqual(result["automatic_gate"], "PASS")
        self.assertEqual(result["manual_user_review"], "PENDING")
        self.assertFalse(result["final_ready"])
        self.assertEqual(
            result["release_decision"],
            "AUTOMATION PASS · MANUAL REVIEW PENDING",
        )


if __name__ == "__main__":
    unittest.main()
