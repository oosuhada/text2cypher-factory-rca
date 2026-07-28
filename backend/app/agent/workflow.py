"""LangGraph workflow: generate → validate → correct/revalidate → execute."""

from __future__ import annotations

import hashlib
from pathlib import Path
import re
from time import perf_counter
from typing import Any, Callable, Literal

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


def _statement_hash(statement: str) -> str:
    return hashlib.sha256(statement.encode("utf-8")).hexdigest()


def has_project_scope(statement: str, project_id: str) -> bool:
    """Require an executable project property predicate, not a comment."""
    without_comments = re.sub(
        r"(?m)//.*$|/\*.*?\*/",
        " ",
        statement,
        flags=re.DOTALL,
    )
    property_name = r"(?:\bproject_id\b|`project_id`)"
    quoted_project = re.escape(project_id)
    return bool(
        re.search(
            rf"{property_name}\s*(?::|=)\s*(['\"]){quoted_project}\1",
            without_comments,
            flags=re.IGNORECASE,
        )
    )


def create_text2cypher_agent(
    model: CypherModel,
    graph: ReadGraph,
    examples: GoldExampleStore,
    max_attempts: int = 3,
    schema_context: str = SCHEMA_CONTEXT,
    semantic_validator: Callable[[str, str], list[str]] = validate_domain_semantics,
    project_id: str = "cip-dmd",
    few_shot_count: int = 6,
):
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")

    def deadline_error(state: CypherState) -> str | None:
        deadline = state.get("deadline_monotonic")
        if deadline is not None and perf_counter() >= deadline:
            return "PIPELINE_TIMEOUT: Text-to-Cypher processing deadline exceeded."
        return None

    def generate_cypher(state: CypherState) -> dict[str, Any]:
        if error := deadline_error(state):
            return {
                "errors": [error],
                "status": "failed",
                "next_action": "end",
                "validated_statement_sha256": "",
                "trace": _event("generate_cypher", failed=True, error=error),
            }
        question = state["question"]
        few_shot = (
            examples.format_for_prompt(question, k=few_shot_count)
            if few_shot_count > 0
            else ""
        )
        try:
            statement = normalize_model_cypher(
                model.generate(question, schema_context, few_shot)
            )
        except Exception as exception:
            error = f"MODEL_ERROR: {type(exception).__name__}: {exception}"
            return {
                "statement": "",
                "errors": [error],
                "status": "failed",
                "next_action": "end",
                "validated_statement_sha256": "",
                "trace": _event("generate_cypher", failed=True, error=error),
            }
        if error := deadline_error(state):
            return {
                "statement": statement,
                "errors": [error],
                "status": "failed",
                "next_action": "end",
                "validated_statement_sha256": "",
                "trace": _event("generate_cypher", failed=True, error=error),
            }
        return {
            "statement": statement,
            "statement_history": [
                {
                    "kind": "generated",
                    "attempt": 1,
                    "statement": statement,
                }
            ],
            "errors": [],
            "status": "running",
            "next_action": "validate",
            "validated_statement_sha256": "",
            "trace": _event(
                "generate_cypher",
                few_shot_count=(
                    min(few_shot_count, len(examples.load()))
                    if few_shot_count > 0
                    else 0
                ),
            ),
        }

    def validate_cypher(state: CypherState) -> dict[str, Any]:
        statement = state.get("statement", "")
        attempts = state.get("attempts", 0) + 1
        if error := deadline_error(state):
            return {
                "errors": [error],
                "attempts": attempts,
                "next_action": "end",
                "status": "failed",
                "validated_statement_sha256": "",
                "trace": _event(
                    "validate_cypher",
                    attempt=attempts,
                    passed=False,
                    errors=[error],
                ),
            }
        errors = validate_read_only(statement)
        blocked = any(
            error.startswith(("WRITE_CLAUSE", "DISALLOWED_COMMAND", "MULTIPLE"))
            for error in errors
        )
        if not errors:
            try:
                errors.extend(
                    semantic_validator(state["question"], statement)
                )
            except Exception as exception:
                errors.append(
                    "VALIDATION_ERROR: "
                    f"{type(exception).__name__}: {exception}"
                )
        if (
            not errors
            and project_id != "cip-dmd"
            and not has_project_scope(statement, project_id)
        ):
            errors.append(
                "PROJECT_SCOPE: Query must restrict graph access to "
                f"project_id {project_id!r}."
            )
        if not errors:
            try:
                errors.extend(graph.explain(statement))
            except Exception as exception:
                errors.append(
                    "EXPLAIN_ERROR: "
                    f"{type(exception).__name__}: {exception}"
                )
        if not errors and (error := deadline_error(state)):
            errors.append(error)

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
            "validated_statement_sha256": (
                _statement_hash(statement) if not errors else ""
            ),
            "trace": _event(
                "validate_cypher",
                attempt=attempts,
                passed=not errors,
                errors=errors,
                statement_sha256=(
                    _statement_hash(statement) if not errors else None
                ),
            ),
        }

    def correct_cypher(state: CypherState) -> dict[str, Any]:
        if error := deadline_error(state):
            return {
                "errors": [error],
                "status": "failed",
                "next_action": "end",
                "validated_statement_sha256": "",
                "trace": _event("correct_cypher", failed=True, error=error),
            }
        try:
            statement = normalize_model_cypher(
                model.correct(
                    state["question"],
                    schema_context,
                    state.get("statement", ""),
                    state.get("errors", []),
                )
            )
        except Exception as exception:
            error = f"MODEL_ERROR: {type(exception).__name__}: {exception}"
            return {
                "errors": [error],
                "status": "failed",
                "next_action": "end",
                "validated_statement_sha256": "",
                "trace": _event("correct_cypher", failed=True, error=error),
            }
        if error := deadline_error(state):
            return {
                "statement": statement,
                "errors": [error],
                "status": "failed",
                "next_action": "end",
                "validated_statement_sha256": "",
                "trace": _event("correct_cypher", failed=True, error=error),
            }
        return {
            "statement": statement,
            "statement_history": [
                {
                    "kind": "corrected",
                    "attempt": state.get("attempts", 0) + 1,
                    "statement": statement,
                }
            ],
            "errors": [],
            "status": "running",
            "next_action": "validate",
            "validated_statement_sha256": "",
            "trace": _event(
                "correct_cypher", after_attempt=state.get("attempts", 0)
            ),
        }

    def execute_cypher(state: CypherState) -> dict[str, Any]:
        statement = state.get("statement", "")
        verified_hash = state.get("validated_statement_sha256", "")
        if error := deadline_error(state):
            return {
                "records": [],
                "errors": [error],
                "status": "failed",
                "next_action": "end",
                "trace": _event("execute_cypher", executed=False, error=error),
            }
        if not verified_hash or verified_hash != _statement_hash(statement):
            error = (
                "VERIFICATION_REQUIRED: The exact Cypher statement did not "
                "pass the latest validation."
            )
            return {
                "records": [],
                "errors": [error],
                "status": "failed",
                "next_action": "end",
                "trace": _event("execute_cypher", executed=False, error=error),
            }
        try:
            # The graph adapter repeats the read-only check immediately before
            # execution, so no future edge can bypass security validation.
            records = graph.execute(statement)
        except Exception as exception:
            error = f"EXECUTION_ERROR: {type(exception).__name__}: {exception}"
            return {
                "records": [],
                "errors": [error],
                "status": "failed",
                "next_action": "end",
                "trace": _event("execute_cypher", executed=False, error=error),
            }
        return {
            "records": records,
            "status": "success" if records else "empty",
            "next_action": "end",
            "trace": _event(
                "execute_cypher",
                executed=True,
                verified_statement_sha256=verified_hash,
                row_count=len(records),
            ),
        }

    def route_after_generation(
        state: CypherState,
    ) -> Literal["validate_cypher", "__end__"]:
        return (
            "validate_cypher"
            if state.get("next_action") == "validate"
            else "__end__"
        )

    def route_after_correction(
        state: CypherState,
    ) -> Literal["validate_cypher", "__end__"]:
        return (
            "validate_cypher"
            if state.get("next_action") == "validate"
            else "__end__"
        )

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
    builder.add_conditional_edges("generate_cypher", route_after_generation)
    builder.add_conditional_edges(
        "validate_cypher", route_after_validation
    )
    builder.add_conditional_edges("correct_cypher", route_after_correction)
    builder.add_edge("execute_cypher", END)
    return builder.compile()


class TextToCypherAgent:
    def __init__(
        self,
        model: CypherModel,
        graph: ReadGraph,
        examples_path: Path,
        max_attempts: int = 3,
        schema_context: str = SCHEMA_CONTEXT,
        semantic_validator: Callable[[str, str], list[str]] = validate_domain_semantics,
        project_id: str = "cip-dmd",
        few_shot_count: int = 6,
        timeout_seconds: float = 30.0,
        metadata: dict[str, Any] | None = None,
    ):
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.max_attempts = max_attempts
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.metadata = {
            "project_id": project_id,
            **(metadata or {}),
        }
        self.workflow = create_text2cypher_agent(
            model=model,
            graph=graph,
            examples=GoldExampleStore(examples_path),
            max_attempts=max_attempts,
            schema_context=schema_context,
            semantic_validator=semantic_validator,
            project_id=project_id,
            few_shot_count=few_shot_count,
        )

    def invoke(self, question: str) -> CypherState:
        started = perf_counter()
        normalized_question = question.strip()
        base: CypherState = {
            "question": normalized_question,
            "statement": "",
            "errors": [],
            "attempts": 0,
            "max_attempts": self.max_attempts,
            "records": [],
            "status": "running",
            "next_action": "end",
            "trace": [],
            "statement_history": [],
            "deadline_monotonic": started + self.timeout_seconds,
            "validated_statement_sha256": "",
            "metadata": self.metadata,
        }
        if detect_ambiguous_request(normalized_question):
            return {
                **base,
                "errors": [
                    "AMBIGUOUS_REQUEST: Specify an entity ID, condition, "
                    "time range, or business metric."
                ],
                "status": "needs_clarification",
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
                **base,
                "errors": ["WRITE_REQUEST: Data modification requests are blocked."],
                "status": "blocked",
                "trace": [{"step": "guard_question", "blocked": True}],
                "elapsed_ms": int((perf_counter() - started) * 1000),
            }
        if isinstance(self.model, GoldCypherModel) and not self.model.supports(
            normalized_question
        ):
            return {
                **base,
                "errors": [
                    "GOLD_UNSUPPORTED: Gold demo only supports registered "
                    "example questions."
                ],
                "status": "unsupported",
                "trace": [
                    {
                        "step": "guard_question",
                        "unsupported": True,
                    }
                ],
                "elapsed_ms": int((perf_counter() - started) * 1000),
            }
        result: CypherState = self.workflow.invoke(
            base
        )
        result["elapsed_ms"] = int((perf_counter() - started) * 1000)
        return result
