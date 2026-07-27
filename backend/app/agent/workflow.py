"""LangGraph workflow: generate → validate → correct/revalidate → execute."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from backend.app.security.read_only import (
    detect_ambiguous_request,
    detect_write_request,
    validate_read_only,
)

from .examples import GoldExampleStore
from .graph import ReadGraph
from .model import CypherModel, GoldCypherModel, normalize_model_cypher
from .schema import SCHEMA_CONTEXT
from .semantic_validation import validate_domain_semantics
from .state import CypherState


def _event(step: str, **details: Any) -> list[dict[str, Any]]:
    return [{"step": step, **details}]


def create_text2cypher_agent(
    model: CypherModel,
    graph: ReadGraph,
    examples: GoldExampleStore,
    max_attempts: int = 3,
):
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")

    def generate_cypher(state: CypherState) -> dict[str, Any]:
        question = state["question"]
        few_shot = examples.format_for_prompt(question)
        statement = normalize_model_cypher(
            model.generate(question, SCHEMA_CONTEXT, few_shot)
        )
        return {
            "statement": statement,
            "status": "running",
            "trace": _event("generate_cypher"),
        }

    def validate_cypher(state: CypherState) -> dict[str, Any]:
        statement = state.get("statement", "")
        attempts = state.get("attempts", 0) + 1
        errors = validate_read_only(statement)
        blocked = any(
            error.startswith(("WRITE_CLAUSE", "DISALLOWED_COMMAND", "MULTIPLE"))
            for error in errors
        )
        if not errors:
            errors.extend(
                validate_domain_semantics(state["question"], statement)
            )
        if not errors:
            errors.extend(graph.explain(statement))

        if blocked:
            next_action: Literal["correct", "execute", "end"] = "end"
            status = "blocked"
        elif not errors:
            next_action = "execute"
            status = "running"
        elif attempts < state["max_attempts"]:
            next_action = "correct"
            status = "running"
        else:
            next_action = "end"
            status = "failed"
        return {
            "errors": errors,
            "attempts": attempts,
            "next_action": next_action,
            "status": status,
            "trace": _event(
                "validate_cypher",
                attempt=attempts,
                passed=not errors,
                errors=errors,
            ),
        }

    def correct_cypher(state: CypherState) -> dict[str, Any]:
        statement = normalize_model_cypher(
            model.correct(
                state["question"],
                SCHEMA_CONTEXT,
                state.get("statement", ""),
                state.get("errors", []),
            )
        )
        return {
            "statement": statement,
            "trace": _event(
                "correct_cypher", after_attempt=state.get("attempts", 0)
            ),
        }

    def execute_cypher(state: CypherState) -> dict[str, Any]:
        # The graph adapter repeats the read-only check immediately before
        # execution, so no future edge can accidentally bypass validation.
        records = graph.execute(state["statement"])
        return {
            "records": records,
            "status": "success" if records else "empty",
            "trace": _event("execute_cypher", row_count=len(records)),
        }

    def route_after_validation(
        state: CypherState,
    ) -> Literal["correct_cypher", "execute_cypher", "__end__"]:
        return {
            "correct": "correct_cypher",
            "execute": "execute_cypher",
            "end": "__end__",
        }.get(state.get("next_action", "end"), "__end__")

    builder = StateGraph(CypherState)
    builder.add_node("generate_cypher", generate_cypher)
    builder.add_node("validate_cypher", validate_cypher)
    builder.add_node("correct_cypher", correct_cypher)
    builder.add_node("execute_cypher", execute_cypher)
    builder.add_edge(START, "generate_cypher")
    builder.add_edge("generate_cypher", "validate_cypher")
    builder.add_conditional_edges(
        "validate_cypher", route_after_validation
    )
    builder.add_edge("correct_cypher", "validate_cypher")
    builder.add_edge("execute_cypher", END)
    return builder.compile()


class TextToCypherAgent:
    def __init__(
        self,
        model: CypherModel,
        graph: ReadGraph,
        examples_path: Path,
        max_attempts: int = 3,
    ):
        self.max_attempts = max_attempts
        self.model = model
        self.workflow = create_text2cypher_agent(
            model=model,
            graph=graph,
            examples=GoldExampleStore(examples_path),
            max_attempts=max_attempts,
        )

    def invoke(self, question: str) -> CypherState:
        started = perf_counter()
        normalized_question = question.strip()
        if detect_ambiguous_request(normalized_question):
            return {
                "question": normalized_question,
                "statement": "",
                "errors": [
                    "AMBIGUOUS_REQUEST: Specify a part type, quality feature, "
                    "or process anomaly."
                ],
                "attempts": 0,
                "max_attempts": self.max_attempts,
                "records": [],
                "status": "needs_clarification",
                "next_action": "end",
                "trace": [
                    {
                        "step": "guard_question",
                        "needs_clarification": True,
                    }
                ],
                "elapsed_ms": int((perf_counter() - started) * 1000),
            }
        if detect_write_request(question):
            return {
                "question": normalized_question,
                "statement": "",
                "errors": ["WRITE_REQUEST: Data modification requests are blocked."],
                "attempts": 0,
                "max_attempts": self.max_attempts,
                "records": [],
                "status": "blocked",
                "next_action": "end",
                "trace": [{"step": "guard_question", "blocked": True}],
                "elapsed_ms": int((perf_counter() - started) * 1000),
            }
        if isinstance(self.model, GoldCypherModel) and not self.model.supports(
            normalized_question
        ):
            return {
                "question": normalized_question,
                "statement": "",
                "errors": [
                    "GOLD_UNSUPPORTED: Gold demo only supports registered "
                    "example questions."
                ],
                "attempts": 0,
                "max_attempts": self.max_attempts,
                "records": [],
                "status": "unsupported",
                "next_action": "end",
                "trace": [
                    {
                        "step": "guard_question",
                        "unsupported": True,
                    }
                ],
                "elapsed_ms": int((perf_counter() - started) * 1000),
            }
        result: CypherState = self.workflow.invoke(
            {
                "question": normalized_question,
                "statement": "",
                "errors": [],
                "attempts": 0,
                "max_attempts": self.max_attempts,
                "records": [],
                "status": "running",
                "next_action": "end",
                "trace": [],
            }
        )
        result["elapsed_ms"] = int((perf_counter() - started) * 1000)
        return result
