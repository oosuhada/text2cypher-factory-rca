from __future__ import annotations

from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = PROJECT_ROOT / "web" / "components"


class ReactComponentArchitectureTest(unittest.TestCase):
    def test_query_workspace_is_an_orchestrator(self):
        source = (COMPONENTS / "query-workspace.tsx").read_text(
            encoding="utf-8"
        )
        self.assertLessEqual(len(source.splitlines()), 150)
        for component in (
            "QuerySidebar",
            "QueryConversationPanel",
            "QueryEvidencePanel",
            "useQuerySession",
        ):
            self.assertIn(component, source)

    def test_query_modules_have_single_responsibilities(self):
        required = {
            "query-config.ts",
            "use-query-session.ts",
            "query-sidebar.tsx",
            "query-conversation-panel.tsx",
            "query-evidence-panel.tsx",
            "expert-review.tsx",
        }
        actual = {
            path.name
            for path in (COMPONENTS / "query").iterdir()
            if path.is_file()
        }
        self.assertTrue(required.issubset(actual))

    def test_project_workspaces_share_cards_and_form(self):
        overview = (COMPONENTS / "project-overview.tsx").read_text(
            encoding="utf-8"
        )
        workspace = (COMPONENTS / "project-workspace.tsx").read_text(
            encoding="utf-8"
        )
        self.assertIn("ProjectCard", overview)
        self.assertIn("ProjectCard", workspace)
        self.assertIn("ProjectCreateForm", workspace)
        self.assertLessEqual(len(overview.splitlines()), 120)
        self.assertLessEqual(len(workspace.splitlines()), 100)

    def test_large_legacy_query_component_does_not_regress(self):
        line_counts = {
            path.name: len(path.read_text(encoding="utf-8").splitlines())
            for path in (COMPONENTS / "query").glob("*.*")
        }
        self.assertLessEqual(max(line_counts.values()), 320)


if __name__ == "__main__":
    unittest.main()
