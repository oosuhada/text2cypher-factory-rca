#!/usr/bin/env python3
"""Build Blind answer keys or run the three-condition LLM evaluation."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

from neo4j import GraphDatabase

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.agent.examples import GoldExampleStore
from backend.app.agent.graph import Neo4jReadGraph
from backend.app.agent.model import (
    GeminiCypherModel,
    OpenAICypherModel,
    has_vertex_credentials,
)
from backend.app.etl.cli import password_from_keychain
from evaluation.evaluator import (
    VARIANTS,
    evaluate_question,
    load_blind_questions,
    summarize_results,
)
from evaluation.gold_validation import (
    build_snapshot,
    compare_snapshot,
    load_snapshot,
    write_snapshot,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--update-expected",
        action="store_true",
        help="Execute human-written Blind Gold Cypher and approve snapshots.",
    )
    parser.add_argument(
        "--verify-expected",
        action="store_true",
        help="Compare current Neo4j results with approved Blind snapshots.",
    )
    parser.add_argument(
        "--provider",
        choices=("auto", "openai", "gemini"),
        default="auto",
    )
    parser.add_argument(
        "--model",
        default=None,
    )
    return parser.parse_args()


def database_credentials() -> tuple[str, str]:
    username = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD") or password_from_keychain(username)
    if not password:
        raise RuntimeError("Neo4j password is not configured")
    return username, password


def update_expected(driver, database, questions, expected_root) -> None:
    updated = 0
    for question in questions:
        cypher = question.get("gold_cypher")
        if not cypher:
            continue
        records, _, _ = driver.execute_query(
            cypher,
            database_=database,
            routing_="r",
        )
        snapshot = build_snapshot(
            question, [record.data() for record in records]
        )
        write_snapshot(
            expected_root / f"{question['id']}.json",
            snapshot,
        )
        updated += 1
        print(f"{question['id']}: UPDATED ({snapshot['row_count']} rows)")
    print(f"Blind expected results: UPDATED ({updated} query scenarios)")


def verify_expected(driver, database, questions, expected_root) -> None:
    verified = 0
    failures = []
    for question in questions:
        cypher = question.get("gold_cypher")
        if not cypher:
            continue
        records, _, _ = driver.execute_query(
            cypher,
            database_=database,
            routing_="r",
        )
        actual = build_snapshot(
            question, [record.data() for record in records]
        )
        expected = load_snapshot(
            expected_root / f"{question['id']}.json"
        )
        comparison = compare_snapshot(expected, actual)
        status = "PASS" if comparison["strict_match"] else "FAIL"
        print(f"{question['id']}: {status} ({actual['row_count']} rows)")
        if not comparison["strict_match"]:
            failures.append(comparison)
        verified += 1
    if failures:
        print(json.dumps(failures, ensure_ascii=False, indent=2))
        raise SystemExit(1)
    print(f"Blind expected results: PASS ({verified}/{verified})")


def run_evaluation(
    driver,
    database,
    questions,
    expected_root,
    provider,
    model_name,
) -> dict:
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
        raise SystemExit(
            "No OpenAI or Vertex AI credentials are configured. "
            "Blind score was not calculated."
        )
    if resolved_provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is not configured.")
    if resolved_provider == "gemini" and not has_vertex_credentials():
        raise SystemExit("Vertex AI credentials are not configured.")
    resolved_model = model_name or (
        os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        if resolved_provider == "openai"
        else os.getenv("GOOGLE_VERTEX_MODEL", "gemini-2.5-flash")
    )
    examples = GoldExampleStore(
        PROJECT_ROOT / "evaluation" / "gold_questions.yml"
    )
    graph = Neo4jReadGraph(driver, database=database)
    variant_reports = {}
    for variant in VARIANTS:
        model = (
            OpenAICypherModel(model=resolved_model)
            if resolved_provider == "openai"
            else GeminiCypherModel(
                model=resolved_model,
                location=os.getenv(
                    "GOOGLE_VERTEX_LOCATION", "us-central1"
                ),
            )
        )
        results = []
        for question in questions:
            expected_path = expected_root / f"{question['id']}.json"
            expected = (
                load_snapshot(expected_path)
                if question.get("gold_cypher")
                else None
            )
            result = evaluate_question(
                question,
                expected,
                model,
                graph,
                examples,
                variant,
            )
            results.append(result)
            print(
                f"{variant.name}/{question['id']}: "
                f"{'PASS' if result['result_match'] else 'FAIL'}"
            )
        variant_reports[variant.name] = {
            "metrics": summarize_results(results),
            "usage": (
                model.usage_summary()
                if hasattr(model, "usage_summary")
                else None
            ),
            "questions": results,
        }
    comparison = [
        {
            "variant": variant.name,
            **variant_reports[variant.name]["metrics"],
            "model_call_count": (
                variant_reports[variant.name].get("usage") or {}
            ).get("call_count", 0),
            "input_tokens": (
                variant_reports[variant.name].get("usage") or {}
            ).get("input_tokens", 0),
            "output_tokens": (
                variant_reports[variant.name].get("usage") or {}
            ).get("output_tokens", 0),
            "estimated_cost_usd": (
                variant_reports[variant.name].get("usage") or {}
            ).get("estimated_cost_usd", 0),
        }
        for variant in VARIANTS
    ]
    return {
        "dataset": "CiP-DMD",
        "provider": resolved_provider,
        "model": resolved_model,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "question_count": len(questions),
        "pricing_basis": (
            {
                "currency": "USD",
                "input_usd_per_million_tokens": (
                    GeminiCypherModel.INPUT_USD_PER_MILLION
                ),
                "output_usd_per_million_tokens": (
                    GeminiCypherModel.OUTPUT_USD_PER_MILLION
                ),
                "thinking_budget": 0,
                "seed": 42,
                "source": (
                    "https://cloud.google.com/vertex-ai/"
                    "generative-ai/pricing"
                ),
                "checked_at": "2026-07-27",
            }
            if resolved_provider == "gemini"
            else None
        ),
        "comparison": comparison,
        "total_usage": {
            "call_count": sum(
                (report.get("usage") or {}).get("call_count", 0)
                for report in variant_reports.values()
            ),
            "input_tokens": sum(
                (report.get("usage") or {}).get("input_tokens", 0)
                for report in variant_reports.values()
            ),
            "output_tokens": sum(
                (report.get("usage") or {}).get("output_tokens", 0)
                for report in variant_reports.values()
            ),
            "estimated_cost_usd": round(
                sum(
                    (report.get("usage") or {}).get(
                        "estimated_cost_usd", 0
                    )
                    for report in variant_reports.values()
                ),
                8,
            ),
        },
        "variants": variant_reports,
    }


def write_report(report: dict) -> tuple[Path, Path]:
    results_root = PROJECT_ROOT / "evaluation" / "results"
    results_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_path = results_root / f"blind_evaluation_{timestamp}.json"
    latest_path = results_root / "latest.json"
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    run_path.write_text(serialized, encoding="utf-8")
    latest_path.write_text(serialized, encoding="utf-8")
    return run_path, latest_path


def update_dashboard_metrics(report: dict) -> Path:
    metrics_path = PROJECT_ROOT / "evaluation" / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    final_metrics = report["variants"]["self_correction"]["metrics"]
    metrics.update(
        {
            "blind_result_accuracy": final_metrics["result_accuracy"],
            "blind_strict_result_accuracy": final_metrics[
                "strict_result_accuracy"
            ],
            "blind_contract_variance_rate": final_metrics[
                "contract_variance_rate"
            ],
            "blind_execution_success_rate": final_metrics[
                "execution_success_rate"
            ],
            "blind_schema_compliance_rate": final_metrics[
                "schema_compliance_rate"
            ],
            "blind_empty_result_handling_rate": final_metrics[
                "empty_result_handling_rate"
            ],
            "blind_correction_success_rate": final_metrics[
                "correction_success_rate"
            ],
            "blind_evidence_display_rate": final_metrics[
                "evidence_display_rate"
            ],
            "blind_average_elapsed_ms": final_metrics[
                "average_elapsed_ms"
            ],
            "blind_evaluation_model": report["model"],
            "blind_evaluation_provider": report["provider"],
            "blind_evaluation_estimated_cost_usd": report[
                "total_usage"
            ]["estimated_cost_usd"],
            "blind_evaluation_input_tokens": report["total_usage"][
                "input_tokens"
            ],
            "blind_evaluation_output_tokens": report["total_usage"][
                "output_tokens"
            ],
            "blind_evaluation_status": "complete",
        }
    )
    metrics_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return metrics_path


def main() -> None:
    args = parse_args()
    if args.update_expected and args.verify_expected:
        raise SystemExit(
            "Choose only one of --update-expected and --verify-expected."
        )
    questions = load_blind_questions(
        PROJECT_ROOT / "evaluation" / "blind_questions.yml"
    )
    expected_root = PROJECT_ROOT / "evaluation" / "blind_results"
    username, password = database_credentials()
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    with GraphDatabase.driver(
        os.getenv("NEO4J_URI", "neo4j://localhost:7687"),
        auth=(username, password),
    ) as driver:
        driver.verify_connectivity()
        if args.update_expected:
            update_expected(driver, database, questions, expected_root)
            return
        if args.verify_expected:
            verify_expected(driver, database, questions, expected_root)
            return
        report = run_evaluation(
            driver,
            database,
            questions,
            expected_root,
            args.provider,
            args.model,
        )
    run_path, latest_path = write_report(report)
    metrics_path = update_dashboard_metrics(report)
    print(f"Run report: {run_path}")
    print(f"Latest report: {latest_path}")
    print(f"Dashboard metrics: {metrics_path}")


if __name__ == "__main__":
    main()
