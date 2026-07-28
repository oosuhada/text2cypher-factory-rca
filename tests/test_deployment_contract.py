import os
from pathlib import Path
import unittest
from unittest.mock import patch

import yaml

from backend.app.services.diagnostics import _neo4j_endpoint


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DeploymentContractTest(unittest.TestCase):
    def test_container_compose_has_health_gated_stack(self):
        compose_path = (
            PROJECT_ROOT / "infra" / "docker-compose.product.yml"
        )
        compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
        services = compose["services"]
        self.assertEqual(
            {"neo4j", "initialize", "api", "streamlit", "web"},
            set(services),
        )
        self.assertEqual(
            services["initialize"]["depends_on"]["neo4j"]["condition"],
            "service_healthy",
        )
        self.assertEqual(
            services["api"]["depends_on"]["initialize"]["condition"],
            "service_completed_successfully",
        )
        self.assertIn("healthcheck", services["api"])
        self.assertIn("healthcheck", services["streamlit"])

    def test_images_use_non_root_runtime_users(self):
        python_dockerfile = (
            PROJECT_ROOT / "backend" / "Dockerfile"
        ).read_text(encoding="utf-8")
        web_dockerfile = (
            PROJECT_ROOT / "web" / "Dockerfile"
        ).read_text(encoding="utf-8")
        self.assertIn("USER factorygraph", python_dockerfile)
        self.assertIn("USER factorygraph", web_dockerfile)
        self.assertIn(
            "COPY --chown=factorygraph:factorygraph schemas /app/schemas",
            python_dockerfile,
        )
        self.assertIn(
            "COPY --chown=factorygraph:factorygraph prompts /app/prompts",
            python_dockerfile,
        )
        self.assertNotIn("COPY .env", python_dockerfile)
        self.assertNotIn("COPY .env", web_dockerfile)

    def test_diagnostics_follow_runtime_neo4j_uri(self):
        with patch.dict(
            os.environ,
            {"NEO4J_URI": "neo4j://graph-db.internal:7777"},
        ):
            self.assertEqual(
                _neo4j_endpoint(), ("graph-db.internal", 7777)
            )

    def test_react_home_exposes_complete_project_workspace_journey(self):
        home = (PROJECT_ROOT / "web" / "app" / "page.tsx").read_text(
            encoding="utf-8"
        )
        overview = (
            PROJECT_ROOT / "web" / "components" / "project-overview.tsx"
        ).read_text(encoding="utf-8")
        workspace = (
            PROJECT_ROOT / "web" / "components" / "project-workspace.tsx"
        ).read_text(encoding="utf-8")
        navigation = (
            PROJECT_ROOT
            / "web"
            / "components"
            / "use-project-navigation.ts"
        ).read_text(encoding="utf-8")
        query = (
            PROJECT_ROOT / "web" / "components" / "query-workspace.tsx"
        ).read_text(encoding="utf-8")
        route = (
            PROJECT_ROOT / "web" / "app" / "projects" / "page.tsx"
        ).read_text(encoding="utf-8")
        self.assertIn("<ProjectOverview />", home)
        self.assertIn("읽기 전용 검증", home)
        self.assertIn("결과표·관계 근거", home)
        self.assertNotIn("Gold Question", home)
        self.assertIn("최근 프로젝트", overview)
        self.assertIn('href="/projects"', overview)
        self.assertIn('href="/projects#new-project"', overview)
        self.assertIn("모든 프로젝트", workspace)
        self.assertIn("새 프로젝트 만들기", workspace)
        self.assertNotIn('href="/query"', overview)
        self.assertNotIn('href="/query"', workspace)
        self.assertIn(
            'openProject(project.project_id, "recommended")',
            overview,
        )
        self.assertIn(
            'openProject(project.project_id, "recommended")',
            workspace,
        )
        self.assertIn('openProject(project.project_id, "query")', overview)
        self.assertIn('openProject(project.project_id, "query")', workspace)
        self.assertIn("await switchProject(projectId)", navigation)
        self.assertIn("router.push(projectRoute(", navigation)
        self.assertIn("project_id: projectId", navigation)
        self.assertIn(
            'searchParams.get("project_id")',
            query,
        )
        self.assertIn("projectContextPending", query)
        self.assertIn("<ProjectWorkspace />", route)

    def test_streamlit_uses_url_backed_project_navigation(self):
        app_source = (
            PROJECT_ROOT / "frontend" / "streamlit_app.py"
        ).read_text(encoding="utf-8")
        navigation_source = (
            PROJECT_ROOT / "frontend" / "navigation.py"
        ).read_text(encoding="utf-8")
        session_source = (
            PROJECT_ROOT / "frontend" / "session_state.py"
        ).read_text(encoding="utf-8")
        page_source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(
                (PROJECT_ROOT / "frontend" / "pages").glob("*.py")
            )
        )
        source = "\n".join(
            (app_source, navigation_source, session_source, page_source)
        )
        self.assertIn('return f"/?workspace=', navigation_source)
        self.assertIn("render_workspace_link(", navigation_source)
        self.assertIn(
            'st.query_params.get("workspace")',
            navigation_source,
        )
        self.assertIn("navigation_widget_revision", source)
        self.assertIn("Internal Operations Console", page_source)
        self.assertIn("React 제품 UI 열기", page_source)
        self.assertIn(
            'st.session_state.get("latest_project_upload") or {}',
            page_source,
        )


if __name__ == "__main__":
    unittest.main()
