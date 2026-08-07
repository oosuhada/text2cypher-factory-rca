from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import yaml

from backend.app.agent.project_router import ProjectRouter, route_accuracy
from backend.app.projects import ProjectRegistry
from backend.app.schema_registry import SchemaRegistry


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ProjectRouterTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.projects = ProjectRegistry(Path(self.temp.name) / "projects.sqlite3")
        self.projects.ensure_default()
        self.projects.create(
            project_id="equipment-history",
            name="Equipment Maintenance History",
            domain_type="maintenance",
            dataset_name="Synthetic Equipment History",
            schema_version="1.0",
            status="ready",
            description="설비 정비, 수리, 교체, 점검, 다운타임과 기술자 이력",
            source_version="synthetic-equipment-history-v1",
            _bootstrap=True,
        )
        self.router = ProjectRouter(
            self.projects,
            SchemaRegistry(PROJECT_ROOT / "schemas"),
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_explicit_project_bypasses_automatic_routing(self):
        decision = self.router.route(
            "정비 이력을 보여줘.",
            explicit_project_id="cip-dmd",
        )
        self.assertEqual(decision.status, "explicit_project")
        self.assertEqual(decision.selected_project_id, "cip-dmd")
        self.assertEqual(decision.confidence, 1.0)
        self.assertEqual(decision.mode, "bypass")
        self.assertEqual(decision.candidates, ())

    def test_manufacturing_question_routes_to_cip_dmd(self):
        decision = self.router.route(
            "압력검사에 실패한 완제품의 구성품과 공정을 보여줘."
        )
        self.assertEqual(decision.status, "routed")
        self.assertEqual(decision.selected_project_id, "cip-dmd")
        self.assertGreaterEqual(decision.confidence or 0, 0.08)
        self.assertEqual(decision.candidates[0]["project_id"], "cip-dmd")

    def test_maintenance_question_routes_to_equipment_history(self):
        decision = self.router.route(
            "EQ-PRESS-01의 정비 비용과 담당 기술자를 보여줘."
        )
        self.assertEqual(decision.status, "routed")
        self.assertEqual(
            decision.selected_project_id,
            "equipment-history",
        )
        self.assertEqual(
            decision.candidates[0]["project_id"],
            "equipment-history",
        )

    def test_low_confidence_question_requires_clarification(self):
        decision = self.router.route("전체 현황을 요약해줘.")
        self.assertEqual(decision.status, "needs_clarification")
        self.assertIsNone(decision.selected_project_id)
        self.assertGreaterEqual(len(decision.candidates), 1)

    def test_non_ready_projects_are_not_routing_candidates(self):
        self.projects.create(
            project_id="draft-project",
            name="Draft Project",
            domain_type="maintenance",
            dataset_name="Draft",
        )
        project_ids = {
            candidate.project_id for candidate in self.router.candidates()
        }
        self.assertNotIn("draft-project", project_ids)

    def test_router_evaluation_meets_release_thresholds(self):
        document = yaml.safe_load(
            (PROJECT_ROOT / "evaluation" / "project_router.yml").read_text(
                encoding="utf-8"
            )
        )
        report = route_accuracy(self.router, document["cases"])
        thresholds = document["thresholds"]
        self.assertGreaterEqual(
            report["top1_accuracy"], thresholds["top1_accuracy"]
        )
        self.assertGreaterEqual(
            report["topk_accuracy"], thresholds["topk_accuracy"]
        )
        self.assertGreaterEqual(
            report["clarification_accuracy"],
            thresholds["clarification_accuracy"],
        )


if __name__ == "__main__":
    unittest.main()
