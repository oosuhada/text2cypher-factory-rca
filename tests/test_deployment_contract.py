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


if __name__ == "__main__":
    unittest.main()
