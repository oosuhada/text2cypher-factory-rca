#!/usr/bin/env python3
"""Create or verify deterministic result snapshots for all Gold queries."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from neo4j import GraphDatabase

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.etl.cli import password_from_keychain
from evaluation.gold_validation import (
    build_snapshot,
    compare_snapshot,
    load_gold_questions,
    load_snapshot,
    write_snapshot,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--update",
        action="store_true",
        help="Replace approved Gold snapshots with current database results.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = PROJECT_ROOT
    questions_path = project_root / "evaluation" / "gold_questions.yml"
    results_root = project_root / "evaluation" / "gold_results"
    questions = load_gold_questions(questions_path)

    username = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD") or password_from_keychain(username)
    if not password:
        raise RuntimeError("Neo4j password is not configured")

    outcomes = []
    with GraphDatabase.driver(
        os.getenv("NEO4J_URI", "neo4j://localhost:7687"),
        auth=(username, password),
    ) as driver:
        driver.verify_connectivity()
        for question in questions:
            records, _, _ = driver.execute_query(
                question["gold_cypher"],
                database_=os.getenv("NEO4J_DATABASE", "neo4j"),
                routing_="r",
            )
            snapshot = build_snapshot(
                question, [record.data() for record in records]
            )
            snapshot_path = results_root / f"{question['id']}.json"
            if args.update:
                write_snapshot(snapshot_path, snapshot)
                outcome = {
                    "question_id": question["id"],
                    "status": "UPDATED",
                    "row_count": snapshot["row_count"],
                    "rows_sha256": snapshot["rows_sha256"],
                }
            else:
                if not snapshot_path.exists():
                    raise FileNotFoundError(
                        f"Missing {snapshot_path}; run once with --update"
                    )
                comparison = compare_snapshot(
                    load_snapshot(snapshot_path), snapshot
                )
                outcome = {
                    **comparison,
                    "status": "PASS" if comparison["match"] else "FAIL",
                }
            outcomes.append(outcome)
            print(
                f"{question['id']}: {outcome['status']} "
                f"({snapshot['row_count']} rows)"
            )

    failed = [
        outcome for outcome in outcomes if outcome["status"] == "FAIL"
    ]
    summary = {
        "mode": "update" if args.update else "verify",
        "question_count": len(outcomes),
        "passed": len(outcomes) - len(failed),
        "failed": len(failed),
        "status": "PASS" if not failed else "FAIL",
        "results": outcomes,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
