"""Reusable Blind Text-to-Cypher evaluation pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Mapping

import yaml

from backend.app.agent.examples import GoldExampleStore
from backend.app.agent.graph import ReadGraph
from backend.app.agent.model import CypherModel, normalize_model_cypher
from backend.app.agent.schema import SCHEMA_CONTEXT
from backend.app.agent.semantic_validation import validate_domain_semantics
from backend.app.security.read_only import (
    detect_ambiguous_request,
    detect_write_request,
    validate_read_only,
)
from backend.app.services.result_formatter import format_agent_result
from evaluation.gold_validation import (
    compare_snapshot,
    normalize_records,
    rows_fingerprint,
)


@dataclass(frozen=True)
class EvaluationVariant:
    name: str
    use_few_shot: bool
    enable_correction: bool


VARIANTS = (
    EvaluationVariant("baseline", False, False),
    EvaluationVariant("few_shot", True, False),
    EvaluationVariant("self_correction", True, True),
)


def load_blind_questions(path) -> list[dict[str, Any]]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    questions = document.get("questions", [])
    ids = [str(question.get("id")) for question in questions]
    if not 20 <= len(questions) <= 30:
        raise ValueError(
            f"Blind evaluation requires 20-30 questions, found {len(questions)}"
        )
    if len(ids) != len(set(ids)):
        raise ValueError("Blind question IDs must be unique")
    return questions


def _state_for_guard(question: str) -> dict[str, Any] | None:
    if detect_ambiguous_request(question):
        return {
            "question": question,
            "statement": "",
            "records": [],
            "status": "needs_clarification",
            "attempts": 0,
            "errors": ["AMBIGUOUS_REQUEST"],
            "trace": [{"step": "guard_question"}],
            "elapsed_ms": 0,
        }
    if detect_write_request(question):
        return {
            "question": question,
            "statement": "",
            "records": [],
            "status": "blocked",
            "attempts": 0,
            "errors": ["WRITE_REQUEST"],
            "trace": [{"step": "guard_question"}],
            "elapsed_ms": 0,
        }
    return None


def _candidate_snapshot(
    question: Mapping[str, Any],
    status: str,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    rows = normalize_records(records)
    return {
        "question_id": question["id"],
        "expected_status": status,
        "row_count": len(rows),
        "rows_sha256": rows_fingerprint(rows),
        "normalized_rows": rows,
    }


def classify_failure(
    expected_status: str,
    actual_status: str,
    result_match: bool,
    errors: list[str],
    has_evidence: bool,
) -> str | None:
    if result_match:
        return None
    if any(error.startswith("MODEL_ERROR") for error in errors):
        return "generation_error"
    if any(error.startswith("EMPTY_QUERY") for error in errors):
        return "empty_query"
    if actual_status == "blocked" and expected_status != "blocked":
        return "unsafe_query"
    if any(error.startswith("EXPLAIN_ERROR") for error in errors):
        return "syntax_or_schema_error"
    if any(
        error.startswith(
            ("DOMAIN_VALUE", "QUESTION_ALIGNMENT", "SCHEMA_TOPOLOGY")
        )
        for error in errors
    ):
        return "semantic_validation_error"
    if any(error.startswith("EXECUTION_ERROR") for error in errors):
        return "execution_error"
    if actual_status != expected_status:
        return "wrong_status"
    if not has_evidence and actual_status == "success":
        return "missing_evidence"
    return "wrong_value_or_rowset"


def evaluate_question(
    question: Mapping[str, Any],
    expected_snapshot: Mapping[str, Any] | None,
    model: CypherModel,
    graph: ReadGraph,
    examples: GoldExampleStore,
    variant: EvaluationVariant,
    max_attempts: int = 3,
) -> dict[str, Any]:
    started = perf_counter()
    question_text = str(question["question"]).strip()
    expected_status = str(question["expected_status"])
    guard_state = _state_for_guard(question_text)
    correction_attempted = False
    generated = guard_state is None
    final_validation_passed = guard_state is not None
    write_executed = False

    if guard_state is not None:
        state = guard_state
    else:
        few_shot = (
            examples.format_for_prompt(question_text)
            if variant.use_few_shot
            else ""
        )
        trace = []
        errors: list[str] = []
        statement = ""
        attempts = 0
        records: list[dict[str, Any]] = []
        status = "failed"
        try:
            statement = normalize_model_cypher(
                model.generate(question_text, SCHEMA_CONTEXT, few_shot)
            )
            trace.append({"step": "generate_cypher"})
        except Exception as error:
            errors = [f"MODEL_ERROR: {error}"]
            trace.append({"step": "generate_cypher", "failed": True})

        while not errors or not errors[0].startswith("MODEL_ERROR"):
            attempts += 1
            errors = validate_read_only(statement)
            unsafe = any(
                error.startswith(
                    ("WRITE_CLAUSE", "DISALLOWED_COMMAND", "MULTIPLE")
                )
                for error in errors
            )
            if not errors:
                errors = validate_domain_semantics(question_text, statement)
            if not errors:
                errors = graph.explain(statement)
            trace.append(
                {
                    "step": "validate_cypher",
                    "attempt": attempts,
                    "passed": not errors,
                    "errors": errors,
                }
            )
            if unsafe:
                status = "blocked"
                break
            if not errors:
                final_validation_passed = True
                try:
                    records = graph.execute(statement)
                    status = "success" if records else "empty"
                    trace.append(
                        {
                            "step": "execute_cypher",
                            "row_count": len(records),
                        }
                    )
                except Exception as error:
                    errors = [f"EXECUTION_ERROR: {error}"]
                    status = "failed"
                break
            if not variant.enable_correction or attempts >= max_attempts:
                status = "failed"
                break
            correction_attempted = True
            try:
                statement = normalize_model_cypher(
                    model.correct(
                        question_text,
                        SCHEMA_CONTEXT,
                        statement,
                        errors,
                    )
                )
                trace.append(
                    {"step": "correct_cypher", "after_attempt": attempts}
                )
            except Exception as error:
                errors = [f"MODEL_ERROR: {error}"]
                status = "failed"
                break

        state = {
            "question": question_text,
            "statement": statement,
            "records": records,
            "status": status,
            "attempts": attempts,
            "errors": errors,
            "trace": trace,
            "elapsed_ms": int((perf_counter() - started) * 1000),
        }

    state["elapsed_ms"] = int((perf_counter() - started) * 1000)
    formatted = format_agent_result(state)
    if expected_snapshot is None:
        status_match = formatted["status"] == expected_status
        comparison = {
            "match": status_match,
            "semantic_match": status_match,
            "strict_match": status_match,
            "contract_only_mismatch": False,
            "expected_row_count": 0,
            "actual_row_count": formatted["row_count"],
            "missing_rows": [],
            "unexpected_rows": [],
        }
    else:
        comparison = compare_snapshot(
            expected_snapshot,
            _candidate_snapshot(
                question,
                formatted["status"],
                formatted["rows"],
            ),
        )
    has_evidence = bool(
        formatted.get("cypher")
        and (
            formatted.get("rows")
            or formatted["status"] == "empty"
        )
    )
    failure_type = classify_failure(
        expected_status,
        formatted["status"],
        comparison["match"],
        formatted["validation"]["errors"],
        has_evidence,
    )
    return {
        "question_id": question["id"],
        "category": question["category"],
        "difficulty": question["difficulty"],
        "question": question_text,
        "expected_status": expected_status,
        "actual_status": formatted["status"],
        "result_match": comparison["match"],
        "strict_result_match": comparison["strict_match"],
        "contract_variance": comparison["contract_only_mismatch"],
        "difference_type": (
            "exact"
            if comparison["strict_match"]
            else "column_alias_or_extra_field"
            if comparison["contract_only_mismatch"]
            else "wrong_value_or_rowset"
        ),
        "expected_row_count": comparison["expected_row_count"],
        "actual_row_count": comparison["actual_row_count"],
        "execution_success": (
            formatted["status"] in {"success", "empty"}
            if expected_status in {"success", "empty"}
            else None
        ),
        "schema_compliant": final_validation_passed if generated else None,
        "read_only_compliant": not write_executed,
        "empty_handled": (
            formatted["status"] == "empty"
            if expected_status == "empty"
            else None
        ),
        "correction_attempted": correction_attempted,
        "correction_succeeded": (
            comparison["match"] if correction_attempted else None
        ),
        "evidence_displayed": (
            has_evidence if expected_status in {"success", "empty"} else None
        ),
        "attempts": formatted["validation"]["attempts"],
        "elapsed_ms": formatted["validation"]["elapsed_ms"],
        "cypher": formatted["cypher"],
        "errors": formatted["validation"]["errors"],
        "failure_type": failure_type,
        "missing_rows": comparison.get("missing_rows", []),
        "unexpected_rows": comparison.get("unexpected_rows", []),
    }


def _rate(values: list[bool | None]) -> float | None:
    applicable = [value for value in values if value is not None]
    return (
        sum(bool(value) for value in applicable) / len(applicable)
        if applicable
        else None
    )


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    failure_counts: dict[str, int] = {}
    for result in results:
        failure_type = result.get("failure_type")
        if failure_type:
            failure_counts[failure_type] = (
                failure_counts.get(failure_type, 0) + 1
            )
    return {
        "question_count": len(results),
        "execution_success_rate": _rate(
            [result["execution_success"] for result in results]
        ),
        "result_accuracy": _rate(
            [result["result_match"] for result in results]
        ),
        "strict_result_accuracy": _rate(
            [result["strict_result_match"] for result in results]
        ),
        "contract_variance_rate": _rate(
            [result["contract_variance"] for result in results]
        ),
        "schema_compliance_rate": _rate(
            [result["schema_compliant"] for result in results]
        ),
        "read_only_compliance_rate": _rate(
            [result["read_only_compliant"] for result in results]
        ),
        "empty_result_handling_rate": _rate(
            [result["empty_handled"] for result in results]
        ),
        "correction_success_rate": _rate(
            [result["correction_succeeded"] for result in results]
        ),
        "evidence_display_rate": _rate(
            [result["evidence_displayed"] for result in results]
        ),
        "average_elapsed_ms": round(
            sum(result["elapsed_ms"] for result in results) / len(results),
            1,
        )
        if results
        else 0.0,
        "failure_counts": dict(sorted(failure_counts.items())),
        "difference_counts": {
            difference_type: sum(
                result.get("difference_type") == difference_type
                for result in results
            )
            for difference_type in (
                "exact",
                "column_alias_or_extra_field",
                "wrong_value_or_rowset",
            )
        },
    }
