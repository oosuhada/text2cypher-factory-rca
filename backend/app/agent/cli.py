"""Run the Text-to-Cypher workflow from the command line."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from neo4j import GraphDatabase

from backend.app.etl.cli import password_from_keychain

from .graph import Neo4jReadGraph
from .model import (
    GeminiCypherModel,
    GoldCypherModel,
    OpenAICypherModel,
    has_vertex_credentials,
)
from .examples import GoldExampleStore
from .workflow import TextToCypherAgent
from backend.app.services.query_service import QueryService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question")
    parser.add_argument(
        "--provider",
        choices=("auto", "gold", "openai", "gemini"),
        default="auto",
        help="auto prefers OpenAI, then Vertex Gemini, then Gold lookup",
    )
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument(
        "--raw",
        action="store_true",
        help="print raw LangGraph state instead of the UI-ready response",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[3]
    examples_path = project_root / "evaluation" / "gold_questions.yml"
    example_store = GoldExampleStore(examples_path)
    provider = args.provider
    if provider == "auto":
        provider = (
            "openai"
            if os.getenv("OPENAI_API_KEY")
            else "gemini"
            if has_vertex_credentials()
            else "gold"
        )
    if provider == "openai":
        model = OpenAICypherModel(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        )
    elif provider == "gemini":
        model = GeminiCypherModel(
            model=os.getenv(
                "GOOGLE_VERTEX_MODEL", "gemini-2.5-flash"
            ),
            location=os.getenv(
                "GOOGLE_VERTEX_LOCATION", "us-central1"
            ),
        )
    else:
        model = GoldCypherModel(example_store)

    username = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD") or password_from_keychain(username)
    if not password:
        raise RuntimeError("Neo4j password is not configured")

    with GraphDatabase.driver(
        os.getenv("NEO4J_URI", "neo4j://localhost:7687"),
        auth=(username, password),
    ) as driver:
        agent = TextToCypherAgent(
            model=model,
            graph=Neo4jReadGraph(
                driver,
                database=os.getenv("NEO4J_DATABASE", "neo4j"),
            ),
            examples_path=examples_path,
            max_attempts=args.max_attempts,
        )
        result = (
            agent.invoke(args.question)
            if args.raw
            else QueryService(
                agent,
                provider=provider,
                usage_reader=(
                    model.usage_summary
                    if hasattr(model, "usage_summary")
                    else None
                ),
            ).query(args.question)
        )
        print(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
