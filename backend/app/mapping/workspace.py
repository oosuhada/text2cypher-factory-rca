"""Validate mapping drafts against uploaded profiles and build manifests."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

from backend.app.ingestion import DatasetWorkspace
from backend.app.schema_registry import SchemaRegistry


NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
TYPE_MAP = {
    "EMPTY": "STRING",
    "STRING": "STRING",
    "INTEGER": "INTEGER",
    "FLOAT": "FLOAT",
    "BOOLEAN": "BOOLEAN",
}


class MappingWorkspace:
    def __init__(
        self,
        root: Path,
        datasets: DatasetWorkspace,
        schemas: SchemaRegistry,
    ):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.datasets = datasets
        self.schemas = schemas

    def _columns(self, profile: dict[str, Any]) -> dict[str, dict[str, dict]]:
        return {
            file["filename"]: {
                column["name"]: column for column in file["columns"]
            }
            for file in profile["files"]
        }

    def preview(
        self,
        project_id: str,
        upload_id: str,
        mapping: dict[str, Any],
        *,
        schema_version: str = "1.0",
    ) -> dict[str, Any]:
        profile = self.datasets.get(project_id, upload_id)
        columns = self._columns(profile)
        file_rows = {
            file["filename"]: file["row_count"] for file in profile["files"]
        }
        nodes = mapping.get("nodes")
        relationships = mapping.get("relationships", [])
        if not isinstance(nodes, list) or not nodes:
            raise ValueError("mapping.nodes는 비어 있지 않은 배열이어야 합니다.")
        if not isinstance(relationships, list):
            raise ValueError("mapping.relationships는 배열이어야 합니다.")
        manifest_nodes = []
        labels = set()
        node_sources: dict[str, str] = {}
        for node in nodes:
            label = str(node.get("label", ""))
            source_file = str(node.get("source_file", ""))
            identity = str(node.get("identity", ""))
            properties = node.get("properties") or {}
            if not NAME.fullmatch(label) or label in labels:
                raise ValueError(f"유효하지 않거나 중복된 노드 라벨입니다: {label}")
            if source_file not in columns:
                raise ValueError(f"{label} source_file을 찾을 수 없습니다: {source_file}")
            if identity not in columns[source_file]:
                raise ValueError(f"{label} identity 컬럼이 없습니다: {identity}")
            if not isinstance(properties, dict) or not properties:
                raise ValueError(f"{label}.properties가 필요합니다.")
            property_types = {}
            for graph_property, source_column in properties.items():
                if not NAME.fullmatch(str(graph_property)):
                    raise ValueError(f"유효하지 않은 속성명입니다: {graph_property}")
                if source_column not in columns[source_file]:
                    raise ValueError(
                        f"{label}.{graph_property} 원본 컬럼이 없습니다: {source_column}"
                    )
                property_types[graph_property] = TYPE_MAP[
                    columns[source_file][source_column]["inferred_type"]
                ]
            if identity not in properties:
                properties = {identity: identity, **properties}
                property_types = {
                    identity: TYPE_MAP[columns[source_file][identity]["inferred_type"]],
                    **property_types,
                }
            labels.add(label)
            node_sources[label] = source_file
            manifest_nodes.append(
                {
                    "label": label,
                    "identity": identity,
                    "properties": property_types,
                }
            )
        manifest_relationships = []
        for relationship in relationships:
            rel_type = str(relationship.get("type", ""))
            source = str(relationship.get("source", ""))
            target = str(relationship.get("target", ""))
            source_key = str(relationship.get("source_key", ""))
            target_key = str(relationship.get("target_key", ""))
            if not NAME.fullmatch(rel_type):
                raise ValueError(f"유효하지 않은 관계 타입입니다: {rel_type}")
            if source not in labels or target not in labels:
                raise ValueError(f"{rel_type}의 source/target 노드가 없습니다.")
            if source_key not in columns[node_sources[source]]:
                raise ValueError(f"{rel_type} source_key 컬럼이 없습니다.")
            if target_key not in columns[node_sources[target]]:
                raise ValueError(f"{rel_type} target_key 컬럼이 없습니다.")
            manifest_relationships.append(
                {"type": rel_type, "source": source, "targets": [target]}
            )
        manifest = {
            "project_id": project_id,
            "version": schema_version,
            "title": mapping.get("title") or f"{project_id} graph",
            "nodes": manifest_nodes,
            "relationships": manifest_relationships,
            "output_rules": mapping.get(
                "output_rules",
                ["Return only evidence found in the selected project graph."],
            ),
        }
        self.schemas.validate(manifest, expected_project_id=project_id)
        return {
            "project_id": project_id,
            "upload_id": upload_id,
            "status": "preview",
            "manifest": manifest,
            "mapping": mapping,
            "estimated_node_rows": {
                label: file_rows[source] for label, source in node_sources.items()
            },
            "estimated_relationship_rows": {
                row["type"]: min(
                    file_rows[node_sources[row["source"]]],
                    file_rows[node_sources[row["target"]]],
                )
                for row in relationships
            },
        }

    def approve(
        self,
        project_id: str,
        upload_id: str,
        mapping: dict[str, Any],
        *,
        schema_version: str = "1.0",
    ) -> dict[str, Any]:
        result = self.preview(
            project_id, upload_id, mapping, schema_version=schema_version
        )
        approved_at = datetime.now(timezone.utc).isoformat()
        record = {**result, "status": "approved", "approved_at": approved_at}
        path = self.root / project_id / "mapping.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.schemas.save(project_id, result["manifest"])
        return record

    def get(self, project_id: str) -> dict[str, Any]:
        path = self.root / project_id / "mapping.json"
        if not path.exists():
            raise KeyError(f"승인된 매핑이 없습니다: {project_id}")
        return json.loads(path.read_text(encoding="utf-8"))
