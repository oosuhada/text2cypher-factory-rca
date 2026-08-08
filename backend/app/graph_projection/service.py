"""Idempotent V3.1 ontology graph projection into project-scoped Neo4j."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from threading import RLock
from typing import Any, Protocol
from uuid import NAMESPACE_URL, uuid5

from neo4j import GraphDatabase, WRITE_ACCESS

from backend.app.etl.cli import password_from_keychain

from .models import (
    GraphProjectionCounts,
    GraphProjectionRequest,
    GraphProjectionResponse,
)


OBJECT_LABELS = {
    "site": "Site",
    "production_cell": "ProductionCell",
    "equipment": "Equipment",
    "risk_event": "RiskEvent",
    "prediction_result": "PredictionResult",
    "work_order": "WorkOrder",
    "maintenance_action": "MaintenanceAction",
    "production_cycle": "ProductionCycle",
}
RELATIONSHIP_TYPES = {
    "SITE_CONTAINS_CELL",
    "CELL_CONTAINS_EQUIPMENT",
    "SUPPLIES_AIR_TO",
    "HAS_RISK_EVENT",
    "HAS_PREDICTION_RESULT",
    "SUPPORTED_BY_PREDICTION_RESULT",
    "HAS_WORK_ORDER",
    "HAS_MAINTENANCE_ACTION",
    "COMPLETED_PRODUCTION_CYCLE",
}
RAW_OBJECT_TYPES = {
    "sensor_observation",
    "compressor_sensor_observation",
    "cnc_sensor_observation",
    "prediction_timeline",
}
RESERVED_NODE_PROPERTIES = {
    "organization_id",
    "project_id",
    "workspace_id",
    "dataset_id",
    "dataset_version_id",
    "object_type",
    "source_identity",
    "source_reference",
    "source_sha256",
    "projection_id",
    "materialization_checksum_sha256",
}
RESERVED_RELATIONSHIP_PROPERTIES = {
    "organization_id",
    "project_id",
    "workspace_id",
    "dataset_id",
    "dataset_version_id",
    "relationship_identity",
    "source_reference",
    "source_sha256",
    "projection_id",
    "materialization_checksum_sha256",
}


class GraphProjectionValidationError(ValueError):
    pass


class GraphProjectionConflict(RuntimeError):
    pass


class GraphProjectionUnavailable(RuntimeError):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _request_checksum(request: GraphProjectionRequest) -> str:
    payload = request.model_dump(mode="json", by_alias=True, exclude={"requested_at"})
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class ProjectionReceiptStore:
    """Persist idempotency receipts separately from the projected domain graph."""

    def __init__(self, path: Path):
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS graph_projection_receipts (
                    project_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    projection_id TEXT NOT NULL,
                    dataset_version_id TEXT NOT NULL,
                    request_checksum_sha256 TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(project_id,idempotency_key)
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def get(self, project_id: str, idempotency_key: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM graph_projection_receipts
                WHERE project_id=? AND idempotency_key=?
                """,
                (project_id, idempotency_key),
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["response"] = json.loads(result.pop("response_json"))
        return result

    def save(
        self,
        request: GraphProjectionRequest,
        *,
        request_checksum_sha256: str,
        response: GraphProjectionResponse,
    ) -> None:
        timestamp = _utc_now().isoformat()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO graph_projection_receipts(
                    project_id,idempotency_key,projection_id,dataset_version_id,
                    request_checksum_sha256,response_json,created_at,updated_at
                ) VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(project_id,idempotency_key) DO UPDATE SET
                    projection_id=excluded.projection_id,
                    dataset_version_id=excluded.dataset_version_id,
                    request_checksum_sha256=excluded.request_checksum_sha256,
                    response_json=excluded.response_json,
                    updated_at=excluded.updated_at
                """,
                (
                    request.project_id,
                    request.idempotency_key,
                    request.projection_id,
                    request.dataset_version_id,
                    request_checksum_sha256,
                    json.dumps(response.model_dump(mode="json"), sort_keys=True),
                    timestamp,
                    timestamp,
                ),
            )
            connection.commit()


class ProjectionWriter(Protocol):
    def project(self, request: GraphProjectionRequest) -> GraphProjectionCounts:
        ...


class InMemoryProjectionWriter:
    """Contract-test writer with the same MERGE identity as Neo4j."""

    def __init__(self) -> None:
        self.nodes: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        self.relationships: dict[
            tuple[str, str, str, str, str, str], dict[str, Any]
        ] = {}
        self.calls = 0

    def project(self, request: GraphProjectionRequest) -> GraphProjectionCounts:
        self.calls += 1
        for node in request.nodes:
            key = (
                request.project_id,
                request.dataset_version_id,
                node.identity.object_type,
                node.identity.source_identity,
            )
            self.nodes[key] = node.model_dump(mode="json")
        for relationship in request.relationships:
            key = (
                request.project_id,
                request.dataset_version_id,
                relationship.relationship_type,
                relationship.from_identity.object_type,
                relationship.from_identity.source_identity,
                f"{relationship.to_identity.object_type}:{relationship.to_identity.source_identity}",
            )
            self.relationships[key] = relationship.model_dump(mode="json")
        return GraphProjectionCounts(
            nodes_received=len(request.nodes),
            relationships_received=len(request.relationships),
            nodes_written=len(request.nodes),
            relationships_written=len(request.relationships),
        )


class Neo4jProjectionWriter:
    def __init__(
        self,
        *,
        uri: str | None = None,
        database: str | None = None,
        username: str | None = None,
        password: str | None = None,
        batch_size: int = 500,
    ) -> None:
        self.uri = uri or os.getenv("NEO4J_URI", "neo4j://localhost:7687")
        self.database = database or os.getenv("NEO4J_DATABASE", "neo4j")
        self.username = username or os.getenv(
            "NEO4J_LOADER_USERNAME", os.getenv("NEO4J_USERNAME", "neo4j")
        )
        self.password = password
        self.batch_size = max(1, batch_size)

    def _password(self) -> str:
        password = (
            self.password
            or os.getenv("NEO4J_LOADER_PASSWORD")
            or os.getenv("NEO4J_PASSWORD")
            or password_from_keychain(self.username)
        )
        if not password:
            raise GraphProjectionUnavailable(
                "Neo4j loader credentials are unavailable"
            )
        return password

    @staticmethod
    def _batches(rows: list[dict[str, Any]], size: int):
        for start in range(0, len(rows), size):
            yield rows[start : start + size]

    def _apply_schema(self, driver: Any) -> None:
        for label in sorted(set(OBJECT_LABELS.values())):
            name = f"od_scope_{label.lower()}_identity"
            driver.execute_query(
                (
                    f"CREATE CONSTRAINT `{name}` IF NOT EXISTS "
                    f"FOR (node:`{label}`) REQUIRE "
                    "(node.project_id,node.dataset_version_id,node.object_type,"
                    "node.source_identity) IS UNIQUE"
                ),
                database_=self.database,
                routing_="w",
            )
        for relationship_type in sorted(RELATIONSHIP_TYPES):
            name = f"od_scope_{relationship_type.lower()}_identity"
            driver.execute_query(
                (
                    f"CREATE INDEX `{name}` IF NOT EXISTS "
                    f"FOR ()-[rel:`{relationship_type}`]-() "
                    "ON (rel.project_id,rel.dataset_version_id,"
                    "rel.relationship_identity)"
                ),
                database_=self.database,
                routing_="w",
            )

    @staticmethod
    def _safe_properties(
        properties: dict[str, Any], reserved: set[str]
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in properties.items():
            if key in reserved:
                continue
            if isinstance(value, (dict, list)):
                result[key] = json.dumps(value, ensure_ascii=False, sort_keys=True)
            else:
                result[key] = value
        return result

    def _write_transaction(
        self, tx: Any, request: GraphProjectionRequest
    ) -> GraphProjectionCounts:
        grouped_nodes: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for node in request.nodes:
            label = OBJECT_LABELS[node.identity.object_type]
            grouped_nodes[label].append(
                {
                    "object_type": node.identity.object_type,
                    "source_identity": node.identity.source_identity,
                    "properties": self._safe_properties(
                        node.properties, RESERVED_NODE_PROPERTIES
                    ),
                    "source_reference": node.source_reference,
                    "source_sha256": node.source_sha256,
                }
            )
        for label, rows in grouped_nodes.items():
            statement = (
                "UNWIND $rows AS row "
                f"MERGE (node:`{label}` {{"
                "project_id:$project_id,dataset_version_id:$dataset_version_id,"
                "object_type:row.object_type,source_identity:row.source_identity}) "
                "SET node += row.properties,"
                "node.organization_id=$organization_id,"
                "node.workspace_id=$workspace_id,"
                "node.dataset_id=$dataset_id,"
                "node.source_reference=row.source_reference,"
                "node.source_sha256=row.source_sha256,"
                "node.projection_id=$projection_id,"
                "node.materialization_checksum_sha256=$materialization_checksum_sha256"
            )
            for batch in self._batches(rows, self.batch_size):
                tx.run(
                    statement,
                    rows=batch,
                    organization_id=request.organization_id,
                    project_id=request.project_id,
                    workspace_id=request.workspace_id,
                    dataset_id=request.dataset_id,
                    dataset_version_id=request.dataset_version_id,
                    projection_id=request.projection_id,
                    materialization_checksum_sha256=(
                        request.materialization_checksum_sha256
                    ),
                ).consume()

        grouped_relationships: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for relationship in request.relationships:
            relationship_identity = (
                f"{relationship.from_identity.object_type}:"
                f"{relationship.from_identity.source_identity}->"
                f"{relationship.to_identity.object_type}:"
                f"{relationship.to_identity.source_identity}"
            )
            grouped_relationships[relationship.relationship_type].append(
                {
                    "from_object_type": relationship.from_identity.object_type,
                    "from_source_identity": relationship.from_identity.source_identity,
                    "to_object_type": relationship.to_identity.object_type,
                    "to_source_identity": relationship.to_identity.source_identity,
                    "relationship_identity": relationship_identity,
                    "properties": self._safe_properties(
                        relationship.properties,
                        RESERVED_RELATIONSHIP_PROPERTIES,
                    ),
                    "source_reference": relationship.source_reference,
                    "source_sha256": relationship.source_sha256,
                }
            )
        for relationship_type, rows in grouped_relationships.items():
            statement = (
                "UNWIND $rows AS row "
                "MATCH (source {project_id:$project_id,"
                "dataset_version_id:$dataset_version_id,"
                "object_type:row.from_object_type,"
                "source_identity:row.from_source_identity}) "
                "MATCH (target {project_id:$project_id,"
                "dataset_version_id:$dataset_version_id,"
                "object_type:row.to_object_type,"
                "source_identity:row.to_source_identity}) "
                f"MERGE (source)-[rel:`{relationship_type}` {{"
                "project_id:$project_id,dataset_version_id:$dataset_version_id,"
                "relationship_identity:row.relationship_identity}]->(target) "
                "SET rel += row.properties,"
                "rel.organization_id=$organization_id,"
                "rel.workspace_id=$workspace_id,"
                "rel.dataset_id=$dataset_id,"
                "rel.source_reference=row.source_reference,"
                "rel.source_sha256=row.source_sha256,"
                "rel.projection_id=$projection_id,"
                "rel.materialization_checksum_sha256=$materialization_checksum_sha256"
            )
            for batch in self._batches(rows, self.batch_size):
                tx.run(
                    statement,
                    rows=batch,
                    organization_id=request.organization_id,
                    project_id=request.project_id,
                    workspace_id=request.workspace_id,
                    dataset_id=request.dataset_id,
                    dataset_version_id=request.dataset_version_id,
                    projection_id=request.projection_id,
                    materialization_checksum_sha256=(
                        request.materialization_checksum_sha256
                    ),
                ).consume()

        node_record = tx.run(
            """
            MATCH (node {project_id:$project_id,dataset_version_id:$dataset_version_id})
            WHERE node.object_type IN $object_types
            RETURN count(node) AS count
            """,
            project_id=request.project_id,
            dataset_version_id=request.dataset_version_id,
            object_types=sorted(request.object_counts),
        ).single()
        relationship_record = tx.run(
            """
            MATCH ()-[rel {project_id:$project_id,dataset_version_id:$dataset_version_id}]->()
            WHERE type(rel) IN $relationship_types
            RETURN count(rel) AS count
            """,
            project_id=request.project_id,
            dataset_version_id=request.dataset_version_id,
            relationship_types=sorted(set(relationship.relationship_type for relationship in request.relationships)),
        ).single()
        cross_scope = tx.run(
            """
            MATCH (source)-[rel {project_id:$project_id,dataset_version_id:$dataset_version_id}]->(target)
            WHERE source.project_id <> $project_id OR target.project_id <> $project_id
               OR source.dataset_version_id <> $dataset_version_id
               OR target.dataset_version_id <> $dataset_version_id
            RETURN count(rel) AS count
            """,
            project_id=request.project_id,
            dataset_version_id=request.dataset_version_id,
        ).single()
        nodes_written = int(node_record["count"]) if node_record else 0
        relationships_written = (
            int(relationship_record["count"]) if relationship_record else 0
        )
        if nodes_written != len(request.nodes):
            raise GraphProjectionValidationError(
                f"Neo4j node reconciliation failed: {nodes_written} != {len(request.nodes)}"
            )
        if relationships_written != len(request.relationships):
            raise GraphProjectionValidationError(
                "Neo4j relationship reconciliation failed: "
                f"{relationships_written} != {len(request.relationships)}"
            )
        if cross_scope and int(cross_scope["count"]) != 0:
            raise GraphProjectionValidationError(
                "Neo4j projection contains cross-project or cross-version relationships"
            )
        return GraphProjectionCounts(
            nodes_received=len(request.nodes),
            relationships_received=len(request.relationships),
            nodes_written=nodes_written,
            relationships_written=relationships_written,
        )

    def project(self, request: GraphProjectionRequest) -> GraphProjectionCounts:
        driver = GraphDatabase.driver(
            self.uri,
            auth=(self.username, self._password()),
        )
        try:
            driver.verify_connectivity()
            self._apply_schema(driver)
            with driver.session(
                database=self.database,
                default_access_mode=WRITE_ACCESS,
            ) as session:
                return session.execute_write(self._write_transaction, request)
        except GraphProjectionValidationError:
            raise
        except Exception as error:
            raise GraphProjectionUnavailable(
                f"Neo4j graph projection failed: {error}"
            ) from error
        finally:
            driver.close()


class OntologyGraphProjectionService:
    def __init__(
        self,
        writer: ProjectionWriter,
        receipts: ProjectionReceiptStore,
    ) -> None:
        self.writer = writer
        self.receipts = receipts

    @staticmethod
    def _validate_semantics(request: GraphProjectionRequest) -> None:
        object_types = {node.identity.object_type for node in request.nodes}
        unknown_objects = object_types - set(OBJECT_LABELS)
        if unknown_objects:
            raise GraphProjectionValidationError(
                f"unsupported projection object types: {sorted(unknown_objects)}"
            )
        raw_objects = object_types & RAW_OBJECT_TYPES
        if raw_objects:
            raise GraphProjectionValidationError(
                f"raw observations cannot be projected: {sorted(raw_objects)}"
            )
        relationship_types = {
            relationship.relationship_type for relationship in request.relationships
        }
        unknown_relationships = relationship_types - RELATIONSHIP_TYPES
        if unknown_relationships:
            raise GraphProjectionValidationError(
                "unsupported projection relationship types: "
                f"{sorted(unknown_relationships)}"
            )
        for node in request.nodes:
            if node.identity.object_type == "work_order":
                if node.properties.get("actual_maintenance_event") is not True:
                    raise GraphProjectionValidationError(
                        "WorkOrder nodes must originate from canonical maintenance events"
                    )
                if node.properties.get("origin") != "canonical_maintenance_event":
                    raise GraphProjectionValidationError(
                        "recommended actions cannot be promoted to WorkOrder nodes"
                    )
            if node.identity.object_type in {"risk_event", "prediction_result"}:
                predicted_type = node.properties.get("predicted_failure_type")
                if predicted_type not in {"failure_risk", "no_significant_risk"}:
                    raise GraphProjectionValidationError(
                        "prediction nodes must retain generic binary risk semantics"
                    )
        for relationship in request.relationships:
            if relationship.relationship_type == "SUPPLIES_AIR_TO":
                if relationship.properties.get("causal_claim_allowed") is not False:
                    raise GraphProjectionValidationError(
                        "SUPPLIES_AIR_TO must remain topology-only"
                    )
            if (
                relationship.from_identity.object_type == "risk_event"
                and relationship.to_identity.object_type == "work_order"
            ):
                raise GraphProjectionValidationError(
                    "recommended risk actions cannot create WorkOrder relationships"
                )

    def project(self, request: GraphProjectionRequest) -> GraphProjectionResponse:
        self._validate_semantics(request)
        checksum = _request_checksum(request)
        existing = self.receipts.get(request.project_id, request.idempotency_key)
        if existing is not None:
            if existing["request_checksum_sha256"] != checksum:
                raise GraphProjectionConflict(
                    "idempotency key was already used for different projection content"
                )
            response = GraphProjectionResponse.model_validate(existing["response"])
            return response.model_copy(update={"idempotent_replay": True})

        counts = self.writer.project(request)
        run_id = f"p3-proj-{uuid5(NAMESPACE_URL, request.idempotency_key)}"
        response = GraphProjectionResponse(
            projection_id=request.projection_id,
            project_id=request.project_id,
            dataset_version_id=request.dataset_version_id,
            status="completed",
            project3_run_id=run_id,
            projection_checksum_sha256=checksum,
            counts=counts,
            updated_at=_utc_now(),
        )
        self.receipts.save(
            request,
            request_checksum_sha256=checksum,
            response=response,
        )
        return response

    def get(self, project_id: str, projection_id: str) -> GraphProjectionResponse:
        # Projection IDs are deterministic, but receipt lookup is keyed by the
        # idempotency key. Scan the small local receipt table by projection ID.
        with self.receipts._lock, self.receipts._connect() as connection:
            row = connection.execute(
                """
                SELECT response_json FROM graph_projection_receipts
                WHERE project_id=? AND projection_id=?
                """,
                (project_id, projection_id),
            ).fetchone()
        if row is None:
            raise KeyError(f"projection not found: {projection_id}")
        return GraphProjectionResponse.model_validate(json.loads(row["response_json"]))


def predictive_maintenance_schema_manifest(
    request: GraphProjectionRequest,
) -> dict[str, Any]:
    node_properties = {
        "organization_id": "STRING",
        "project_id": "STRING",
        "workspace_id": "STRING",
        "dataset_id": "STRING",
        "dataset_version_id": "STRING",
        "object_type": "STRING",
        "source_identity": "STRING",
        "source_reference": "STRING",
        "source_sha256": "STRING",
        "projection_id": "STRING",
        "materialization_checksum_sha256": "STRING",
    }
    domain_properties = {
        "Site": {
            "display_name": "STRING",
            "site_id": "STRING",
        },
        "ProductionCell": {
            "display_name": "STRING",
            "cell_id": "STRING",
            "site_id": "STRING",
        },
        "Equipment": {
            "display_name": "STRING",
            "asset_id": "STRING",
            "asset_type": "STRING",
            "site_id": "STRING",
            "cell_id": "STRING",
            "line": "STRING",
            "criticality": "STRING",
        },
        "RiskEvent": {
            "artifact_id": "STRING",
            "asset_id": "STRING",
            "status": "STRING",
            "status_grade": "STRING",
            "failure_probability": "FLOAT",
            "confidence": "FLOAT",
            "prediction_task": "STRING",
            "predicted_failure_type": "STRING",
            "recommended_decision": "STRING",
            "recommended_action": "STRING",
            "recommendation_execution_state": "STRING",
            "top_factors": "STRING",
            "observed_at": "DATETIME",
            "model_version": "STRING",
            "result_contract_source": "STRING",
        },
        "PredictionResult": {
            "prediction_id": "STRING",
            "asset_id": "STRING",
            "observed_at": "DATETIME",
            "prediction_horizon_hours": "INTEGER",
            "prediction_task": "STRING",
            "failure_probability": "FLOAT",
            "predicted_failure_type": "STRING",
            "confidence": "FLOAT",
            "model_version": "STRING",
            "feature_scope": "STRING",
            "result_contract_source": "STRING",
        },
        "WorkOrder": {
            "status": "STRING",
            "work_type": "STRING",
            "maintenance_id": "STRING",
            "asset_id": "STRING",
            "started_at": "DATETIME",
            "completed_at": "DATETIME",
            "tool_replaced": "BOOLEAN",
            "actual_maintenance_event": "BOOLEAN",
            "origin": "STRING",
        },
        "MaintenanceAction": {
            "action": "STRING",
            "actor": "STRING",
            "created_at": "DATETIME",
            "maintenance_id": "STRING",
            "actual_maintenance_event": "BOOLEAN",
        },
        "ProductionCycle": {
            "product_id": "STRING",
            "cnc_asset_id": "STRING",
            "cycle_started_at": "DATETIME",
            "cycle_completed_at": "DATETIME",
            "product_type": "STRING",
            "cutting_minutes": "FLOAT",
            "tool_wear_increment_min": "FLOAT",
        },
    }
    nodes = []
    for label in OBJECT_LABELS.values():
        nodes.append(
            {
                "label": label,
                "identity": "source_identity",
                "required_properties": [
                    "source_identity",
                    "dataset_version_id",
                    "source_reference",
                ],
                "properties": {
                    **node_properties,
                    **domain_properties[label],
                },
            }
        )
    relationships = [
        {
            "type": "SITE_CONTAINS_CELL",
            "source": "Site",
            "targets": ["ProductionCell"],
            "cardinality": "ONE_TO_MANY",
        },
        {
            "type": "CELL_CONTAINS_EQUIPMENT",
            "source": "ProductionCell",
            "targets": ["Equipment"],
            "cardinality": "ONE_TO_MANY",
        },
        {
            "type": "SUPPLIES_AIR_TO",
            "source": "Equipment",
            "targets": ["Equipment"],
            "cardinality": "MANY_TO_MANY",
            "properties": {
                "semantics": "STRING",
                "causal_claim_allowed": "BOOLEAN",
            },
        },
        {
            "type": "HAS_RISK_EVENT",
            "source": "Equipment",
            "targets": ["RiskEvent"],
            "cardinality": "ONE_TO_MANY",
        },
        {
            "type": "HAS_PREDICTION_RESULT",
            "source": "Equipment",
            "targets": ["PredictionResult"],
            "cardinality": "ONE_TO_MANY",
        },
        {
            "type": "SUPPORTED_BY_PREDICTION_RESULT",
            "source": "RiskEvent",
            "targets": ["PredictionResult"],
            "cardinality": "MANY_TO_ONE",
        },
        {
            "type": "HAS_WORK_ORDER",
            "source": "Equipment",
            "targets": ["WorkOrder"],
            "cardinality": "ONE_TO_MANY",
        },
        {
            "type": "HAS_MAINTENANCE_ACTION",
            "source": "WorkOrder",
            "targets": ["MaintenanceAction"],
            "cardinality": "ONE_TO_ONE",
        },
        {
            "type": "COMPLETED_PRODUCTION_CYCLE",
            "source": "Equipment",
            "targets": ["ProductionCycle"],
            "cardinality": "ONE_TO_MANY",
        },
    ]
    return {
        "project_id": request.project_id,
        "version": request.mapping_version,
        "source_version": request.source_version,
        "isolation_mode": "dataset_version_property",
        "title": "Predictive Maintenance V3.1 Ontology Graph",
        "nodes": nodes,
        "relationships": relationships,
        "output_rules": [
            "SUPPLIES_AIR_TO is topology only and must not be described as confirmed causality.",
            "Do not produce CAUSES or ROOT_CAUSE_OF claims from topology alone.",
            "predicted_failure_type is a generic binary risk class, not PWF/HDF/OSF/TWF.",
            "recommended_action is a recommendation and is not an executed WorkOrder.",
            "Always return dataset_version_id and source_reference as graph provenance.",
        ],
        "query_scenarios": [
            {
                "id": "pm-topology-1",
                "question": "압축기에서 공급받는 CNC 설비를 보여줘.",
                "required_nodes": ["Equipment"],
                "required_relationships": ["SUPPLIES_AIR_TO"],
                "required_properties": ["Equipment.source_identity"],
            },
            {
                "id": "pm-risk-work-1",
                "question": "설비의 위험 예측과 실제 정비 작업을 근거와 함께 보여줘.",
                "required_nodes": [
                    "Equipment",
                    "RiskEvent",
                    "PredictionResult",
                    "WorkOrder",
                    "MaintenanceAction",
                ],
                "required_relationships": [
                    "HAS_RISK_EVENT",
                    "SUPPORTED_BY_PREDICTION_RESULT",
                    "HAS_WORK_ORDER",
                    "HAS_MAINTENANCE_ACTION",
                ],
                "required_properties": [
                    "Equipment.source_identity",
                    "RiskEvent.source_reference",
                    "WorkOrder.source_reference",
                ],
            },
        ],
    }
