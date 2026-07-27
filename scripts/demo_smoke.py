#!/usr/bin/env python3
"""Execute and cache the four fixed stage-17 Gold demo scenarios."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.agent.examples import GoldExampleStore
from frontend.app_services import build_service_bundle


DEMO_IDS = ("Q3", "Q2", "Q4", "Q5")


def main() -> None:
    examples = {
        example.question_id: example
        for example in GoldExampleStore(
            PROJECT_ROOT / "evaluation" / "gold_questions.yml"
        ).load()
    }
    bundle = build_service_bundle(
        PROJECT_ROOT, provider="gold", model_name=None
    )
    results = []
    try:
        for question_id in DEMO_IDS:
            example = examples[question_id]
            response = bundle.query.query(example.question)
            expected_status = "empty" if question_id == "Q5" else "success"
            passed = response["status"] == expected_status
            results.append(
                {
                    "question_id": question_id,
                    "question": example.question,
                    "expected_status": expected_status,
                    "actual_status": response["status"],
                    "row_count": response["row_count"],
                    "cypher": response["cypher"],
                    "passed": passed,
                }
            )
            print(
                f"{question_id}: {'PASS' if passed else 'FAIL'} "
                f"({response['status']}, {response['row_count']} rows)"
            )
    finally:
        bundle.close()
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if all(row["passed"] for row in results) else "FAIL",
        "scenario_count": len(results),
        "results": results,
    }
    output_path = (
        PROJECT_ROOT / "data" / "processed" / "demo_smoke_latest.json"
    )
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Demo cache: {output_path}")
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
