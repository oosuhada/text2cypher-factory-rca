#!/usr/bin/env python3
"""Execute every Gold Cypher query against the local read-only graph."""

from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess

from neo4j import GraphDatabase


def password_from_keychain(username: str) -> str | None:
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


def extract_gold_queries(path: Path) -> list[tuple[str, str]]:
    text = path.read_text(encoding="utf-8")
    question_ids = re.findall(r"^  - id: (Q\d+)$", text, re.MULTILINE)
    blocks = re.findall(
        r"^    gold_cypher: \|\n((?:^      .*\n|^\n)+)",
        text,
        re.MULTILINE,
    )
    if len(question_ids) != len(blocks):
        raise ValueError(
            f"Question/query mismatch: {len(question_ids)} IDs, "
            f"{len(blocks)} Cypher blocks"
        )
    return [
        (
            question_id,
            "\n".join(line[6:] for line in block.splitlines()).strip(),
        )
        for question_id, block in zip(question_ids, blocks, strict=True)
    ]


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    queries = extract_gold_queries(
        project_root / "evaluation" / "gold_questions.yml"
    )
    username = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD") or password_from_keychain(username)
    if not password:
        raise RuntimeError("Neo4j password is not configured")

    with GraphDatabase.driver(
        os.getenv("NEO4J_URI", "neo4j://localhost:7687"),
        auth=(username, password),
    ) as driver:
        for question_id, cypher in queries:
            records, _, _ = driver.execute_query(
                cypher,
                database_=os.getenv("NEO4J_DATABASE", "neo4j"),
                routing_="r",
            )
            print(f"{question_id}: PASS ({len(records)} rows)")
    print(f"Gold queries: PASS ({len(queries)}/{len(queries)})")


if __name__ == "__main__":
    main()
