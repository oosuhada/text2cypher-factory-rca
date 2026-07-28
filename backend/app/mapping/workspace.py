"""Validate mapping drafts against uploaded profiles and build manifests."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

from backend.app.ingestion import DatasetWorkspace
from backend.app.ingestion.coercion import coerce_value
from backend.app.ingestion.readers import read_tabular_path
from backend.app.schema_registry import SchemaRegistry


NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
TYPE_MAP = {
    "EMPTY": "STRING",
    "STRING": "STRING",
    "INTEGER": "INTEGER",
    "FLOAT": "FLOAT",
    "BOOLEAN": "BOOLEAN",
}
SUPPORTED_PROPERTY_TYPES = {
    *TYPE_MAP.values(),
    "DATE",
    "DATETIME",
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

    @staticmethod
    def _property_types(
        *,
        owner: str,
        properties: dict[str, str],
        overrides: dict[str, str],
        source_columns: dict[str, dict],
    ) -> dict[str, str]:
        unknown_overrides = set(overrides) - set(properties)
        if unknown_overrides:
            raise ValueError(
                f"{owner}.property_types에 매핑되지 않은 속성이 있습니다: "
                f"{sorted(unknown_overrides)}"
            )
        resolved: dict[str, str] = {}
        for graph_property, source_column in properties.items():
            override = overrides.get(graph_property)
            if override is not None:
                normalized = str(override).upper()
                if normalized not in SUPPORTED_PROPERTY_TYPES:
                    raise ValueError(
                        f"{owner}.{graph_property} 타입이 유효하지 않습니다: "
                        f"{override}"
                    )
                resolved[graph_property] = normalized
            else:
                resolved[graph_property] = TYPE_MAP[
                    source_columns[source_column]["inferred_type"]
                ]
        return resolved

    @staticmethod
    def _isolation(
        examples: list[dict[str, Any]],
        *,
        reason: str,
        owner: str,
        row_number: int,
        values: dict[str, Any],
    ) -> None:
        if len(examples) < 20:
            examples.append(
                {
                    "reason": reason,
                    "owner": owner,
                    "row_number": row_number,
                    "values": values,
                }
            )

    def _dry_run(
        self,
        *,
        project_id: str,
        upload_id: str,
        profile: dict[str, Any],
        mapping: dict[str, Any],
        manifest: dict[str, Any],
    ) -> dict[str, Any]:
        source_root = (
            self.datasets._project_root(project_id) / upload_id / "source"
        )
        rows_by_file: dict[str, list[dict[str, Any]]] = {}

        def rows(filename: str) -> list[dict[str, Any]]:
            if filename not in rows_by_file:
                rows_by_file[filename] = read_tabular_path(
                    source_root / filename
                )
            return rows_by_file[filename]

        manifest_nodes = {
            node["label"]: node for node in manifest["nodes"]
        }
        mapping_nodes = {
            node["label"]: node for node in mapping["nodes"]
        }
        identities: dict[str, set[Any]] = {}
        node_reports: dict[str, dict[str, Any]] = {}
        isolation_examples: list[dict[str, Any]] = []
        isolation_count = 0
        for node in mapping["nodes"]:
            label = node["label"]
            identity = node["identity"]
            identity_source = node["properties"][identity]
            property_types = manifest_nodes[label]["properties"]
            unique_identities: set[Any] = set()
            missing_identity = 0
            duplicate_identity = 0
            type_errors = 0
            missing_required = 0
            input_rows = rows(node["source_file"])
            for row_number, row in enumerate(input_rows, start=2):
                raw_identity = row.get(identity_source)
                if raw_identity in (None, ""):
                    missing_identity += 1
                    isolation_count += 1
                    self._isolation(
                        isolation_examples,
                        reason="missing_identity",
                        owner=label,
                        row_number=row_number,
                        values={identity_source: raw_identity},
                    )
                    continue
                try:
                    projected = {
                        graph_property: coerce_value(
                            row.get(source_column),
                            property_types[graph_property],
                        )
                        for graph_property, source_column
                        in node["properties"].items()
                    }
                except (TypeError, ValueError) as error:
                    type_errors += 1
                    isolation_count += 1
                    self._isolation(
                        isolation_examples,
                        reason="type_error",
                        owner=label,
                        row_number=row_number,
                        values={"error": str(error)},
                    )
                    continue
                missing_properties = [
                    name
                    for name in manifest_nodes[label].get(
                        "required_properties", []
                    )
                    if projected.get(name) is None
                ]
                if missing_properties:
                    missing_required += 1
                    isolation_count += 1
                    self._isolation(
                        isolation_examples,
                        reason="missing_required_property",
                        owner=label,
                        row_number=row_number,
                        values={"properties": missing_properties},
                    )
                    continue
                identity_value = projected[identity]
                if identity_value in unique_identities:
                    duplicate_identity += 1
                    isolation_count += 1
                    self._isolation(
                        isolation_examples,
                        reason="duplicate_identity",
                        owner=label,
                        row_number=row_number,
                        values={identity: identity_value},
                    )
                    continue
                unique_identities.add(identity_value)
            identities[label] = unique_identities
            node_reports[label] = {
                "source_file": node["source_file"],
                "input_rows": len(input_rows),
                "projected_rows": len(unique_identities),
                "missing_identity_count": missing_identity,
                "duplicate_identity_count": duplicate_identity,
                "type_error_count": type_errors,
                "missing_required_property_count": missing_required,
            }

        relationship_reports: dict[str, dict[str, Any]] = {}
        for relationship in mapping.get("relationships", []):
            rel_type = relationship["type"]
            source_node = mapping_nodes[relationship["source"]]
            target_node = mapping_nodes[relationship["target"]]
            relationship_file = relationship.get(
                "source_file", source_node["source_file"]
            )
            input_rows = rows(relationship_file)
            source_type = manifest_nodes[source_node["label"]][
                "properties"
            ][source_node["identity"]]
            target_type = manifest_nodes[target_node["label"]][
                "properties"
            ][target_node["identity"]]
            relationship_manifest = next(
                row
                for row in manifest["relationships"]
                if row["type"] == rel_type
            )
            property_types = relationship_manifest.get("properties") or {}
            valid_relationships: set[tuple[Any, ...]] = set()
            missing_keys = 0
            orphan_rows = 0
            duplicate_rows = 0
            type_errors = 0
            missing_required = 0
            for row_number, row in enumerate(input_rows, start=2):
                try:
                    source_value = coerce_value(
                        row.get(relationship["source_key"]), source_type
                    )
                    target_value = coerce_value(
                        row.get(relationship["target_key"]), target_type
                    )
                    property_values = tuple(
                        coerce_value(
                            row.get(source_column),
                            property_types[graph_property],
                        )
                        for graph_property, source_column in (
                            relationship.get("properties") or {}
                        ).items()
                    )
                except (TypeError, ValueError) as error:
                    type_errors += 1
                    isolation_count += 1
                    self._isolation(
                        isolation_examples,
                        reason="type_error",
                        owner=rel_type,
                        row_number=row_number,
                        values={"error": str(error)},
                    )
                    continue
                property_value_map = dict(
                    zip(
                        (relationship.get("properties") or {}).keys(),
                        property_values,
                    )
                )
                missing_properties = [
                    name
                    for name in relationship_manifest.get(
                        "required_properties", []
                    )
                    if property_value_map.get(name) is None
                ]
                if missing_properties:
                    missing_required += 1
                    isolation_count += 1
                    self._isolation(
                        isolation_examples,
                        reason="missing_required_property",
                        owner=rel_type,
                        row_number=row_number,
                        values={"properties": missing_properties},
                    )
                    continue
                if source_value is None or target_value is None:
                    missing_keys += 1
                    isolation_count += 1
                    self._isolation(
                        isolation_examples,
                        reason="missing_relationship_key",
                        owner=rel_type,
                        row_number=row_number,
                        values={
                            "source": source_value,
                            "target": target_value,
                        },
                    )
                    continue
                if (
                    source_value not in identities[source_node["label"]]
                    or target_value not in identities[target_node["label"]]
                ):
                    orphan_rows += 1
                    isolation_count += 1
                    self._isolation(
                        isolation_examples,
                        reason="orphan_relationship",
                        owner=rel_type,
                        row_number=row_number,
                        values={
                            "source": source_value,
                            "target": target_value,
                        },
                    )
                    continue
                # The loader MERGEs one relationship per source/target/type.
                # Keep preview counts identical to the actual graph identity;
                # later property differences update that relationship.
                relationship_key = (source_value, target_value)
                if relationship_key in valid_relationships:
                    duplicate_rows += 1
                    isolation_count += 1
                    self._isolation(
                        isolation_examples,
                        reason="duplicate_relationship",
                        owner=rel_type,
                        row_number=row_number,
                        values={
                            "source": source_value,
                            "target": target_value,
                        },
                    )
                    continue
                valid_relationships.add(relationship_key)
            relationship_reports[rel_type] = {
                "source_file": relationship_file,
                "input_rows": len(input_rows),
                "projected_rows": len(valid_relationships),
                "missing_key_count": missing_keys,
                "orphan_count": orphan_rows,
                "duplicate_count": duplicate_rows,
                "type_error_count": type_errors,
                "missing_required_property_count": missing_required,
            }
        return {
            "status": "WARN" if isolation_count else "PASS",
            "project_id": project_id,
            "upload_id": upload_id,
            "nodes": node_reports,
            "relationships": relationship_reports,
            "isolation": {
                "count": isolation_count,
                "examples": isolation_examples,
            },
            "lineage": {
                "sources": profile.get("sources", []),
                "normalized_files": [
                    {
                        "filename": file["filename"],
                        "sha256": file["sha256"],
                        "lineage": file.get("lineage", {}),
                    }
                    for file in profile["files"]
                ],
            },
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
            property_type_overrides = node.get("property_types") or {}
            if not NAME.fullmatch(label) or label in labels:
                raise ValueError(f"유효하지 않거나 중복된 노드 라벨입니다: {label}")
            if source_file not in columns:
                raise ValueError(f"{label} source_file을 찾을 수 없습니다: {source_file}")
            if not isinstance(properties, dict) or not properties:
                raise ValueError(f"{label}.properties가 필요합니다.")
            if identity not in properties:
                raise ValueError(
                    f"{label} identity 속성이 properties에 없습니다: "
                    f"{identity}"
                )
            for graph_property, source_column in properties.items():
                if not NAME.fullmatch(str(graph_property)):
                    raise ValueError(f"유효하지 않은 속성명입니다: {graph_property}")
                if source_column not in columns[source_file]:
                    raise ValueError(
                        f"{label}.{graph_property} 원본 컬럼이 없습니다: {source_column}"
                    )
            property_types = self._property_types(
                owner=label,
                properties=properties,
                overrides=property_type_overrides,
                source_columns=columns[source_file],
            )
            required_properties = node.get(
                "required_properties", [identity]
            )
            labels.add(label)
            node_sources[label] = source_file
            manifest_nodes.append(
                {
                    "label": label,
                    "identity": identity,
                    "properties": property_types,
                    "required_properties": required_properties,
                    "source": {
                        "upload_id": upload_id,
                        "filename": source_file,
                    },
                }
            )
        manifest_relationships = []
        for relationship in relationships:
            rel_type = str(relationship.get("type", ""))
            source = str(relationship.get("source", ""))
            target = str(relationship.get("target", ""))
            source_key = str(relationship.get("source_key", ""))
            target_key = str(relationship.get("target_key", ""))
            relationship_file = str(
                relationship.get(
                    "source_file", node_sources.get(source, "")
                )
            )
            relationship_properties = relationship.get("properties") or {}
            relationship_type_overrides = (
                relationship.get("property_types") or {}
            )
            if not NAME.fullmatch(rel_type):
                raise ValueError(f"유효하지 않은 관계 타입입니다: {rel_type}")
            if source not in labels or target not in labels:
                raise ValueError(f"{rel_type}의 source/target 노드가 없습니다.")
            if relationship_file not in columns:
                raise ValueError(
                    f"{rel_type} source_file을 찾을 수 없습니다: "
                    f"{relationship_file}"
                )
            if source_key not in columns[relationship_file]:
                raise ValueError(f"{rel_type} source_key 컬럼이 없습니다.")
            if target_key not in columns[relationship_file]:
                raise ValueError(f"{rel_type} target_key 컬럼이 없습니다.")
            for graph_property, source_column in (
                relationship_properties.items()
            ):
                if not NAME.fullmatch(str(graph_property)):
                    raise ValueError(
                        f"유효하지 않은 관계 속성명입니다: {graph_property}"
                    )
                if source_column not in columns[relationship_file]:
                    raise ValueError(
                        f"{rel_type}.{graph_property} 원본 컬럼이 없습니다: "
                        f"{source_column}"
                    )
            relationship_property_types = self._property_types(
                owner=rel_type,
                properties=relationship_properties,
                overrides=relationship_type_overrides,
                source_columns=columns[relationship_file],
            )
            manifest_relationships.append(
                {
                    "type": rel_type,
                    "source": source,
                    "targets": [target],
                    "cardinality": relationship.get(
                        "cardinality", "MANY_TO_MANY"
                    ),
                    "properties": relationship_property_types,
                    "required_properties": relationship.get(
                        "required_properties", []
                    ),
                    "source_ref": {
                        "upload_id": upload_id,
                        "filename": relationship_file,
                    },
                }
            )
        manifest = {
            "project_id": project_id,
            "version": schema_version,
            "isolation_mode": "property",
            "source_version": mapping.get(
                "source_version", upload_id
            ),
            "title": mapping.get("title") or f"{project_id} graph",
            "nodes": manifest_nodes,
            "relationships": manifest_relationships,
            "query_scenarios": mapping.get("query_scenarios", []),
            "output_rules": mapping.get(
                "output_rules",
                ["Return only evidence found in the selected project graph."],
            ),
        }
        self.schemas.validate(manifest, expected_project_id=project_id)
        dry_run = self._dry_run(
            project_id=project_id,
            upload_id=upload_id,
            profile=profile,
            mapping=mapping,
            manifest=manifest,
        )
        return {
            "project_id": project_id,
            "upload_id": upload_id,
            "status": "preview",
            "manifest": manifest,
            "mapping": mapping,
            "dry_run": dry_run,
            "estimated_node_rows": {
                label: dry_run["nodes"][label]["projected_rows"]
                for label in node_sources
            },
            "estimated_relationship_rows": {
                row["type"]: dry_run["relationships"][row["type"]][
                    "projected_rows"
                ]
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
