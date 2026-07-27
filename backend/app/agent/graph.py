"""Neo4j access restricted to validated read queries."""

from __future__ import annotations

from typing import Any, Protocol

from neo4j import Driver, Query, READ_ACCESS
from neo4j.exceptions import Neo4jError
from neo4j.graph import Node, Path, Relationship

from backend.app.security.read_only import ensure_read_only


class ReadGraph(Protocol):
    def explain(self, statement: str) -> list[str]: ...
    def execute(self, statement: str) -> list[dict[str, Any]]: ...


def _serializable(value: Any) -> Any:
    if isinstance(value, Node):
        return {
            "element_id": value.element_id,
            "labels": sorted(value.labels),
            "properties": dict(value),
        }
    if isinstance(value, Relationship):
        return {
            "element_id": value.element_id,
            "type": value.type,
            "start_node_id": value.start_node.element_id,
            "end_node_id": value.end_node.element_id,
            "properties": dict(value),
        }
    if isinstance(value, Path):
        return {
            "nodes": [_serializable(node) for node in value.nodes],
            "relationships": [
                _serializable(relationship)
                for relationship in value.relationships
            ],
        }
    if isinstance(value, dict):
        return {key: _serializable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serializable(item) for item in value]
    return value


class Neo4jReadGraph:
    def __init__(
        self,
        driver: Driver,
        database: str = "neo4j",
        timeout_seconds: float = 10.0,
        max_records: int = 500,
    ):
        self.driver = driver
        self.database = database
        self.timeout_seconds = timeout_seconds
        self.max_records = max_records

    def explain(self, statement: str) -> list[str]:
        ensure_read_only(statement)
        try:
            with self.driver.session(
                database=self.database,
                default_access_mode=READ_ACCESS,
            ) as session:
                session.run(
                    Query(
                        f"EXPLAIN {statement}",
                        timeout=self.timeout_seconds,
                    )
                ).consume()
        except Neo4jError as error:
            return [f"EXPLAIN_ERROR: {error.message or str(error)}"]
        return []

    def execute(self, statement: str) -> list[dict[str, Any]]:
        ensure_read_only(statement)
        with self.driver.session(
            database=self.database,
            default_access_mode=READ_ACCESS,
        ) as session:
            result = session.run(
                Query(statement, timeout=self.timeout_seconds)
            )
            return [
                {
                    key: _serializable(value)
                    for key, value in record.items()
                }
                for record in list(result)[: self.max_records]
            ]
