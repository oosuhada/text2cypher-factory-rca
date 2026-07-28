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

    def test_each_workspace_has_a_page_module(self):
        expected_modules = {
            "audit.py",
            "dashboard.py",
            "data_sources.py",
            "evaluations.py",
            "evidence.py",
            "graph_explorer_page.py",
            "home.py",
            "projects.py",
            "query_studio.py",
            "schema_studio.py",
        }
        actual_modules = {
            path.name
            for path in (FRONTEND_ROOT / "pages").glob("*.py")
            if path.name != "__init__.py"
        }
        self.assertEqual(actual_modules, expected_modules)

    def test_page_modules_do_not_import_the_entrypoint(self):
        for path in (FRONTEND_ROOT / "pages").glob("*.py"):
            source = path.read_text(encoding="utf-8")
            self.assertNotIn(
                "frontend.streamlit_app",
                source,
                msg=f"{path.name} creates a circular entrypoint dependency",
            )

    def test_runtime_resources_are_outside_entrypoint(self):
        runtime_source = (
            FRONTEND_ROOT / "runtime.py"
        ).read_text(encoding="utf-8")
        self.assertIn("def get_services(", runtime_source)
        self.assertIn("def clear_service_cache(", runtime_source)
        self.assertIn("def get_data_intake_service(", runtime_source)


if __name__ == "__main__":
    unittest.main()
