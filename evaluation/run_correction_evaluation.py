#!/usr/bin/env python3
"""Evaluate real LLM correction on deliberately rejected Cypher queries."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

from neo4j import GraphDatabase
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.agent.graph import Neo4jReadGraph
from backend.app.agent.model import (
    GeminiCypherModel,
    OpenAICypherModel,
    has_vertex_credentials,
    normalize_model_cypher,
)
from backend.app.agent.schema import SCHEMA_CONTEXT
from backend.app.agent.semantic_validation import validate_domain_semantics
from backend.app.etl.cli import password_from_keychain
from backend.app.security.read_only import validate_read_only
from evaluation.evaluator import load_blind_questions
from evaluation.gold_validation import (
    compare_snapshot,
    load_snapshot,
    normalize_records,
    rows_fingerprint,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--provider",
        choices=("auto", "gemini", "openai"),
        default="auto",
    )
    parser.add_argument("--model", default=None)
    parser.add_argument("--max-corrections", type=int, default=2)
    return parser.parse_args()


def validate(question: str, statement: str, graph) -> list[str]:
    errors = validate_read_only(statement)
    if not errors:
        errors = validate_domain_semantics(question, statement)
    if not errors:
        errors = graph.explain(statement)
    return errors


def candidate_snapshot(
    question_id: str, status: str, records: list[dict]
) -> dict:
    rows = normalize_records(records)
    return {
        "question_id": question_id,
        "expected_status": status,
        "row_count": len(rows),
        "rows_sha256": rows_fingerprint(rows),
        "normalized_rows": rows,
    }


def resolved_model(provider: str, model_name: str | None):
    resolved_provider = provider
    if provider == "auto":
        resolved_provider = (
            "openai"
            if os.getenv("OPENAI_API_KEY")
            else "gemini"
            if has_vertex_credentials()
            else "unavailable"
        )
    if resolved_provider == "unavailable":
        raise SystemExit("No OpenAI or Vertex credentials are configured.")
    if resolved_provider == "openai":
        if not os.getenv("OPENAI_API_KEY"):
            raise SystemExit("OPENAI_API_KEY is not configured.")
        resolved_name = model_name or os.getenv(
            "OPENAI_MODEL", "gpt-4.1-mini"
        )
        return (
            resolved_provider,
            resolved_name,
            OpenAICypherModel(model=resolved_name),
        )
    if not has_vertex_credentials():
        raise SystemExit("Vertex AI credentials are not configured.")
    resolved_name = model_name or os.getenv(
        "GOOGLE_VERTEX_MODEL", "gemini-2.5-flash"
    )
    return (
        "gemini",
        resolved_name,
        GeminiCypherModel(
            model=resolved_name,
            location=os.getenv("GOOGLE_VERTEX_LOCATION", "us-central1"),
        ),
    )


def main() -> None:
    args = parse_args()
    provider, model_name, model = resolved_model(
        args.provider, args.model
    )
    case_document = yaml.safe_load(
        (PROJECT_ROOT / "evaluation" / "correction_cases.yml").read_text(
            encoding="utf-8"
        )
    )
    cases = case_document["cases"]
    questions = {
        question["id"]: question
        for question in load_blind_questions(
            PROJECT_ROOT / "evaluation" / "blind_questions.yml"
        )
    }
    username = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD") or password_from_keychain(
        username
    )
    if not password:
        raise SystemExit("Neo4j password is not configured.")

    results = []
    with GraphDatabase.driver(
        os.getenv("NEO4J_URI", "neo4j://localhost:7687"),
        auth=(username, password),
    ) as driver:
        driver.verify_connectivity()
        graph = Neo4jReadGraph(
            driver, database=os.getenv("NEO4J_DATABASE", "neo4j")
        )
        for case in cases:
            question = questions[case["source_question_id"]]
            expected = load_snapshot(
                PROJECT_ROOT
                / "evaluation"
                / "blind_results"
                / f"{question['id']}.json"
            )
            statement = str(case["rejected_cypher"]).strip()
            initial_errors = validate(
                question["question"], statement, graph
            )
            if not initial_errors:
                raise RuntimeError(
                    f"{case['id']} seed query is not rejected"
                )
            attempts = 0
            corrected_errors = initial_errors
            records: list[dict] = []
            while corrected_errors and attempts < args.max_corrections:
                attempts += 1
                statement = normalize_model_cypher(
                    model.correct(
                        question["question"],
                        SCHEMA_CONTEXT,
                        statement,
                        corrected_errors,
                    )
                )
                corrected_errors = validate(
                    question["question"], statement, graph
                )
            if not corrected_errors:
                records = graph.execute(statement)
            status = (
                "failed"
                if corrected_errors
                else "success"
                if records
                else "empty"
            )
            comparison = compare_snapshot(
                expected,
                candidate_snapshot(question["id"], status, records),
            )
            result = {
                "case_id": case["id"],
                "source_question_id": question["id"],
                "error_type": case["error_type"],
                "initial_errors": initial_errors,
                "correction_attempts": attempts,
                "corrected_cypher": statement,
                "remaining_errors": corrected_errors,
                "validation_success": not corrected_errors,
                "result_match": comparison["match"],
                "strict_result_match": comparison["strict_match"],
                "contract_only_mismatch": comparison[
                    "contract_only_mismatch"
                ],
                "actual_status": status,
            }
            results.append(result)
            print(
                f"{case['id']}: "
                f"{'PASS' if result['result_match'] else 'FAIL'}"
            )

    usage = (
        model.usage_summary() if hasattr(model, "usage_summary") else None
    )
    report = {
        "provider": provider,
        "model": model_name,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "case_count": len(results),
        "validation_success_rate": sum(
            result["validation_success"] for result in results
        )
        / len(results),
        "result_accuracy": sum(
            result["result_match"] for result in results
        )
        / len(results),
        "strict_result_accuracy": sum(
            result["strict_result_match"] for result in results
        )
        / len(results),
        "usage": usage,
        "results": results,
    }
    results_root = PROJECT_ROOT / "evaluation" / "results"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_path = results_root / f"correction_evaluation_{timestamp}.json"
    latest_path = results_root / "correction_latest.json"
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    run_path.write_text(serialized, encoding="utf-8")
    latest_path.write_text(serialized, encoding="utf-8")

    metrics_path = PROJECT_ROOT / "evaluation" / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics.update(
        {
            "correction_case_count": report["case_count"],
            "correction_validation_success_rate": report[
                "validation_success_rate"
            ],
            "correction_result_accuracy": report["result_accuracy"],
            "correction_strict_result_accuracy": report[
                "strict_result_accuracy"
            ],
        }
    )
    metrics_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Run report: {run_path}")
    print(f"Latest report: {latest_path}")


if __name__ == "__main__":
    main()
