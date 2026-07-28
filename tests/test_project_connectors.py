import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend.app.projects import Neo4jConnectorService, ProjectRegistry
from backend.app.schema_registry import SchemaRegistry


class FakeIntrospector:
    def inspect(self, **payload):
        self.payload = payload
        return {
            "fingerprint": "a" * 64,
            "counts": {"nodes": 12, "relationships": 18},
            "schema": {
                "project_id": payload["project_id"],
                "version": "introspected-aaaaaaaaaaaa",
                "source_version": "a" * 64,
                "isolation_mode": "database",
                "title": "External maintenance graph",
                "nodes": [
                    {
                        "label": "Equipment",
                        "identity": "equipment_id",
                        "properties": {
                            "equipment_id": "STRING",
                            "name": "STRING",
                        },
                        "required_properties": ["equipment_id"],
                    }
                ],
                "relationships": [],
                "query_scenarios": [],
            },
        }


class Neo4jConnectorServiceTest(unittest.TestCase):
    def test_validate_and_approve_external_graph_without_storing_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            projects = ProjectRegistry(root / "projects.sqlite3")
            projects.create(
                project_id="external-maintenance",
                name="External maintenance",
                domain_type="maintenance",
                dataset_name="Existing Neo4j",
                source_type="neo4j",
            )
            schemas = SchemaRegistry(root / "schemas")
            introspector = FakeIntrospector()
            service = Neo4jConnectorService(
                root / "connectors",
                projects,
                schemas,
                introspector=introspector,
            )
            with patch.dict(
                os.environ, {"EXTERNAL_NEO4J_PASSWORD": "secret-value"}
            ):
                validated = service.validate(
                    "external-maintenance",
                    uri="neo4j+s://graph.example.com",
                    database="maintenance",
                    username="reader",
                    password_env="EXTERNAL_NEO4J_PASSWORD",
                )
                self.assertEqual(validated["status"], "validated")
                self.assertNotIn(
                    "secret-value",
                    (
                        root
                        / "connectors"
                        / f"{validated['connector_id']}.json"
                    ).read_text(),
                )
                approved = service.approve(
                    "external-maintenance", validated["connector_id"]
                )
                connection = service.connection("external-maintenance")

            self.assertEqual(approved["status"], "approved")
            self.assertEqual(
                projects.require("external-maintenance")["status"],
                "evaluation_required",
            )
            self.assertEqual(
                schemas.load("external-maintenance")["isolation_mode"],
                "database",
            )
            self.assertEqual(connection["database"], "maintenance")
            artifacts = projects.artifacts("external-maintenance")
            self.assertEqual(artifacts["integrity"]["status"], "verified")
            self.assertEqual(artifacts["read_only"]["status"], "verified")

    def test_rejects_credentials_in_uri_and_missing_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            projects = ProjectRegistry(root / "projects.sqlite3")
            projects.create(
                project_id="external-graph",
                name="External",
                domain_type="maintenance",
                dataset_name="Neo4j",
                source_type="neo4j",
            )
            service = Neo4jConnectorService(
                root / "connectors",
                projects,
                SchemaRegistry(root / "schemas"),
                introspector=FakeIntrospector(),
            )
            with self.assertRaisesRegex(ValueError, "인증정보"):
                service.validate(
                    "external-graph",
                    uri="neo4j://user:pass@localhost:7687",
                    database="neo4j",
                    username="reader",
                    password_env="MISSING_NEO4J_PASSWORD",
                )
            with self.assertRaisesRegex(ValueError, "환경변수"):
                service.validate(
                    "external-graph",
                    uri="neo4j://localhost:7687",
                    database="neo4j",
                    username="reader",
                    password_env="MISSING_NEO4J_PASSWORD",
                )
