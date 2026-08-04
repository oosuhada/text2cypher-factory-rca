"""Load an approved tabular mapping into a project-isolated Neo4j graph."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from neo4j import Driver

from backend.app.ingestion import DatasetWorkspace
from backend.app.ingestion.coercion import coerce_value
from backend.app.ingestion.readers import read_tabular_path
from backend.app.mapping import MappingWorkspace


def _read_rows(path: Path) -> list[dict[str, Any]]:
    return read_tabular_path(path)


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
        for file in (approved.get("dry_run") or {}).get(
            "lineage", {}
        ).get("normalized_files", []):
            path = source_root / file["filename"]
            actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual_hash != file["sha256"]:
                raise ValueError(
                    "승인 후 정규화 파일이 변경되었습니다: "
                    f"{file['filename']}"
                )
        mapping = approved["mapping"]
        manifest_nodes = {
            node["label"]: node for node in approved["manifest"]["nodes"]
        }
        nodes_by_label = {node["label"]: node for node in mapping["nodes"]}
        loaded_nodes: dict[str, int] = {}
        loaded_relationships: dict[str, int] = {}
        node_identities: dict[str, set[Any]] = {}
        for node in mapping["nodes"]:
            rows = _read_rows(source_root / node["source_file"])
            identity = node["identity"]
            unique_projected: dict[Any, dict[str, Any]] = {}
            for row in rows:
                try:
                    projected_row = {
                        graph_property: coerce_value(
                            row.get(source_column),
                            manifest_nodes[node["label"]]["properties"][
                                graph_property
                            ],
                        )
                        for graph_property, source_column
                        in node["properties"].items()
                    }
                except (TypeError, ValueError):
                    continue
                identity_value = projected_row.get(identity)
                if identity_value in (None, ""):
                    continue
                if any(
                    projected_row.get(name) is None
                    for name in manifest_nodes[node["label"]].get(
                        "required_properties", []
                    )
                ):
                    continue
                unique_projected.setdefault(identity_value, projected_row)
            projected = list(unique_projected.values())
            node_identities[node["label"]] = set(unique_projected)
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
            relationship_manifest = next(
                row
                for row in approved["manifest"]["relationships"]
                if row["type"] == relationship["type"]
            )
            relationship_property_types = (
                relationship_manifest.get("properties") or {}
            )
            unique_projected: dict[tuple[Any, ...], dict[str, Any]] = {}
            for row in rows:
                try:
                    source_value = coerce_value(
                        row.get(relationship["source_key"]),
                        manifest_nodes[source_node["label"]]["properties"][
                            source_node["identity"]
                        ],
                    )
                    target_value = coerce_value(
                        row.get(relationship["target_key"]),
                        manifest_nodes[target_node["label"]]["properties"][
                            target_node["identity"]
                        ],
                    )
                    property_values = {
                        graph_property: coerce_value(
                            row.get(source_column),
                            relationship_property_types[graph_property],
                        )
                        for graph_property, source_column in (
                            relationship.get("properties") or {}
                        ).items()
                    }
                except (TypeError, ValueError):
                    continue
                if any(
                    property_values.get(name) is None
                    for name in relationship_manifest.get(
                        "required_properties", []
                    )
                ):
                    continue
                if (
                    source_value not in node_identities[source_node["label"]]
                    or target_value not in node_identities[target_node["label"]]
                ):
                    continue
                relationship_key = (
                    source_value,
                    target_value,
                    *property_values.values(),
                )
                unique_projected.setdefault(
                    relationship_key,
                    {
                        "source_value": source_value,
                        "target_value": target_value,
                        **property_values,
                    },
                )
            projected = list(unique_projected.values())
            relationship_assignments = ", ".join(
                f"rel.`{name}` = row.`{name}`"
                for name in (relationship.get("properties") or {})
            )
            relationship_set = (
                f"SET {relationship_assignments}, "
                if relationship_assignments
                else "SET "
            )
            query = (
                "UNWIND $rows AS row "
                f"MATCH (source:`{source_node['label']}` "
                f"{{project_id: $project_id, `{source_node['identity']}`: row.source_value}}) "
                f"MATCH (target:`{target_node['label']}` "
                f"{{project_id: $project_id, `{target_node['identity']}`: row.target_value}}) "
                f"MERGE (source)-[rel:`{relationship['type']}`]->(target) "
                f"{relationship_set}rel.project_id = $project_id, "
                "rel.source_upload_id = $upload_id"
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
            "dry_run": approved.get("dry_run", {}),
            "lineage": (approved.get("dry_run") or {}).get(
                "lineage", {}
            ),
            "integrity": {
                "scoped_node_count": int(counts["nodes"]),
                "scoped_relationship_count": int(counts["relationships"]),
                "project_scope_applied": True,
            },
        }
