from __future__ import annotations

import ast
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = PROJECT_ROOT / "frontend"


class StreamlitPageArchitectureTest(unittest.TestCase):
    def test_entrypoint_is_router_only(self):
        app_path = FRONTEND_ROOT / "streamlit_app.py"
        source = app_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        function_names = {
            node.name
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
        }
        self.assertEqual(function_names, {"main"})
        self.assertLessEqual(len(source.splitlines()), 150)

    def test_each_workspace_has_an_official_module(self):
        expected_modules = {
            "audit.py",
            "dashboard.py",
            "data_sources.py",
            "evaluations.py",
            "evidence.py",
            "graph_explorer.py",
            "home.py",
            "projects.py",
            "query_studio.py",
            "schema_studio.py",
        }
        actual_modules = {
            path.name
            for path in (FRONTEND_ROOT / "workspaces").glob("*.py")
            if path.name != "__init__.py"
        }
        self.assertEqual(actual_modules, expected_modules)

    def test_entrypoint_uses_hidden_router_and_workspace_boundary(self):
        entrypoint = (FRONTEND_ROOT / "streamlit_app.py").read_text(
            encoding="utf-8"
        )
        router = (FRONTEND_ROOT / "streamlit_router.py").read_text(
            encoding="utf-8"
        )
        console = (FRONTEND_ROOT / "internal_console.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("build_hidden_navigation", entrypoint)
        self.assertIn('st.navigation(pages, position="hidden")', router)
        self.assertIn("frontend.workspaces.", console)
        self.assertNotIn("frontend.pages.", entrypoint + router + console)

    def test_legacy_pages_redirect_to_canonical_workspaces(self):
        expected_redirects = {
            "audit.py": "audit_logs",
            "dashboard.py": "dashboard",
            "data_sources.py": "data_sources",
            "evaluations.py": "evaluations",
            "evidence.py": "query_studio",
            "graph_explorer_page.py": "graph_explorer",
            "home.py": "home",
            "projects.py": "projects",
            "query_studio.py": "query_studio",
            "schema_studio.py": "pipeline",
        }
        for filename, workspace_key in expected_redirects.items():
            source = (FRONTEND_ROOT / "pages" / filename).read_text(
                encoding="utf-8"
            )
            self.assertIn('if __name__ == "__main__":', source)
            self.assertIn("redirect_legacy_page", source)
            self.assertIn(
                f'redirect_legacy_page("{workspace_key}")', source
            )
            self.assertNotIn("frontend.streamlit_app", source)

    def test_automatic_sidebar_navigation_is_disabled(self):
        config = (
            PROJECT_ROOT / ".streamlit" / "config.toml"
        ).read_text(encoding="utf-8")
        self.assertIn("[client]", config)
        self.assertIn("showSidebarNavigation = false", config)

    def test_runtime_resources_are_outside_entrypoint(self):
        runtime_source = (
            FRONTEND_ROOT / "runtime.py"
        ).read_text(encoding="utf-8")
        self.assertIn("def get_services(", runtime_source)
        self.assertIn("def clear_service_cache(", runtime_source)
        self.assertIn("def get_data_intake_service(", runtime_source)


if __name__ == "__main__":
    unittest.main()
