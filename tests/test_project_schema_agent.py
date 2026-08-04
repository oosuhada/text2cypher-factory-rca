import tempfile
import unittest
from pathlib import Path

import yaml

from backend.app.agent.workflow import TextToCypherAgent


class RecordingModel:
    def __init__(self):
        self.schemas = []

    def generate(self, question, schema, few_shot_examples):
        self.schemas.append(schema)
        return (
            "MATCH (e:Equipment {project_id: 'equipment-history'}) "
            "RETURN e"
        )

    def correct(self, question, schema, statement, errors):
        self.schemas.append(schema)
        return statement


class PassingGraph:
    def explain(self, statement):
        return []

    def execute(self, statement):
        return [{"equipment_id": "EQ-1"}]


class ProjectSchemaAgentTest(unittest.TestCase):
    def test_custom_schema_and_project_scope_are_applied(self):
        with tempfile.TemporaryDirectory() as temp:
            examples = Path(temp) / "examples.yml"
            examples.write_text(
                yaml.safe_dump({"questions": []}), encoding="utf-8"
            )
            model = RecordingModel()
            agent = TextToCypherAgent(
                model,
                PassingGraph(),
                examples,
                schema_context="Equipment {equipment_id: STRING}",
                semantic_validator=lambda _question, _statement: [],
                project_id="equipment-history",
            )
            result = agent.invoke("고장 이력이 있는 장비를 보여줘")
            self.assertEqual(result["status"], "success")
            self.assertIn("Equipment", model.schemas[0])

    def test_unscoped_query_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            examples = Path(temp) / "examples.yml"
            examples.write_text("questions: []\n", encoding="utf-8")
            model = RecordingModel()
            model.generate = lambda *_args: "MATCH (e:Equipment) RETURN e"
            agent = TextToCypherAgent(
                model,
                PassingGraph(),
                examples,
                schema_context="Equipment {equipment_id: STRING}",
                semantic_validator=lambda _question, _statement: [],
                project_id="equipment-history",
                max_attempts=1,
            )
            result = agent.invoke("장비를 보여줘")
            self.assertEqual(result["status"], "failed")
            self.assertTrue(result["errors"][0].startswith("PROJECT_SCOPE"))
