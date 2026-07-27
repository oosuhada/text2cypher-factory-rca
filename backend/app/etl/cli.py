"""Command-line entrypoint for the CiP-DMD Neo4j ETL."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
from typing import Any

from neo4j import GraphDatabase

from .extract import audit_quality_csvs, extract_records
from .load import graph_counts, load_payload
from .transform import transform_records
from .validate import validate_payload


def password_from_keychain(username: str) -> str | None:
    if os.name != "posix":
        return None
    try:
        result = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-s",
                "p3-cip-dmd-neo4j",
                "-a",
                username,
                "-w",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify-idempotency", action="store_true")
    parser.add_argument("--batch-size", type=int, default=500)
    return parser.parse_args()


def write_report(
    processed_root: Path, report: dict[str, Any]
) -> tuple[Path, Path]:
    runs_root = processed_root / "etl_runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_path = runs_root / f"etl_{timestamp}.json"
    latest_path = processed_root / "cip_dmd_etl_summary.json"
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    run_path.write_text(serialized, encoding="utf-8")
    latest_path.write_text(serialized, encoding="utf-8")
    return run_path, latest_path


def write_quarantine(
    processed_root: Path, quarantined: list[dict[str, Any]]
) -> Path:
    quarantine_root = processed_root / "quarantine"
    quarantine_root.mkdir(parents=True, exist_ok=True)
    quarantine_path = (
        quarantine_root / "missing_component_references.json"
    )
    quarantine_path.write_text(
        json.dumps(quarantined, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return quarantine_path


def main() -> None:
    args = parse_args()
    if args.batch_size < 1:
        raise ValueError("--batch-size must be positive")

    project_root = Path(__file__).resolve().parents[3]
    raw_root = project_root / "data" / "raw" / "cip_dmd"
    processed_root = project_root / "data" / "processed"
    schema_path = project_root / "infra" / "schema.cypher"

    extracted = extract_records(raw_root)
    quality_csv_audit = audit_quality_csvs(raw_root)
    payload = transform_records(extracted)
    validation = validate_payload(payload)
    quarantine_path = write_quarantine(
        processed_root, payload.quarantined
    )
    report: dict[str, Any] = {
        "dataset": "CiP-DMD",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "mode": "dry-run" if args.dry_run else "load",
        "validation": validation,
        "payload": payload.summary(),
        "quality_csv_audit": quality_csv_audit,
        "quarantine_file": str(quarantine_path),
    }

    if args.dry_run:
        report["status"] = "PASS"
        run_path, latest_path = write_report(processed_root, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"Run report: {run_path}")
        print(f"Latest report: {latest_path}")
        return

    uri = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    username = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD") or password_from_keychain(username)
    if not password:
        raise RuntimeError(
            "Set NEO4J_PASSWORD or register the local password in macOS Keychain"
        )

    with GraphDatabase.driver(uri, auth=(username, password)) as driver:
        driver.verify_connectivity()
        before = graph_counts(driver, database)
        first_counters = load_payload(
            driver,
            database,
            payload,
            schema_path,
            batch_size=args.batch_size,
        )
        after_first = graph_counts(driver, database)
        if after_first != validation["counts"]:
            raise RuntimeError(
                "Loaded graph counts do not match the validated payload: "
                f"{after_first}"
            )

        report["database"] = {
            "uri": uri,
            "database": database,
            "before": before,
            "after_first": after_first,
            "first_load_counters": first_counters,
        }

        if args.verify_idempotency:
            second_counters = load_payload(
                driver,
                database,
                payload,
                schema_path,
                batch_size=args.batch_size,
            )
            after_second = graph_counts(driver, database)
            idempotent = after_second == after_first
            report["database"]["after_second"] = after_second
            report["database"]["second_load_counters"] = second_counters
            report["idempotency"] = {
                "status": "PASS" if idempotent else "FAIL",
                "counts_unchanged": idempotent,
            }
            if not idempotent:
                raise RuntimeError("Graph counts changed on the second ETL run")

    report["status"] = "PASS"
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    run_path, latest_path = write_report(processed_root, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Run report: {run_path}")
    print(f"Latest report: {latest_path}")


if __name__ == "__main__":
    main()
