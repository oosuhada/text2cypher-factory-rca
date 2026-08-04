"""Transactional, project-isolated loading for approved graph mappings."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable

from neo4j import Driver, WRITE_ACCESS

from backend.app.ingestion import DatasetWorkspace
from backend.app.ingestion.coercion import coerce_value
from backend.app.ingestion.readers import read_tabular_path
from backend.app.mapping import MappingWorkspace


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _batches(rows: list[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    for start in range(0, len(rows), size):
        yield rows[start : start + size]


def _safe_schema_name(prefix: str, *parts: str) -> str:
    raw = "_".join((prefix, *parts)).lower()
    normalized = re.sub(r"[^a-z0-9_]+", "_", raw).strip("_")
    if len(normalized) <= 55:
        return normalized
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:8]
    return f"{normalized[:46]}_{digest}"


class LoadReportStore:
    """Persist load state without exposing credentials or raw records."""

    def __init__(self, root: Path):
        self.root = root.resolve()

    def _path(self, project_id: str, upload_id: str) -> Path:
        if not re.fullmatch(r"[a-z][a-z0-9-]{2,62}", project_id):
            raise ValueError("유효하지 않은 load report project_id입니다.")
        if not re.fullmatch(r"[A-Za-z0-9-]{8,80}", upload_id):
            raise ValueError("유효하지 않은 load report upload_id입니다.")
        return self.root / project_id / f"{upload_id}.json"

    def write(
        self,
        project_id: str,
        upload_id: str,
        report: dict[str, Any],
    ) -> Path:
        path = self._path(project_id, upload_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
        return path

    def get(self, project_id: str, upload_id: str) -> dict[str, Any]:
        path = self._path(project_id, upload_id)
        if not path.exists():
            raise KeyError("적재 보고서를 찾을 수 없습니다.")
        return json.loads(path.read_text(encoding="utf-8"))


class GenericGraphLoader:
    def __init__(
        self,
        datasets: DatasetWorkspace,
        mappings: MappingWorkspace,
        *,
        database: str = "neo4j",
        batch_size: int = 500,
        report_root: Path | None = None,
    ):
        if batch_size < 1:
            raise ValueError("batch_size는 1 이상이어야 합니다.")
        self.datasets = datasets
        self.mappings = mappings
        self.database = database
        self.batch_size = batch_size
        self.reports = LoadReportStore(
            report_root or mappings.root.parent / "load_reports"
        )

    def _verify_approved_sources(
        self,
        project_id: str,
        upload_id: str,
        approved: dict[str, Any],
    ) -> Path:
        if approved["upload_id"] != upload_id:
            raise ValueError("승인된 매핑과 요청 upload_id가 다릅니다.")
        source_root = (
            self.datasets._project_root(project_id) / upload_id / "source"
        )
        for file in (approved.get("dry_run") or {}).get(
            "lineage", {}
        ).get("normalized_files", []):
            path = source_root / file["filename"]
            if not path.exists():
                raise ValueError(
                    f"승인된 정규화 파일이 없습니다: {file['filename']}"
                )
            actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual_hash != file["sha256"]:
                raise ValueError(
                    "승인 후 정규화 파일이 변경되었습니다: "
                    f"{file['filename']}"
                )
        return source_root

    @staticmethod
    def _prepare(
        source_root: Path,
        approved: dict[str, Any],
    ) -> dict[str, Any]:
        mapping = approved["mapping"]
        manifest_nodes = {
            node["label"]: node for node in approved["manifest"]["nodes"]
        }
        nodes_by_label = {node["label"]: node for node in mapping["nodes"]}
        node_rows: dict[str, list[dict[str, Any]]] = {}
        node_identities: dict[str, set[Any]] = {}

        for node in mapping["nodes"]:
            rows = read_tabular_path(source_root / node["source_file"])
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
                        for graph_property, source_column in node[
                            "properties"
                        ].items()
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
            node_rows[node["label"]] = list(unique_projected.values())
            node_identities[node["label"]] = set(unique_projected)

        relationship_rows: dict[str, list[dict[str, Any]]] = {}
        for relationship in mapping.get("relationships", []):
            source_node = nodes_by_label[relationship["source"]]
            target_node = nodes_by_label[relationship["target"]]
            relationship_file = relationship.get(
                "source_file", source_node["source_file"]
            )
            rows = read_tabular_path(source_root / relationship_file)
            relationship_manifest = next(
                row
                for row in approved["manifest"]["relationships"]
                if row["type"] == relationship["type"]
            )
            property_types = relationship_manifest.get("properties") or {}
            unique_projected: dict[tuple[Any, Any], dict[str, Any]] = {}
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
                            property_types[graph_property],
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
                # MERGE identifies a relationship by its endpoints and type.
                # Property changes update the same relationship rather than
                # creating parallel edges, so dry-run and load use the same key.
                unique_projected.setdefault(
                    (source_value, target_value),
                    {
                        "source_value": source_value,
                        "target_value": target_value,
                        **property_values,
                    },
                )
            relationship_rows[relationship["type"]] = list(
                unique_projected.values()
            )

        return {
            "mapping": mapping,
            "manifest": approved["manifest"],
            "nodes": node_rows,
            "relationships": relationship_rows,
            "expected": {
                "nodes": {
                    label: len(rows) for label, rows in node_rows.items()
                },
                "relationships": {
                    rel_type: len(rows)
                    for rel_type, rows in relationship_rows.items()
                },
            },
        }

    def _apply_schema(
        self,
        driver: Driver,
        prepared: dict[str, Any],
    ) -> list[str]:
        existing = driver.execute_query(
            """
            SHOW CONSTRAINTS
            YIELD name, labelsOrTypes, properties, type
            RETURN name, labelsOrTypes, properties, type
            """,
            database_=self.database,
            routing_="r",
        ).records
        legacy_conflicts = []
        identities = {
            node["label"]: node["identity"]
            for node in prepared["manifest"]["nodes"]
        }
        for record in existing:
            values = (
                record.data() if hasattr(record, "data") else dict(record)
            )
            labels = values.get("labelsOrTypes") or []
            properties = values.get("properties") or []
            if (
                len(labels) == 1
                and identities.get(labels[0]) in properties
                and "project_id" not in properties
                and "UNIQUENESS" in str(values.get("type", ""))
            ):
                legacy_conflicts.append(str(values.get("name")))
        if legacy_conflicts:
            raise RuntimeError(
                "멀티 프로젝트 적재와 충돌하는 전역 uniqueness constraint가 "
                f"있습니다: {legacy_conflicts}. "
                "scripts/migrate_project_scoped_schema.py를 먼저 실행하세요."
            )
        applied: list[str] = []
        for node in prepared["manifest"]["nodes"]:
            label = node["label"]
            identity = node["identity"]
            name = _safe_schema_name(
                "p3_scope_unique", label, identity
            )
            statement = (
                f"CREATE CONSTRAINT `{name}` IF NOT EXISTS "
                f"FOR (node:`{label}`) "
                f"REQUIRE (node.project_id, node.`{identity}`) IS UNIQUE"
            )
            driver.execute_query(
                statement,
                database_=self.database,
                routing_="w",
            )
            applied.append(name)
        for relationship in prepared["manifest"].get(
            "relationships", []
        ):
            rel_type = relationship["type"]
            name = _safe_schema_name("p3_scope_upload", rel_type)
            statement = (
                f"CREATE INDEX `{name}` IF NOT EXISTS "
                f"FOR ()-[rel:`{rel_type}`]-() "
                "ON (rel.project_id, rel.source_upload_id)"
            )
            driver.execute_query(
                statement,
                database_=self.database,
                routing_="w",
            )
            applied.append(name)
        return applied

    @staticmethod
    def _counter_values(summary: Any) -> dict[str, int]:
        counters = summary.counters
        return {
            name: int(getattr(counters, name, 0))
            for name in (
                "nodes_created",
                "relationships_created",
                "properties_set",
                "labels_added",
            )
        }

    @staticmethod
    def _add_counters(
        total: dict[str, int], current: dict[str, int]
    ) -> None:
        for name, value in current.items():
            total[name] = total.get(name, 0) + value

    def _load_transaction(
        self,
        tx: Any,
        project_id: str,
        upload_id: str,
        prepared: dict[str, Any],
    ) -> dict[str, Any]:
        mapping = prepared["mapping"]
        nodes_by_label = {
            node["label"]: node for node in mapping["nodes"]
        }
        counters: dict[str, int] = {}
        for node in mapping["nodes"]:
            identity = node["identity"]
            assignments = ", ".join(
                f"node.`{name}` = row.`{name}`"
                for name in node["properties"]
                if name != identity
            )
            set_clause = f"SET {assignments}, " if assignments else "SET "
            query = (
                "UNWIND $rows AS row "
                f"MERGE (node:`{node['label']}` "
                f"{{project_id: $project_id, `{identity}`: row.`{identity}`}}) "
                f"{set_clause}node.project_id = $project_id, "
                "node.source_upload_id = $upload_id"
            )
            for batch in _batches(
                prepared["nodes"][node["label"]], self.batch_size
            ):
                summary = tx.run(
                    query,
                    rows=batch,
                    project_id=project_id,
                    upload_id=upload_id,
                ).consume()
                self._add_counters(
                    counters, self._counter_values(summary)
                )

        for relationship in mapping.get("relationships", []):
            source_node = nodes_by_label[relationship["source"]]
            target_node = nodes_by_label[relationship["target"]]
            assignments = ", ".join(
                f"rel.`{name}` = row.`{name}`"
                for name in (relationship.get("properties") or {})
            )
            set_clause = f"SET {assignments}, " if assignments else "SET "
            query = (
                "UNWIND $rows AS row "
                f"MATCH (source:`{source_node['label']}` "
                f"{{project_id: $project_id, "
                f"`{source_node['identity']}`: row.source_value}}) "
                f"MATCH (target:`{target_node['label']}` "
                f"{{project_id: $project_id, "
                f"`{target_node['identity']}`: row.target_value}}) "
                f"MERGE (source)-[rel:`{relationship['type']}`]->(target) "
                f"{set_clause}rel.project_id = $project_id, "
                "rel.source_upload_id = $upload_id"
            )
            for batch in _batches(
                prepared["relationships"][relationship["type"]],
                self.batch_size,
            ):
                summary = tx.run(
                    query,
                    rows=batch,
                    project_id=project_id,
                    upload_id=upload_id,
                ).consume()
                self._add_counters(
                    counters, self._counter_values(summary)
                )

        actual_nodes: dict[str, int] = {}
        for node in mapping["nodes"]:
            record = tx.run(
                (
                    f"MATCH (node:`{node['label']}` "
                    "{project_id: $project_id, "
                    "source_upload_id: $upload_id}) "
                    "RETURN count(node) AS count"
                ),
                project_id=project_id,
                upload_id=upload_id,
            ).single()
            actual_nodes[node["label"]] = int(record["count"])

        actual_relationships: dict[str, int] = {}
        for relationship in mapping.get("relationships", []):
            record = tx.run(
                (
                    f"MATCH ()-[rel:`{relationship['type']}` "
                    "{project_id: $project_id, "
                    "source_upload_id: $upload_id}]->() "
                    "RETURN count(rel) AS count"
                ),
                project_id=project_id,
                upload_id=upload_id,
            ).single()
            actual_relationships[relationship["type"]] = int(
                record["count"]
            )

        cross_scope = tx.run(
            """
            MATCH (source)-[rel {project_id: $project_id}]->(target)
            WHERE source.project_id IS NULL
               OR target.project_id IS NULL
               OR source.project_id <> $project_id
               OR target.project_id <> $project_id
            RETURN count(rel) AS count
            """,
            project_id=project_id,
        ).single()
        cross_scope_count = int(cross_scope["count"])
        expected = prepared["expected"]
        mismatches = {
            "nodes": {
                label: {
                    "expected": expected["nodes"][label],
                    "actual": actual_nodes.get(label, 0),
                }
                for label in expected["nodes"]
                if actual_nodes.get(label, 0) != expected["nodes"][label]
            },
            "relationships": {
                rel_type: {
                    "expected": expected["relationships"][rel_type],
                    "actual": actual_relationships.get(rel_type, 0),
                }
                for rel_type in expected["relationships"]
                if actual_relationships.get(rel_type, 0)
                != expected["relationships"][rel_type]
            },
        }
        if mismatches["nodes"] or mismatches["relationships"]:
            raise RuntimeError(
                "적재 건수 reconciliation 실패: "
                f"{json.dumps(mismatches, ensure_ascii=False)}"
            )
        if cross_scope_count:
            raise RuntimeError(
                f"프로젝트 경계를 넘는 관계가 {cross_scope_count}건 있습니다."
            )
        scoped = tx.run(
            """
            MATCH (node {project_id: $project_id})
            WITH count(node) AS nodes
            OPTIONAL MATCH ()-[rel {project_id: $project_id}]->()
            RETURN nodes, count(rel) AS relationships
            """,
            project_id=project_id,
        ).single()
        return {
            "status": "PASS",
            "expected": expected,
            "actual": {
                "nodes": actual_nodes,
                "relationships": actual_relationships,
            },
            "mismatches": mismatches,
            "cross_project_relationship_count": cross_scope_count,
            "scoped_node_count": int(scoped["nodes"]),
            "scoped_relationship_count": int(scoped["relationships"]),
            "project_scope_applied": True,
            "transactional": True,
            "counters": counters,
        }

    def load(
        self,
        driver: Driver,
        project_id: str,
        upload_id: str,
    ) -> dict[str, Any]:
        approved = self.mappings.get(project_id)
        started_at = _utc_now()
        base_report = {
            "project_id": project_id,
            "upload_id": upload_id,
            "status": "loading",
            "started_at": started_at,
            "batch_size": self.batch_size,
        }
        self.reports.write(project_id, upload_id, base_report)
        try:
            source_root = self._verify_approved_sources(
                project_id, upload_id, approved
            )
            prepared = self._prepare(source_root, approved)
            schema_objects = self._apply_schema(driver, prepared)
            with driver.session(
                database=self.database,
                default_access_mode=WRITE_ACCESS,
            ) as session:
                integrity = session.execute_write(
                    self._load_transaction,
                    project_id,
                    upload_id,
                    prepared,
                )
            finished_at = _utc_now()
            result = {
                **base_report,
                "status": "loaded",
                "finished_at": finished_at,
                "input": prepared["expected"],
                "dry_run": approved.get("dry_run", {}),
                "lineage": (approved.get("dry_run") or {}).get(
                    "lineage", {}
                ),
                "schema_objects": schema_objects,
                "integrity": integrity,
                "access": {
                    "loader_mode": "WRITE",
                    "reader_mode": "READ",
                },
            }
            report_path = self.reports.write(
                project_id, upload_id, result
            )
            return {**result, "report_path": str(report_path)}
        except Exception as error:
            failed = {
                **base_report,
                "status": "load_failed",
                "finished_at": _utc_now(),
                "error_type": type(error).__name__,
                "error": str(error),
                "rollback_expected": True,
            }
            self.reports.write(project_id, upload_id, failed)
            raise
