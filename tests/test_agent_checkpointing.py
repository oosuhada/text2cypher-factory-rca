from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend.app.agent.checkpoints import RunCheckpointStore
from backend.app.agent.model import CypherModel
from backend.app.agent.state import (
    AGENT_STATE_SCHEMA_VERSION,
    migrate_agent_state,
)
from backend.app.agent.workflow import TextToCypherAgent


class FixedModel(CypherModel):
    def generate(self, question: str, schema: str, examples: str) -> str:
        return "MATCH (n:Part) RETURN n.part_id LIMIT 1"

    def correct(
        self,
        question: str,
        schema: str,
        statement: str,
        errors: list[str],
    ) -> str:
        return statement


class RecordingGraph:
    def __init__(self):
        self.explained: list[str] = []
        self.executed: list[str] = []

    def explain(self, statement: str) -> list[str]:
        self.explained.append(statement)
        return []

    def execute(self, statement: str) -> list[dict[str, str]]:
        self.executed.append(statement)
        return [{"part_id": "P-001"}]


def examples_file(root: Path) -> Path:
    path = root / "gold.yml"
    path.write_text(
        "questions:\n"
        "  - id: T1\n"
        "    category: parts\n"
        "    question: 부품 하나를 보여줘\n"
        "    gold_cypher: MATCH (n:Part) RETURN n.part_id LIMIT 1\n",
        encoding="utf-8",
    )
    return path


class AgentCheckpointingTest(unittest.TestCase):
    def test_expanded_state_contains_stage3_context_sections(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            graph = RecordingGraph()
            agent = TextToCypherAgent(
                FixedModel(),
                graph,
                examples_file(root),
                metadata={
                    "schema_version": "1.1",
                    "prompt_version": "text2cypher-v1",
                },
            )
            result = agent.invoke(
                "부품 하나를 보여줘",
                run_id="run-context-1",
                organization_id="factory-a",
                user_id="analyst-1",
                roles=("Analyst",),
            )

        self.assertEqual(
            result["state_schema_version"], AGENT_STATE_SCHEMA_VERSION
        )
        self.assertEqual(result["organization"]["organization_id"], "factory-a")
        self.assertEqual(result["user"]["user_id"], "analyst-1")
        self.assertEqual(result["user"]["roles"], ["Analyst"])
        self.assertEqual(result["project"]["project_id"], "cip-dmd")
        self.assertEqual(result["run"]["run_id"], "run-context-1")
        self.assertEqual(result["run"]["status"], "success")
        self.assertEqual(result["routing"]["status"], "explicit_project")
        self.assertEqual(result["schema"]["schema_version"], "1.1")
        self.assertGreaterEqual(len(result["tool_trace"]), 4)
        self.assertIn("graph", result["evidence"])
        self.assertEqual(
            result["recommendation"]["status"], "not_requested"
        )
        self.assertEqual(result["approval"]["status"], "not_required")

    def test_legacy_state_is_migrated_to_current_schema(self):
        legacy = {
            "question": "부품 하나를 보여줘",
            "status": "success",
            "records": [{"part_id": "P-001"}],
            "metadata": {
                "project_id": "equipment-history",
                "schema_version": "1.0",
            },
        }
        migrated = migrate_agent_state(legacy)

        self.assertEqual(
            migrated["state_schema_version"], AGENT_STATE_SCHEMA_VERSION
        )
        self.assertEqual(
            migrated["project"]["project_id"], "equipment-history"
        )
        self.assertTrue(migrated["run"]["run_id"].startswith("legacy-"))
        self.assertEqual(migrated["routing"]["status"], "explicit_project")
        self.assertEqual(migrated["approval"]["status"], "not_required")

    def test_future_state_schema_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "newer than this application"):
            migrate_agent_state(
                {"state_schema_version": AGENT_STATE_SCHEMA_VERSION + 1}
            )

    def test_sqlite_checkpoint_resumes_after_agent_restart(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            checkpoint_path = root / "checkpoints.sqlite3"
            gold_path = examples_file(root)

            first_graph = RecordingGraph()
            first_store = RunCheckpointStore.sqlite(checkpoint_path)
            first_agent = TextToCypherAgent(
                FixedModel(),
                first_graph,
                gold_path,
                checkpointer=first_store.saver,
                checkpoint_namespace="stage3-resume-test",
                interrupt_before=["execute_cypher"],
            )
            paused = first_agent.invoke(
                "부품 하나를 보여줘",
                run_id="resumable-run-1",
                organization_id="factory-a",
                user_id="analyst-1",
            )
            persisted_before_restart = first_agent.state("resumable-run-1")
            first_store.close()

            self.assertEqual(paused["status"], "paused")
            self.assertEqual(first_graph.executed, [])
            self.assertEqual(
                persisted_before_restart["checkpoint"]["next"],
                ["execute_cypher"],
            )

            second_graph = RecordingGraph()
            second_store = RunCheckpointStore.sqlite(checkpoint_path)
            second_agent = TextToCypherAgent(
                FixedModel(),
                second_graph,
                gold_path,
                checkpointer=second_store.saver,
                checkpoint_namespace="stage3-resume-test",
            )
            resumed = second_agent.resume("resumable-run-1")
            persisted_after_restart = second_agent.state("resumable-run-1")
            second_store.close()

        self.assertEqual(resumed["status"], "success")
        self.assertEqual(resumed["records"], [{"part_id": "P-001"}])
        self.assertEqual(len(second_graph.executed), 1)
        self.assertEqual(persisted_after_restart["checkpoint"]["next"], [])
        self.assertEqual(
            persisted_after_restart["run"]["status"], "success"
        )


if __name__ == "__main__":
    unittest.main()
