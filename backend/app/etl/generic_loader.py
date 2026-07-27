"""Load an approved tabular mapping into a project-isolated Neo4j graph."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from neo4j import Driver

from backend.app.ingestion import DatasetWorkspace
from backend.app.mapping import MappingWorkspace


def _read_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as source:
            return [dict(row) for row in csv.DictReader(source)]
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(payload, dict):
        payload = payload.get("rows", payload.get("data", [payload]))
    return [dict(row) for row in payload]


class GenericGraphLoader:
    def __init__(
        self,
        datasets: DatasetWorkspace,
        mappings: MappingWorkspace,
        *,
        database: str = "neo4j",
    ):
        self.datasets = datasets
        self.mappings = mappings
        self.database = database

    def load(
        self,
        driver: Driver,
        project_id: str,
        upload_id: str,
    ) -> dict[str, Any]:
        approved = self.mappings.get(project_id)
        if approved["upload_id"] != upload_id:
            raise ValueError("승인된 매핑과 요청 upload_id가 다릅니다.")
        source_root = (
            self.datasets._project_root(project_id) / upload_id / "source"
        )
        mapping = approved["mapping"]
        nodes_by_label = {node["label"]: node for node in mapping["nodes"]}
        loaded_nodes: dict[str, int] = {}
        loaded_relationships: dict[str, int] = {}
        for node in mapping["nodes"]:
            rows = _read_rows(source_root / node["source_file"])
            identity = node["identity"]
            projected = [
                {
                    graph_property: row.get(source_column)
                    for graph_property, source_column in node["properties"].items()
                }
                | {identity: row.get(identity)}
                for row in rows
            ]
            projected = [row for row in projected if row.get(identity) not in (None, "")]
            assignments = ", ".join(
                f"node.`{name}` = row.`{name}`"
                for name in node["properties"]
                if name != identity
            )
            set_clause = (
                f"SET {assignments}, " if assignments else "SET "
            )
            query = (
                "UNWIND $rows AS row "
                f"MERGE (node:`{node['label']}` "
                f"{{project_id: $project_id, `{identity}`: row.`{identity}`}}) "
                f"{set_clause}node.project_id = $project_id, "
                "node.source_upload_id = $upload_id"
            )
            driver.execute_query(
                query,
                rows=projected,
                project_id=project_id,
                upload_id=upload_id,
                database_=self.database,
            )
            loaded_nodes[node["label"]] = len(projected)
        for relationship in mapping.get("relationships", []):
            source_node = nodes_by_label[relationship["source"]]
            target_node = nodes_by_label[relationship["target"]]
            relationship_file = relationship.get(
                "source_file", source_node["source_file"]
            )
            rows = _read_rows(source_root / relationship_file)
            projected = [
                {
                    "source_value": row.get(relationship["source_key"]),
                    "target_value": row.get(relationship["target_key"]),
                }
                for row in rows
            ]
            projected = [
                row
                for row in projected
                if row["source_value"] not in (None, "")
                and row["target_value"] not in (None, "")
            ]
            query = (
                "UNWIND $rows AS row "
                f"MATCH (source:`{source_node['label']}` "
                f"{{project_id: $project_id, `{source_node['identity']}`: row.source_value}}) "
                f"MATCH (target:`{target_node['label']}` "
                f"{{project_id: $project_id, `{target_node['identity']}`: row.target_value}}) "
                f"MERGE (source)-[rel:`{relationship['type']}`]->(target) "
                "SET rel.project_id = $project_id, rel.source_upload_id = $upload_id"
            )
            driver.execute_query(
                query,
                rows=projected,
                project_id=project_id,
                upload_id=upload_id,
                database_=self.database,
            )
            loaded_relationships[relationship["type"]] = len(projected)
        counts = driver.execute_query(
            """
            MATCH (node {project_id: $project_id})
            WITH count(node) AS nodes
            OPTIONAL MATCH ()-[rel {project_id: $project_id}]->()
            RETURN nodes, count(rel) AS relationships
            """,
            project_id=project_id,
            database_=self.database,
        ).records[0]
        return {
            "project_id": project_id,
            "upload_id": upload_id,
            "status": "loaded",
            "input": {
                "nodes": loaded_nodes,
                "relationships": loaded_relationships,
            },
            "integrity": {
                "scoped_node_count": int(counts["nodes"]),
                "scoped_relationship_count": int(counts["relationships"]),
                "project_scope_applied": True,
            },
        }
