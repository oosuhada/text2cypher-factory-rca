"""Reusable Blind Text-to-Cypher evaluation pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable, Mapping

import yaml

from backend.app.agent.examples import GoldExampleStore
from backend.app.agent.graph import ReadGraph
from backend.app.agent.model import CypherModel
from backend.app.agent.schema import SCHEMA_CONTEXT
from backend.app.agent.semantic_validation import validate_domain_semantics
from backend.app.agent.workflow import TextToCypherAgent
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
            (
                "DOMAIN_VALUE",
                "QUESTION_ALIGNMENT",
                "SCHEMA_TOPOLOGY",
                "PROJECT_SCOPE",
            )
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
    schema_context: str = SCHEMA_CONTEXT,
    semantic_validator: Callable[
        [str, str], list[str]
    ] = validate_domain_semantics,
    project_id: str = "cip-dmd",
    few_shot_count: int = 6,
    timeout_seconds: float = 30.0,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    started = perf_counter()
    question_text = str(question["question"]).strip()
    expected_status = str(question["expected_status"])
    generated = _state_for_guard(question_text) is None
    state = TextToCypherAgent(
        model=model,
        graph=graph,
        examples_path=examples.path,
        max_attempts=max_attempts if variant.enable_correction else 1,
        schema_context=schema_context,
        semantic_validator=semantic_validator,
        project_id=project_id,
        few_shot_count=few_shot_count if variant.use_few_shot else 0,
        timeout_seconds=timeout_seconds,
        metadata=metadata,
    ).invoke(question_text)
    formatted = format_agent_result(state)
    trace = formatted["validation"]["trace"]
    correction_attempted = any(
        event.get("step") == "correct_cypher" for event in trace
    )
    final_validation_passed = any(
        event.get("step") == "validate_cypher"
        and event.get("passed") is True
        for event in trace
    )
    write_executed = any(
        event.get("step") == "execute_cypher"
        and event.get("executed") is True
        and formatted["status"] == "blocked"
        for event in trace
    )
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
        "execution_verified": (
            formatted["validation"].get("execution_verified", False)
            if formatted["status"] in {"success", "empty"}
            else None
        ),
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


def classification_metrics(
    results: list[dict[str, Any]],
    *,
    labels: tuple[str, ...] = (
        "success",
        "empty",
        "blocked",
        "needs_clarification",
        "failed",
    ),
) -> dict[str, Any]:
    observed = {
        str(result[field])
        for result in results
        for field in ("expected_status", "actual_status")
    }
    ordered_labels = list(labels) + sorted(observed - set(labels))
    matrix = {
        expected: {actual: 0 for actual in ordered_labels}
        for expected in ordered_labels
    }
    for result in results:
        matrix[str(result["expected_status"])][
            str(result["actual_status"])
        ] += 1
    per_class = {}
    for label in ordered_labels:
        true_positive = matrix[label][label]
        false_positive = sum(
            matrix[expected][label]
            for expected in ordered_labels
            if expected != label
        )
        false_negative = sum(
            matrix[label][actual]
            for actual in ordered_labels
            if actual != label
        )
        support = sum(matrix[label].values())
        precision = (
            true_positive / (true_positive + false_positive)
            if true_positive + false_positive
            else 0.0
        )
        recall = (
            true_positive / (true_positive + false_negative)
            if true_positive + false_negative
            else 0.0
        )
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )
        per_class[label] = {
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "f1": round(f1, 6),
            "support": support,
        }
    supported = [
        metrics for metrics in per_class.values() if metrics["support"]
    ]
    total = len(results)
    return {
        "labels": ordered_labels,
        "confusion_matrix": matrix,
        "accuracy": round(
            sum(
                matrix[label][label] for label in ordered_labels
            )
            / total,
            6,
        )
        if total
        else 0.0,
        "macro_precision": round(
            sum(row["precision"] for row in supported) / len(supported), 6
        )
        if supported
        else 0.0,
        "macro_recall": round(
            sum(row["recall"] for row in supported) / len(supported), 6
        )
        if supported
        else 0.0,
        "macro_f1": round(
            sum(row["f1"] for row in supported) / len(supported), 6
        )
        if supported
        else 0.0,
        "per_class": per_class,
    }


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
        "unverified_execution_count": sum(
            result.get("execution_verified") is False
            for result in results
            if result.get("execution_verified") is not None
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
        "status_classification": classification_metrics(results),
    }
