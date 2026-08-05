from pathlib import Path
from time import sleep
import unittest

from backend.app.agent.examples import GoldExampleStore
from backend.app.agent.model import (
    GeminiCypherModel,
    OpenAICypherModel,
    SequenceCypherModel,
    normalize_model_cypher,
)
from backend.app.agent.workflow import TextToCypherAgent
from backend.app.security.read_only import (
    detect_ambiguous_request,
    detect_write_request,
    validate_read_only,
)
from backend.app.agent.semantic_validation import (
    build_domain_validator,
    validate_domain_semantics,
)


class FakeReadGraph:
    def __init__(self):
        self.executed: list[str] = []
        self.explained: list[str] = []

    def explain(self, statement: str) -> list[str]:
        self.explained.append(statement)
        if "BROKEN" in statement:
            return ["EXPLAIN_ERROR: Invalid input"]
        return []

    def execute(self, statement: str) -> list[dict]:
        self.executed.append(statement)
        return [{"part_id": "300002"}]


class RaisingModel:
    def generate(self, *_args):
        raise RuntimeError("provider unavailable")

    def correct(self, *_args):
        raise RuntimeError("provider unavailable")


class SlowModel:
    def generate(self, *_args):
        sleep(0.01)
        return "RETURN 1 AS count"

    def correct(self, *_args):
        return "RETURN 1 AS count"


class RaisingGraph(FakeReadGraph):
    def __init__(self, *, explain=False, execute=False):
        super().__init__()
        self.raise_explain = explain
        self.raise_execute = execute

    def explain(self, statement):
        if self.raise_explain:
            raise RuntimeError("database unavailable")
        return super().explain(statement)

    def execute(self, statement):
        if self.raise_execute:
            raise RuntimeError("database unavailable")
        return super().execute(statement)


class FakeChat:
    def __init__(self, content):
        self.content = content
        self.prompts = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return type("Response", (), {"content": self.content})()


class FakeGeminiModels:
    def __init__(self):
        self.requests = []

    def generate_content(self, **kwargs):
        self.requests.append(kwargs)
        usage = type(
            "Usage",
            (),
            {"prompt_token_count": 100, "candidates_token_count": 20},
        )()
        return type(
            "Response",
            (),
            {
                "text": "```cypher\nRETURN 1 AS count\n```",
                "usage_metadata": usage,
            },
        )()


class FakeGeminiClient:
    def __init__(self):
        self.models = FakeGeminiModels()


class TextToCypherTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project_root = Path(__file__).resolve().parents[1]
        cls.examples_path = (
            cls.project_root / "evaluation" / "gold_questions.yml"
        )

    def test_gold_examples_reload_and_keep_map_braces(self):
        store = GoldExampleStore(self.examples_path)
        self.assertEqual(len(store.load()), 15)
        formatted = store.format_for_prompt(
            "압력검사에 실패한 완제품을 보여줘.", k=15
        )
        self.assertIn("{feature: 'pressure'}", formatted)

    def test_normalizes_markdown_fence(self):
        self.assertEqual(
            normalize_model_cypher("```cypher\nMATCH (n) RETURN n\n```"),
            "MATCH (n) RETURN n",
        )

    def test_read_only_validator_blocks_mutations_and_commands(self):
        blocked = [
            "MATCH (n) DELETE n",
            "MATCH (n) SET n.name = 'x' RETURN n",
            "MERGE (n:Part {part_id: 'x'}) RETURN n",
            "CALL db.labels()",
            "MATCH (n) RETURN n; MATCH (m) RETURN m",
            "LOAD CSV FROM 'file:///x.csv' AS row RETURN row",
        ]
        for statement in blocked:
            with self.subTest(statement=statement):
                self.assertTrue(validate_read_only(statement))

    def test_keywords_in_literals_do_not_trigger_write_block(self):
        self.assertEqual(
            validate_read_only(
                "MATCH (n:Part {part_id: 'DELETE SET MERGE'}) RETURN n"
            ),
            [],
        )

    def test_write_intent_guard(self):
        self.assertTrue(detect_write_request("완제품 데이터를 전부 삭제해줘"))
        self.assertFalse(detect_write_request("불량 부품을 조회해줘"))

    def test_ambiguity_guard(self):
        self.assertTrue(detect_ambiguous_request("문제 있는 부품 찾아줘."))
        self.assertFalse(
            detect_ambiguous_request(
                "압력검사에 실패한 완제품의 구성품을 보여줘."
            )
        )

    def test_domain_semantics_rejects_display_name_as_equipment_id(self):
        errors = validate_domain_semantics(
            "DMC 50H 장비 실행을 보여줘.",
            "MATCH (e:Equipment {equipment_id: 'DMC 50H'}) RETURN e",
        )
        self.assertTrue(errors)
        self.assertIn("Equipment.name", errors[0])

    def test_question_alignment_requires_component_role(self):
        errors = validate_domain_semantics(
            "구성품과 역할을 보여줘.",
            "MATCH (c:Cylinder)-[:ASSEMBLED_FROM]->(p:Part) "
            "RETURN p.part_id",
        )
        self.assertTrue(
            any(error.startswith("QUESTION_ALIGNMENT") for error in errors)
        )

    def test_schema_domain_validator_rejects_translated_storage_value(self):
        validator = build_domain_validator(
            {
                "domain_values": {
                    "Equipment.equipment_type": [
                        "press",
                        "milling",
                    ]
                }
            }
        )
        errors = validator(
            "프레스 설비의 정비 건수를 알려줘.",
            "MATCH (e:Equipment {equipment_type: '프레스'}) RETURN e",
        )
        self.assertTrue(errors)
        self.assertIn("'press'", errors[0])

    def test_schema_domain_validator_is_label_aware(self):
        validator = build_domain_validator(
            {
                "domain_values": {
                    "Process.name": ["assembly"],
                    "Equipment.name": ["DMC 50H"],
                }
            }
        )
        errors = validator(
            "조립 공정을 보여줘.",
            "MATCH (p:Process {name: 'assembly'}) RETURN p.name",
        )
        self.assertEqual(errors, [])

    def test_user_supplied_unknown_id_is_allowed_to_return_empty(self):
        validator = build_domain_validator(
            {
                "nodes": [
                    {
                        "label": "Equipment",
                        "identity": "equipment_id",
                    }
                ],
                "domain_values": {
                    "Equipment.equipment_id": ["known-equipment"],
                }
            }
        )
        errors = validator(
            "존재하지 않는 장비 ZZZ-999를 보여줘.",
            "MATCH (e:Equipment {equipment_id: 'ZZZ-999'}) RETURN e",
        )
        self.assertEqual(errors, [])

    def test_domain_semantics_rejects_equipment_to_anomaly_topology(self):
        statements = (
            "MATCH (run:ProcessRun)-[:RUN_ON]->(equipment:Equipment) "
            "-[:CLASSIFIED_AS]->(anomaly:AnomalyClass) RETURN count(run)",
            "MATCH (run:ProcessRun)-[:RUN_ON]->(:Equipment {name:'DMC 50H'}) "
            "-[:CLASSIFIED_AS]->(anomaly:AnomalyClass) RETURN count(run)",
        )
        for statement in statements:
            with self.subTest(statement=statement):
                errors = validate_domain_semantics(
                    "Kasto SBA 2의 비정상 실행 수를 알려줘.",
                    statement,
                )
                self.assertTrue(
                    any(
                        error.startswith("SCHEMA_TOPOLOGY")
                        for error in errors
                    )
                )

    def test_ambiguous_request_asks_for_clarification_before_model(self):
        graph = FakeReadGraph()
        agent = TextToCypherAgent(
            SequenceCypherModel([]),
            graph,
            self.examples_path,
        )
        result = agent.invoke("문제 있는 부품 찾아줘.")
        self.assertEqual(result["status"], "needs_clarification")
        self.assertEqual(result["attempts"], 0)
        self.assertEqual(graph.explained, [])
        self.assertEqual(graph.executed, [])

    def test_openai_adapter_accepts_free_question_and_normalizes_response(self):
        fake_chat = FakeChat(
            "자유 질문 결과입니다.\n```cypher\n"
            "MATCH (n:Part) RETURN n.part_id LIMIT 3\n```"
        )
        model = OpenAICypherModel(chat=fake_chat)
        statement = model.generate(
            "최근 부품 세 개를 보여줘.",
            "Part(part_id)",
            "",
        )
        self.assertEqual(
            statement,
            "MATCH (n:Part) RETURN n.part_id LIMIT 3",
        )
        self.assertEqual(len(fake_chat.prompts), 1)

    def test_gemini_adapter_tracks_tokens_latency_and_estimated_cost(self):
        client = FakeGeminiClient()
        model = GeminiCypherModel(client=client)
        statement = model.generate("질문", "스키마", "")
        usage = model.usage_summary()
        self.assertEqual(statement, "RETURN 1 AS count")
        self.assertEqual(usage["call_count"], 1)
        self.assertEqual(usage["input_tokens"], 100)
        self.assertEqual(usage["output_tokens"], 20)
        self.assertAlmostEqual(usage["estimated_cost_usd"], 0.000027)
        self.assertEqual(len(client.models.requests), 1)

    def test_valid_query_executes_once(self):
        graph = FakeReadGraph()
        agent = TextToCypherAgent(
            SequenceCypherModel(["MATCH (n:Part) RETURN n.part_id LIMIT 1"]),
            graph,
            self.examples_path,
        )
        result = agent.invoke("부품 하나를 보여줘")
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(len(graph.explained), 1)
        self.assertEqual(len(graph.executed), 1)
        verified_hash = result["validated_statement_sha256"]
        execution_event = next(
            event
            for event in result["trace"]
            if event["step"] == "execute_cypher"
        )
        self.assertTrue(verified_hash)
        self.assertEqual(
            execution_event["verified_statement_sha256"],
            verified_hash,
        )

    def test_syntax_error_is_corrected_and_revalidated(self):
        graph = FakeReadGraph()
        agent = TextToCypherAgent(
            SequenceCypherModel(
                [
                    "MATCH BROKEN RETURN",
                    "MATCH (n:Part) RETURN n.part_id LIMIT 1",
                ]
            ),
            graph,
            self.examples_path,
        )
        result = agent.invoke("부품 하나를 보여줘")
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["attempts"], 2)
        self.assertEqual(len(graph.explained), 2)
        self.assertEqual(len(graph.executed), 1)
        self.assertIn(
            "correct_cypher",
            [event["step"] for event in result["trace"]],
        )

    def test_persistent_error_never_executes(self):
        graph = FakeReadGraph()
        agent = TextToCypherAgent(
            SequenceCypherModel(
                ["MATCH BROKEN RETURN", "MATCH BROKEN RETURN"]
            ),
            graph,
            self.examples_path,
            max_attempts=2,
        )
        result = agent.invoke("부품 하나를 보여줘")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["attempts"], 2)
        self.assertEqual(graph.executed, [])

    def test_generated_write_query_is_blocked_without_correction(self):
        graph = FakeReadGraph()
        agent = TextToCypherAgent(
            SequenceCypherModel(["MATCH (n) DELETE n"]),
            graph,
            self.examples_path,
        )
        result = agent.invoke("노드 상태를 정리해줘")
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(graph.explained, [])
        self.assertEqual(graph.executed, [])

    def test_write_request_is_blocked_before_model(self):
        graph = FakeReadGraph()
        agent = TextToCypherAgent(
            SequenceCypherModel([]),
            graph,
            self.examples_path,
        )
        result = agent.invoke("압력 실패 데이터를 삭제해줘")
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["attempts"], 0)
        self.assertEqual(graph.executed, [])

    def test_model_failure_returns_failed_contract_without_execution(self):
        graph = FakeReadGraph()
        agent = TextToCypherAgent(
            RaisingModel(),
            graph,
            self.examples_path,
        )
        result = agent.invoke("부품 하나를 보여줘")
        self.assertEqual(result["status"], "failed")
        self.assertTrue(result["errors"][0].startswith("MODEL_ERROR"))
        self.assertEqual(graph.explained, [])
        self.assertEqual(graph.executed, [])

    def test_explain_failure_never_executes(self):
        graph = RaisingGraph(explain=True)
        agent = TextToCypherAgent(
            SequenceCypherModel(["RETURN 1 AS count"]),
            graph,
            self.examples_path,
            max_attempts=1,
        )
        result = agent.invoke("전체 건수를 알려줘")
        self.assertEqual(result["status"], "failed")
        self.assertTrue(result["errors"][0].startswith("EXPLAIN_ERROR"))
        self.assertEqual(graph.executed, [])

    def test_execution_failure_returns_failed_contract(self):
        graph = RaisingGraph(execute=True)
        agent = TextToCypherAgent(
            SequenceCypherModel(["RETURN 1 AS count"]),
            graph,
            self.examples_path,
        )
        result = agent.invoke("전체 건수를 알려줘")
        self.assertEqual(result["status"], "failed")
        self.assertTrue(result["errors"][0].startswith("EXECUTION_ERROR"))
        self.assertFalse(
            next(
                event
                for event in result["trace"]
                if event["step"] == "execute_cypher"
            )["executed"]
        )

    def test_pipeline_timeout_after_generation_never_executes(self):
        graph = FakeReadGraph()
        agent = TextToCypherAgent(
            SlowModel(),
            graph,
            self.examples_path,
            timeout_seconds=0.001,
        )
        result = agent.invoke("전체 건수를 알려줘")
        self.assertEqual(result["status"], "failed")
        self.assertTrue(result["errors"][0].startswith("PIPELINE_TIMEOUT"))
        self.assertEqual(graph.explained, [])
        self.assertEqual(graph.executed, [])


if __name__ == "__main__":
    unittest.main()
