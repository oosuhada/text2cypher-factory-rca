from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker
import pytest
from pydantic import ValidationError

from backend.app.api.main import create_app
from backend.app.graph_projection import (
    GraphProjectionConflict,
    GraphProjectionIdentity,
    GraphProjectionNode,
    GraphProjectionRelationship,
    GraphProjectionRequest,
    GovernanceArtifactReference,
    InMemoryProjectionWriter,
    OntologyGraphProjectionService,
    ProjectionReceiptStore,
    ResultProjectionContract,
    TopologyProjectionContract,
)
from backend.app.ingestion import DatasetWorkspace
from backend.app.projects import ProjectRegistry
from backend.app.schema_registry import SchemaRegistry


SHA_A = "a" * 64
SHA_B = "b" * 64
PROJECT_ID = "predictive-maintenance-v2"


def identity(
    object_type: str,
    source_identity: str,
    *,
    dataset_version_id: str = "dsv-v3-1",
) -> GraphProjectionIdentity:
    return GraphProjectionIdentity(
        organization_id="org-ontology-demo",
        project_id=PROJECT_ID,
        dataset_id="pm-canonical",
        dataset_version_id=dataset_version_id,
        object_type=object_type,
        source_identity=source_identity,
    )


def node(
    object_type: str,
    source_identity: str,
    properties: dict | None = None,
    *,
    dataset_version_id: str = "dsv-v3-1",
) -> GraphProjectionNode:
    return GraphProjectionNode(
        identity=identity(
            object_type,
            source_identity,
            dataset_version_id=dataset_version_id,
        ),
        properties=properties or {},
        source_reference=(
            f"dataset:pm-canonical:version:{dataset_version_id}:"
            f"role:asset_master:sha256:{SHA_A}:"
            f"object:{object_type}:{source_identity}"
        ),
        source_sha256=SHA_A,
    )


def relationship(
    relationship_type: str,
    source_type: str,
    source_identity: str,
    target_type: str,
    target_identity: str,
    properties: dict | None = None,
    *,
    dataset_version_id: str = "dsv-v3-1",
) -> GraphProjectionRelationship:
    return GraphProjectionRelationship(
        relationship_type=relationship_type,
        from_identity=identity(
            source_type,
            source_identity,
            dataset_version_id=dataset_version_id,
        ),
        to_identity=identity(
            target_type,
            target_identity,
            dataset_version_id=dataset_version_id,
        ),
        properties=properties or {},
        source_reference=(
            f"dataset:pm-canonical:version:{dataset_version_id}:"
            f"role:ontology_link:sha256:{SHA_A}:"
            f"object:{relationship_type}:{source_identity}->{target_identity}"
        ),
        source_sha256=SHA_A,
    )


def release_gates() -> dict:
    return {
        "tool_wear_continuity": {
            "pass": True,
            "running_reset_count": 0,
            "tool_replacement_event_count": 731,
            "aligned_reset_transition_count": 731,
            "reset_without_matching_maintenance_count": 0,
            "replacement_without_reset_count": 0,
        },
        "agent_example_evaluation": {
            "maintenance_evidence_accuracy": 1.0,
            "false_upstream_claim_rate": 0.0,
        },
    }


def request(
    *,
    dataset_version_id: str = "dsv-v3-1",
    idempotency_key: str = "graph-projection-v3-1",
) -> GraphProjectionRequest:
    nodes = [
        node("equipment", "CNC-001", dataset_version_id=dataset_version_id),
        node(
            "risk_event",
            "RESULT-001",
            {
                "predicted_failure_type": "failure_risk",
                "recommended_action": {"action": "inspect"},
                "recommendation_execution_state": "not_executed",
            },
            dataset_version_id=dataset_version_id,
        ),
        node(
            "prediction_result",
            "PRED-001",
            {"predicted_failure_type": "failure_risk"},
            dataset_version_id=dataset_version_id,
        ),
        node(
            "work_order",
            "MNT-001",
            {
                "actual_maintenance_event": True,
                "origin": "canonical_maintenance_event",
            },
            dataset_version_id=dataset_version_id,
        ),
        node(
            "maintenance_action",
            "MNT-001",
            {"actual_maintenance_event": True},
            dataset_version_id=dataset_version_id,
        ),
    ]
    relationships = [
        relationship(
            "HAS_RISK_EVENT",
            "equipment",
            "CNC-001",
            "risk_event",
            "RESULT-001",
            dataset_version_id=dataset_version_id,
        ),
        relationship(
            "HAS_PREDICTION_RESULT",
            "equipment",
            "CNC-001",
            "prediction_result",
            "PRED-001",
            dataset_version_id=dataset_version_id,
        ),
        relationship(
            "SUPPORTED_BY_PREDICTION_RESULT",
            "risk_event",
            "RESULT-001",
            "prediction_result",
            "PRED-001",
            dataset_version_id=dataset_version_id,
        ),
        relationship(
            "HAS_WORK_ORDER",
            "equipment",
            "CNC-001",
            "work_order",
            "MNT-001",
            {"actual_maintenance_event": True},
            dataset_version_id=dataset_version_id,
        ),
        relationship(
            "HAS_MAINTENANCE_ACTION",
            "work_order",
            "MNT-001",
            "maintenance_action",
            "MNT-001",
            {"actual_maintenance_event": True},
            dataset_version_id=dataset_version_id,
        ),
    ]
    return GraphProjectionRequest(
        projection_id=f"projection-{dataset_version_id}",
        idempotency_key=idempotency_key,
        organization_id="org-ontology-demo",
        project_id=PROJECT_ID,
        workspace_id="predictive-maintenance-main",
        dataset_id="pm-canonical",
        dataset_version_id=dataset_version_id,
        source_version="canonical-ai4i-physics-v3.1",
        bundle_checksum_sha256=SHA_A,
        materialization_checksum_sha256=SHA_B,
        mapping_id="pm-map-v3-1",
        mapping_version="predictive-maintenance-v3.1",
        role_checksums={"asset_master": SHA_A, "result_artifact": SHA_B},
        object_counts={
            "equipment": 1,
            "risk_event": 1,
            "prediction_result": 1,
            "work_order": 1,
            "maintenance_action": 1,
        },
        link_counts={
            "HAS_RISK_EVENT": 1,
            "HAS_PREDICTION_RESULT": 1,
            "SUPPORTED_BY_PREDICTION_RESULT": 1,
            "HAS_WORK_ORDER": 1,
            "HAS_MAINTENANCE_ACTION": 1,
        },
        result_contract=ResultProjectionContract(
            source_role="result_artifact",
            schema_versions=["result-artifact-v1.0"],
            model_versions=["independent-logreg-v3.1"],
            prediction_tasks=["binary_failure_within_horizon"],
            predicted_failure_type_semantics=(
                "generic_binary_risk_not_ai4i_failure_mode"
            ),
            source_sha256=SHA_B,
        ),
        release_gates=release_gates(),
        governance_artifacts=[
            GovernanceArtifactReference(
                role="package_validation",
                checksum_sha256=SHA_A,
            )
        ],
        topology_semantics=TopologyProjectionContract(
            SUPPLIES_AIR_TO="topology_only_not_causal_truth",
            causal_claim_allowed=False,
        ),
        excluded_sources=[
            "compressor_sensor_observation",
            "cnc_sensor_observation",
            "prediction_timeline",
            "canonical/evaluation_truth",
            "experiments/connected_air_supply/hidden_truth",
        ],
        graph_projection_status="pending",
        nodes=nodes,
        relationships=relationships,
        requested_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
    )


def full_v3_request() -> GraphProjectionRequest:
    nodes: list[GraphProjectionNode] = []
    relationships: list[GraphProjectionRelationship] = []
    for index in range(4):
        nodes.append(node("site", f"SITE-{index:02d}"))
    for index in range(20):
        nodes.append(node("production_cell", f"CELL-{index:02d}"))
        relationships.append(
            relationship(
                "SITE_CONTAINS_CELL",
                "site",
                f"SITE-{index // 5:02d}",
                "production_cell",
                f"CELL-{index:02d}",
            )
        )
    for index in range(100):
        nodes.append(node("equipment", f"EQ-{index:03d}"))
        relationships.append(
            relationship(
                "CELL_CONTAINS_EQUIPMENT",
                "production_cell",
                f"CELL-{index // 5:02d}",
                "equipment",
                f"EQ-{index:03d}",
            )
        )
        nodes.append(
            node(
                "risk_event",
                f"RESULT-{index:03d}",
                {
                    "predicted_failure_type": "failure_risk",
                    "recommendation_execution_state": "not_executed",
                },
            )
        )
        nodes.append(
            node(
                "prediction_result",
                f"PRED-{index:03d}",
                {"predicted_failure_type": "failure_risk"},
            )
        )
        relationships.extend(
            [
                relationship(
                    "HAS_RISK_EVENT",
                    "equipment",
                    f"EQ-{index:03d}",
                    "risk_event",
                    f"RESULT-{index:03d}",
                ),
                relationship(
                    "HAS_PREDICTION_RESULT",
                    "equipment",
                    f"EQ-{index:03d}",
                    "prediction_result",
                    f"PRED-{index:03d}",
                ),
                relationship(
                    "SUPPORTED_BY_PREDICTION_RESULT",
                    "risk_event",
                    f"RESULT-{index:03d}",
                    "prediction_result",
                    f"PRED-{index:03d}",
                ),
            ]
        )
    for index in range(80):
        relationships.append(
            relationship(
                "SUPPLIES_AIR_TO",
                "equipment",
                f"EQ-{index % 20:03d}",
                "equipment",
                f"EQ-{index + 20:03d}",
                {
                    "semantics": "topology_only",
                    "causal_claim_allowed": False,
                },
            )
        )
        nodes.append(node("production_cycle", f"CYCLE-{index:03d}"))
        relationships.append(
            relationship(
                "COMPLETED_PRODUCTION_CYCLE",
                "equipment",
                f"EQ-{index + 20:03d}",
                "production_cycle",
                f"CYCLE-{index:03d}",
            )
        )
    for index in range(790):
        nodes.append(
            node(
                "work_order",
                f"MNT-{index:04d}",
                {
                    "actual_maintenance_event": True,
                    "origin": "canonical_maintenance_event",
                },
            )
        )
        nodes.append(
            node(
                "maintenance_action",
                f"MNT-{index:04d}",
                {"actual_maintenance_event": True},
            )
        )
        relationships.extend(
            [
                relationship(
                    "HAS_WORK_ORDER",
                    "equipment",
                    f"EQ-{index % 100:03d}",
                    "work_order",
                    f"MNT-{index:04d}",
                    {"actual_maintenance_event": True},
                ),
                relationship(
                    "HAS_MAINTENANCE_ACTION",
                    "work_order",
                    f"MNT-{index:04d}",
                    "maintenance_action",
                    f"MNT-{index:04d}",
                    {"actual_maintenance_event": True},
                ),
            ]
        )
    base = request()
    return base.model_copy(
        update={
            "projection_id": "projection-full-v3-1",
            "idempotency_key": "graph-projection-full-v3-1",
            "object_counts": {
                "site": 4,
                "production_cell": 20,
                "equipment": 100,
                "risk_event": 100,
                "prediction_result": 100,
                "work_order": 790,
                "maintenance_action": 790,
                "production_cycle": 80,
            },
            "link_counts": {
                "SITE_CONTAINS_CELL": 20,
                "CELL_CONTAINS_EQUIPMENT": 100,
                "SUPPLIES_AIR_TO": 80,
                "HAS_RISK_EVENT": 100,
                "HAS_PREDICTION_RESULT": 100,
                "SUPPORTED_BY_PREDICTION_RESULT": 100,
                "HAS_WORK_ORDER": 790,
                "HAS_MAINTENANCE_ACTION": 790,
                "COMPLETED_PRODUCTION_CYCLE": 80,
            },
            "nodes": nodes,
            "relationships": relationships,
        }
    )


def test_full_v3_projection_is_idempotent_and_version_scoped(tmp_path: Path) -> None:
    writer = InMemoryProjectionWriter()
    service = OntologyGraphProjectionService(
        writer,
        ProjectionReceiptStore(tmp_path / "receipts.sqlite3"),
    )
    payload = GraphProjectionRequest.model_validate(
        full_v3_request().model_dump(mode="json", by_alias=True)
    )
    first = service.project(payload)
    second = service.project(payload)

    assert first.counts.nodes_written == 1_984
    assert first.counts.relationships_written == 2_160
    assert second.idempotent_replay is True
    assert writer.calls == 1
    assert len(writer.nodes) == 1_984
    assert len(writer.relationships) == 2_160

    other_version = request(
        dataset_version_id="dsv-v2",
        idempotency_key="graph-projection-v2",
    )
    service.project(other_version)
    assert len(writer.nodes) == 1_989
    assert {
        key[1] for key in writer.nodes
    } == {"dsv-v3-1", "dsv-v2"}


def test_projection_rejects_semantic_drift_and_idempotency_conflicts(
    tmp_path: Path,
) -> None:
    writer = InMemoryProjectionWriter()
    service = OntologyGraphProjectionService(
        writer,
        ProjectionReceiptStore(tmp_path / "receipts.sqlite3"),
    )
    payload = request()
    service.project(payload)
    changed = payload.model_copy(
        update={
            "nodes": [
                payload.nodes[0].model_copy(
                    update={"properties": {"changed": True}}
                ),
                *payload.nodes[1:],
            ]
        }
    )
    with pytest.raises(GraphProjectionConflict):
        service.project(changed)

    bad_work_order = request(idempotency_key="bad-work-order")
    bad_nodes = [
        item.model_copy(
            update={
                "properties": {
                    "actual_maintenance_event": False,
                    "origin": "recommended_action",
                }
            }
        )
        if item.identity.object_type == "work_order"
        else item
        for item in bad_work_order.nodes
    ]
    with pytest.raises(ValueError, match="canonical maintenance"):
        service.project(bad_work_order.model_copy(update={"nodes": bad_nodes}))

    with pytest.raises(ValidationError, match="causal relationship"):
        GraphProjectionRelationship(
            relationship_type="CAUSES",
            from_identity=identity("equipment", "EQ-1"),
            to_identity=identity("risk_event", "RISK-1"),
            properties={},
            source_reference="dataset:pm:version:v1",
            source_sha256=SHA_A,
        )

    broken_gate = payload.model_dump(mode="python", by_alias=True)
    broken_gate["release_gates"]["tool_wear_continuity"][
        "aligned_reset_transition_count"
    ] = 730
    with pytest.raises(ValidationError, match="release gate mismatch"):
        GraphProjectionRequest.model_validate(broken_gate)


def test_projection_http_contract_enforces_scope_and_records_schema(
    tmp_path: Path,
) -> None:
    projects = ProjectRegistry(tmp_path / "projects.sqlite3")
    projects.ensure_default()
    schemas = SchemaRegistry(tmp_path / "schemas")
    schemas.save(
        "cip-dmd",
        {
            "project_id": "cip-dmd",
            "version": "1.0",
            "title": "Test",
            "nodes": [
                {
                    "label": "Part",
                    "identity": "part_id",
                    "required_properties": ["part_id"],
                    "properties": {"part_id": "STRING"},
                }
            ],
            "relationships": [],
        },
    )
    service = OntologyGraphProjectionService(
        InMemoryProjectionWriter(),
        ProjectionReceiptStore(tmp_path / "receipts.sqlite3"),
    )
    bundle = SimpleNamespace(close=lambda: None)
    app = create_app(
        bundle_factory=lambda: bundle,
        project_registry=projects,
        schema_registry=schemas,
        dataset_workspace=DatasetWorkspace(tmp_path / "uploads"),
        graph_projection_service=service,
    )
    payload = request().model_dump(mode="json", by_alias=True)
    headers = {
        "X-Organization-ID": "org-ontology-demo",
        "X-Project-ID": PROJECT_ID,
        "X-Workspace-ID": "predictive-maintenance-main",
    }
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/projects/{PROJECT_ID}/graph/projections",
            json=payload,
            headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "completed"
        replay = client.post(
            f"/api/v1/projects/{PROJECT_ID}/graph/projections",
            json=payload,
            headers=headers,
        )
        assert replay.json()["idempotent_replay"] is True
        denied = client.post(
            f"/api/v1/projects/{PROJECT_ID}/graph/projections",
            json=payload,
            headers={**headers, "X-Project-ID": "other-project"},
        )
        assert denied.status_code == 403
        status = client.get(
            f"/api/v1/projects/{PROJECT_ID}/graph/projections/"
            f"{payload['projection_id']}",
            headers={"X-Project-ID": PROJECT_ID},
        )
        assert status.status_code == 200

    project = projects.require(PROJECT_ID)
    assert project["status"] == "ready"
    assert project["source_version"] == "canonical-ai4i-physics-v3.1"
    contract = schemas.contract(PROJECT_ID)
    assert "SUPPLIES_AIR_TO" in contract["relationship_types"]
    assert "CAUSES" not in contract["relationship_types"]
    assert any(
        "topology" in rule.lower()
        for rule in schemas.load(PROJECT_ID)["output_rules"]
    )


def test_provider_json_schema_accepts_the_typed_request_and_response(
    tmp_path: Path,
) -> None:
    del tmp_path
    schema = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "schemas"
            / "project3-graph-projection.schema.json"
        ).read_text(encoding="utf-8")
    )
    validator = Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
    )
    payload = request()
    response = OntologyGraphProjectionService(
        InMemoryProjectionWriter(),
        ProjectionReceiptStore(Path("/tmp/p3-schema-receipts.sqlite3")),
    ).project(payload)
    assert list(
        validator.iter_errors(payload.model_dump(mode="json", by_alias=True))
    ) == []
    assert list(
        validator.iter_errors(response.model_dump(mode="json", by_alias=True))
    ) == []
