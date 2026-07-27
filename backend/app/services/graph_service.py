"""Read-only schema and bounded neighborhood queries for API clients."""

from __future__ import annotations

from typing import Any

from neo4j import Driver, Query, READ_ACCESS
from neo4j.graph import Node, Path, Relationship

from backend.app.agent.schema import SCHEMA_CONTEXT


NODE_IDENTITIES = {
    "Part": "part_id",
    "Cylinder": "part_id",
    "CylinderBottom": "part_id",
    "PistonRod": "part_id",
    "Process": "name",
    "ProcessRun": "run_id",
    "Equipment": "equipment_id",
    "AnomalyClass": "code",
    "QualityMeasurement": "measurement_id",
    "QualityFailure": "measurement_id",
}

RELATIONSHIP_TYPES = (
    "ASSEMBLED_FROM",
    "UNDERWENT",
    "INSTANCE_OF",
    "RUN_ON",
    "CLASSIFIED_AS",
    "HAS_MEASUREMENT",
    "FOR_PROCESS",
)


def schema_contract() -> dict[str, Any]:
    return {
        "schema_context": SCHEMA_CONTEXT,
        "node_identities": [
            {"label": label, "identity_property": identity}
            for label, identity in NODE_IDENTITIES.items()
        ],
        "relationship_types": list(RELATIONSHIP_TYPES),
    }


def _node_payload(node: Node) -> dict[str, Any]:
    return {
        "id": node.element_id,
        "labels": sorted(node.labels),
        "properties": dict(node),
    }


def _relationship_payload(
    relationship: Relationship,
) -> dict[str, Any]:
    return {
        "id": relationship.element_id,
        "type": relationship.type,
        "source": relationship.start_node.element_id,
        "target": relationship.end_node.element_id,
        "properties": dict(relationship),
    }


class GraphCatalogService:
    """Expose the canonical schema and safe, bounded graph evidence."""

    def __init__(
        self,
        driver: Driver,
        database: str = "neo4j",
        timeout_seconds: float = 10.0,
    ):
        self.driver = driver
        self.database = database
        self.timeout_seconds = timeout_seconds

    def schema(self) -> dict[str, Any]:
        return schema_contract()

    def subgraph(
        self,
        label: str,
        identity: str,
        depth: int = 2,
        limit: int = 50,
    ) -> dict[str, Any]:
        if label not in NODE_IDENTITIES:
            raise ValueError(f"지원하지 않는 노드 라벨입니다: {label}")
        if not 1 <= depth <= 3:
            raise ValueError("depth는 1~3이어야 합니다.")
        if not 1 <= limit <= 100:
            raise ValueError("limit은 1~100이어야 합니다.")

        identity_property = NODE_IDENTITIES[label]
        statement = f"""
        MATCH (root:`{label}`)
        WHERE root.`{identity_property}` = $identity
        CALL (root) {{
          OPTIONAL MATCH path=(root)-[*1..{depth}]-(neighbor)
          RETURN path
          LIMIT $limit
        }}
        WITH root, collect(path) AS paths
        RETURN root, paths
        """
        with self.driver.session(
            database=self.database,
            default_access_mode=READ_ACCESS,
        ) as session:
            record = session.run(
                Query(statement, timeout=self.timeout_seconds),
                identity=identity,
                limit=limit,
            ).single()

        if record is None:
            return {
                "root": None,
                "nodes": [],
                "relationships": [],
                "node_count": 0,
                "relationship_count": 0,
                "depth": depth,
                "truncated": False,
            }

        root = record["root"]
        paths = [path for path in record["paths"] if isinstance(path, Path)]
        nodes: dict[str, dict[str, Any]] = {}
        relationships: dict[str, dict[str, Any]] = {}
        if isinstance(root, Node):
            nodes[root.element_id] = _node_payload(root)
        for path in paths:
            for node in path.nodes:
                nodes[node.element_id] = _node_payload(node)
            for relationship in path.relationships:
                relationships[relationship.element_id] = (
                    _relationship_payload(relationship)
                )
        return {
            "root": _node_payload(root) if isinstance(root, Node) else None,
            "nodes": list(nodes.values()),
            "relationships": list(relationships.values()),
            "node_count": len(nodes),
            "relationship_count": len(relationships),
            "depth": depth,
            "truncated": len(paths) >= limit,
        }
