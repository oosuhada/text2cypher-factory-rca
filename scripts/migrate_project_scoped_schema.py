#!/usr/bin/env python3
"""Migrate the legacy CiP-DMD graph to project-scoped identities.

The command is deliberately explicit: it never changes the database unless
``--apply`` is supplied and the database is already in loader/read-write mode.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.etl.cli import password_from_keychain


LEGACY_CONSTRAINTS = (
    "part_id_unique",
    "process_name_unique",
    "process_run_id_unique",
    "measurement_id_unique",
    "equipment_id_unique",
    "anomaly_class_code_unique",
)
NODE_LABELS = (
    "Part",
    "Process",
    "ProcessRun",
    "QualityMeasurement",
    "Equipment",
    "AnomalyClass",
)
RELATIONSHIP_TYPES = (
    "ASSEMBLED_FROM",
    "UNDERWENT",
    "INSTANCE_OF",
    "RUN_ON",
    "CLASSIFIED_AS",
    "HAS_MEASUREMENT",
    "FOR_PROCESS",
)


def _credentials() -> tuple[str, str]:
    username = os.getenv("NEO4J_LOADER_USERNAME") or os.getenv(
        "NEO4J_USERNAME", "neo4j"
    )
    password = (
        os.getenv("NEO4J_LOADER_PASSWORD")
        or os.getenv("NEO4J_PASSWORD")
        or password_from_keychain(username)
    )
    if not password:
        raise RuntimeError("Neo4j loader 인증정보를 찾을 수 없습니다.")
    return username, password


def _counts(driver, database: str) -> dict[str, int]:
    nodes = driver.execute_query(
        """
        MATCH (node)
        WHERE any(label IN labels(node) WHERE label IN $labels)
          AND node.project_id IS NULL
        RETURN count(node) AS count
        """,
        labels=list(NODE_LABELS),
        database_=database,
        routing_="r",
    ).records[0]["count"]
    relationships = driver.execute_query(
        """
        MATCH ()-[rel]->()
        WHERE type(rel) IN $types AND rel.project_id IS NULL
        RETURN count(rel) AS count
        """,
        types=list(RELATIONSHIP_TYPES),
        database_=database,
        routing_="r",
    ).records[0]["count"]
    return {
        "unscoped_nodes": int(nodes),
        "unscoped_relationships": int(relationships),
    }


def migrate(driver, database: str, project_id: str) -> dict:
    before = _counts(driver, database)
    driver.execute_query(
        """
        MATCH (node)
        WHERE any(label IN labels(node) WHERE label IN $labels)
          AND node.project_id IS NULL
        SET node.project_id = $project_id
        """,
        labels=list(NODE_LABELS),
        project_id=project_id,
        database_=database,
        routing_="w",
    )
    driver.execute_query(
        """
        MATCH ()-[rel]->()
        WHERE type(rel) IN $types AND rel.project_id IS NULL
        SET rel.project_id = $project_id
        """,
        types=list(RELATIONSHIP_TYPES),
        project_id=project_id,
        database_=database,
        routing_="w",
    )
    schema = ROOT / "infra" / "schema.cypher"
    statements = [
        statement.strip()
        for statement in schema.read_text(encoding="utf-8").split(";")
        if statement.strip()
    ]
    for statement in statements:
        driver.execute_query(
            statement, database_=database, routing_="w"
        )
    for name in LEGACY_CONSTRAINTS:
        driver.execute_query(
            f"DROP CONSTRAINT `{name}` IF EXISTS",
            database_=database,
            routing_="w",
        )
    after = _counts(driver, database)
    if after != {"unscoped_nodes": 0, "unscoped_relationships": 0}:
        raise RuntimeError(f"프로젝트 scope migration 실패: {after}")
    return {
        "status": "PASS",
        "project_id": project_id,
        "before": before,
        "after": after,
        "dropped_legacy_constraints": list(LEGACY_CONSTRAINTS),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--project-id", default="cip-dmd")
    args = parser.parse_args()
    username, password = _credentials()
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    uri = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
    if uri.startswith("neo4j://localhost"):
        uri = f"bolt://{uri.removeprefix('neo4j://')}"
    driver = None
    last_error = None
    for _ in range(120):
        candidate = GraphDatabase.driver(uri, auth=(username, password))
        try:
            candidate.verify_connectivity()
            driver = candidate
            break
        except Exception as error:
            last_error = error
            candidate.close()
            time.sleep(0.5)
    if driver is None:
        raise RuntimeError(
            f"Neo4j가 60초 안에 준비되지 않았습니다: {last_error}"
        )
    with driver:
        if not args.apply:
            print(
                json.dumps(
                    {
                        "status": "DRY_RUN",
                        "project_id": args.project_id,
                        **_counts(driver, database),
                        "next": (
                            "Switch Neo4j to loader mode, then rerun with "
                            "--apply."
                        ),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return
        print(
            json.dumps(
                migrate(driver, database, args.project_id),
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
