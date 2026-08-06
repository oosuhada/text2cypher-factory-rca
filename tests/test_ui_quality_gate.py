import json
from pathlib import Path
import unittest

from frontend.design_system import Action, Role, can_perform
from frontend.quality_gate import (
    current_visual_contract,
    role_journey_contract,
    run_ui_quality_gate,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class UiQualityGateTest(unittest.TestCase):
    def test_all_roles_have_explicit_navigation_and_action_contracts(self):
        journeys = role_journey_contract()
        self.assertEqual(set(journeys), {role.value for role in Role})
        self.assertNotIn("Data Sources", journeys[Role.VIEWER.value])
        self.assertIn("Evaluations", journeys[Role.ANALYST.value])
        self.assertIn("Approval Queue", journeys[Role.DOMAIN_EXPERT.value])
        self.assertIn("Pipeline", journeys[Role.DATA_STEWARD.value])
        self.assertIn("Admin", journeys[Role.ADMIN.value])
        self.assertFalse(can_perform(Role.VIEWER, Action.RERUN_QUERY))
        self.assertTrue(
            can_perform(Role.DOMAIN_EXPERT, Action.REVIEW_RESULT)
        )
        self.assertTrue(can_perform(Role.ADMIN, Action.MANAGE_PLATFORM))

    def test_visual_contract_baseline_is_current(self):
        baseline = json.loads(
            (
                PROJECT_ROOT / "evaluation" / "ui_visual_baseline.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(baseline, current_visual_contract())

    def test_release_gate_covers_two_domains_and_failure_fallback(self):
        report = run_ui_quality_gate(PROJECT_ROOT)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(
            report["projects"], ["cip-dmd", "equipment-history"]
        )
        self.assertEqual(report["failure_fallback"], "PASS")


if __name__ == "__main__":
    unittest.main()
