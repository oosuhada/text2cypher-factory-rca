#!/usr/bin/env python3
"""Run a small live OpenAI-to-Neo4j smoke test when a key is configured."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from frontend.app_services import build_service_bundle


DEFAULT_QUESTIONS = [
    "장비별 공정 실행 횟수를 많은 순서대로 알려줘.",
    "품질 불합격이 가장 많은 검사 항목 세 개를 보여줘.",
    "완제품 399999가 존재하는지 확인해줘.",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--question",
        action="append",
        dest="questions",
        help="Question to test; repeat for multiple questions.",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit(
            "OPENAI_API_KEY is not configured; live smoke test was not run."
        )

    services = build_service_bundle(
        PROJECT_ROOT,
        provider="openai",
        model_name=args.model,
    )
    outcomes = []
    try:
        for question in args.questions or DEFAULT_QUESTIONS:
            result = services.query.query(question)
            outcome = {
                "question": question,
                "status": result["status"],
                "row_count": result["row_count"],
                "attempts": result["validation"]["attempts"],
                "elapsed_ms": result["validation"]["elapsed_ms"],
                "has_cypher": bool(result["cypher"]),
                "error_count": len(result["validation"]["errors"]),
            }
            outcomes.append(outcome)
            print(json.dumps(outcome, ensure_ascii=False))
    finally:
        services.close()

    passed = sum(
        outcome["status"] in {"success", "empty"}
        and outcome["has_cypher"]
        for outcome in outcomes
    )
    summary = {
        "model": args.model,
        "question_count": len(outcomes),
        "passed": passed,
        "failed": len(outcomes) - passed,
        "status": "PASS" if passed == len(outcomes) else "FAIL",
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary["status"] == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
