"""Strict Project 2 → Project 3 graph projection contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


SHA256_PATTERN = r"^[a-f0-9]{64}$"
FORBIDDEN_RUNTIME_TERMS = {
    "evaluation_truth",
    "hidden_truth",
    "condition_variant",
    "failure_occurred_at",
    "source_event_id",
}


class ProjectionModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )


class GraphProjectionIdentity(ProjectionModel):
    organization_id: str = Field(min_length=1, max_length=160)
    project_id: str = Field(min_length=1, max_length=160)
    dataset_id: str = Field(min_length=1, max_length=160)
    dataset_version_id: str = Field(min_length=1, max_length=160)
    object_type: str = Field(min_length=1, max_length=160)
    source_identity: str = Field(min_length=1, max_length=256)


class GraphProjectionNode(ProjectionModel):
    identity: GraphProjectionIdentity
    properties: dict[str, Any] = Field(default_factory=dict)
    source_reference: str = Field(min_length=1, max_length=4096)
    source_sha256: str = Field(pattern=SHA256_PATTERN)


class GraphProjectionRelationship(ProjectionModel):
    relationship_type: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,127}$")
    from_identity: GraphProjectionIdentity
    to_identity: GraphProjectionIdentity
    properties: dict[str, Any] = Field(default_factory=dict)
    source_reference: str = Field(min_length=1, max_length=4096)
    source_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def relationship_scope_matches(self) -> "GraphProjectionRelationship":
        source_scope = (
            self.from_identity.organization_id,
            self.from_identity.project_id,
            self.from_identity.dataset_id,
            self.from_identity.dataset_version_id,
        )
        target_scope = (
            self.to_identity.organization_id,
            self.to_identity.project_id,
            self.to_identity.dataset_id,
            self.to_identity.dataset_version_id,
        )
        if source_scope != target_scope:
            raise ValueError(
                "projection relationship endpoints must share dataset version scope"
            )
        if self.relationship_type in {"CAUSES", "ROOT_CAUSE_OF"}:
            raise ValueError("topology projection cannot assert a causal relationship")
        return self


class GovernanceArtifactReference(ProjectionModel):
    role: Literal["package_validation", "agent_example_evaluation"]
    checksum_sha256: str = Field(pattern=SHA256_PATTERN)
    media_type: Literal["application/json"] = "application/json"


class ResultProjectionContract(ProjectionModel):
    source_role: Literal["result_artifact", "prediction_snapshot_compatibility"]
    schema_versions: list[str] = Field(min_length=1)
    model_versions: list[str] = Field(min_length=1)
    prediction_tasks: list[Literal["binary_failure_within_horizon"]] = Field(
        min_length=1
    )
    predicted_failure_type_semantics: Literal[
        "generic_binary_risk_not_ai4i_failure_mode"
    ]
    source_sha256: str = Field(pattern=SHA256_PATTERN)


class TopologyProjectionContract(ProjectionModel):
    supplies_air_to: Literal["topology_only_not_causal_truth"] = Field(
        alias="SUPPLIES_AIR_TO"
    )
    causal_claim_allowed: Literal[False] = False


class GraphProjectionRequest(ProjectionModel):
    contract_version: Literal["1.0"] = "1.0"
    message_type: Literal["graph_projection_request"] = "graph_projection_request"
    projection_id: str = Field(min_length=1, max_length=160)
    idempotency_key: str = Field(min_length=1, max_length=256)
    organization_id: str = Field(min_length=1, max_length=160)
    project_id: str = Field(min_length=1, max_length=160)
    workspace_id: str = Field(min_length=1, max_length=160)
    dataset_id: str = Field(min_length=1, max_length=160)
    dataset_version_id: str = Field(min_length=1, max_length=160)
    source_version: str = Field(min_length=1, max_length=160)
    bundle_checksum_sha256: str = Field(pattern=SHA256_PATTERN)
    materialization_checksum_sha256: str = Field(pattern=SHA256_PATTERN)
    mapping_id: str = Field(min_length=1, max_length=256)
    mapping_version: str = Field(min_length=1, max_length=160)
    role_checksums: dict[str, str] = Field(default_factory=dict)
    object_counts: dict[str, int] = Field(default_factory=dict)
    link_counts: dict[str, int] = Field(default_factory=dict)
    result_contract: ResultProjectionContract
    release_gates: dict[str, Any] = Field(default_factory=dict)
    governance_artifacts: list[GovernanceArtifactReference] = Field(
        default_factory=list
    )
    topology_semantics: TopologyProjectionContract
    excluded_sources: list[str] = Field(default_factory=list)
    graph_projection_status: Literal["pending"] = "pending"
    nodes: list[GraphProjectionNode] = Field(default_factory=list)
    relationships: list[GraphProjectionRelationship] = Field(default_factory=list)
    requested_at: datetime

    @model_validator(mode="after")
    def validate_projection_envelope(self) -> "GraphProjectionRequest":
        expected_scope = (
            self.organization_id,
            self.project_id,
            self.dataset_id,
            self.dataset_version_id,
        )
        identities = [node.identity for node in self.nodes]
        identities.extend(rel.from_identity for rel in self.relationships)
        identities.extend(rel.to_identity for rel in self.relationships)
        for identity in identities:
            actual_scope = (
                identity.organization_id,
                identity.project_id,
                identity.dataset_id,
                identity.dataset_version_id,
            )
            if actual_scope != expected_scope:
                raise ValueError("projection object scope must match request envelope")

        node_keys = [
            (node.identity.object_type, node.identity.source_identity)
            for node in self.nodes
        ]
        if len(node_keys) != len(set(node_keys)):
            raise ValueError("projection request contains duplicate node identities")
        node_key_set = set(node_keys)
        for relationship in self.relationships:
            source_key = (
                relationship.from_identity.object_type,
                relationship.from_identity.source_identity,
            )
            target_key = (
                relationship.to_identity.object_type,
                relationship.to_identity.source_identity,
            )
            if source_key not in node_key_set or target_key not in node_key_set:
                raise ValueError(
                    "projection relationships must reference nodes in the same request"
                )

        invalid_role_checksums = {
            role: checksum
            for role, checksum in self.role_checksums.items()
            if not isinstance(checksum, str)
            or len(checksum) != 64
            or any(character not in "0123456789abcdef" for character in checksum)
        }
        if invalid_role_checksums:
            raise ValueError(
                "projection role_checksums must be lowercase SHA-256 values"
            )
        if any(value < 0 for value in self.object_counts.values()):
            raise ValueError("projection object counts must not be negative")
        if any(value < 0 for value in self.link_counts.values()):
            raise ValueError("projection link counts must not be negative")
        if sum(self.object_counts.values()) != len(self.nodes):
            raise ValueError("projection object count contract does not match nodes")
        if sum(self.link_counts.values()) != len(self.relationships):
            raise ValueError(
                "projection relationship count contract does not match relationships"
            )

        rendered_runtime = str(
            {
                "nodes": [node.model_dump(mode="json") for node in self.nodes],
                "relationships": [
                    relationship.model_dump(mode="json")
                    for relationship in self.relationships
                ],
            }
        ).lower()
        if any(term in rendered_runtime for term in FORBIDDEN_RUNTIME_TERMS):
            raise ValueError("projection runtime payload exposes forbidden truth metadata")

        if self.source_version == "canonical-ai4i-physics-v3.1":
            if self.result_contract.source_role != "result_artifact":
                raise ValueError("v3.1 projection requires Result Artifact precedence")
            if self.result_contract.schema_versions != ["result-artifact-v1.0"]:
                raise ValueError("v3.1 projection requires result-artifact-v1.0")
            if self.result_contract.model_versions != ["independent-logreg-v3.1"]:
                raise ValueError("v3.1 projection requires independent-logreg-v3.1")
            continuity = self.release_gates.get("tool_wear_continuity")
            if not isinstance(continuity, dict) or continuity.get("pass") is not True:
                raise ValueError(
                    "v3.1 projection requires a passing tool-wear release gate"
                )
            expected_continuity = {
                "running_reset_count": 0,
                "tool_replacement_event_count": 731,
                "aligned_reset_transition_count": 731,
                "reset_without_matching_maintenance_count": 0,
                "replacement_without_reset_count": 0,
            }
            for field, expected in expected_continuity.items():
                if continuity.get(field) != expected:
                    raise ValueError(
                        f"v3.1 projection release gate mismatch: {field}"
                    )
            agent_gate = self.release_gates.get("agent_example_evaluation")
            if not isinstance(agent_gate, dict):
                raise ValueError(
                    "v3.1 projection requires agent evidence release metadata"
                )
            if agent_gate.get("maintenance_evidence_accuracy") != 1.0:
                raise ValueError(
                    "v3.1 projection requires valid maintenance evidence"
                )
            if agent_gate.get("false_upstream_claim_rate") != 0.0:
                raise ValueError(
                    "v3.1 projection rejects false upstream causal claims"
                )
        return self


ProjectionStatus = Literal[
    "accepted", "processing", "completed", "failed", "blocked"
]
ProjectionErrorCode = Literal[
    "validation_failed",
    "project_not_ready",
    "schema_version_unsupported",
    "identity_conflict",
    "graph_unavailable",
    "timeout",
    "internal_error",
]


class GraphProjectionError(ProjectionModel):
    code: ProjectionErrorCode
    message: str = Field(min_length=1, max_length=2000)
    retryable: bool
    retry_after_seconds: int | None = Field(default=None, ge=1)
    details: dict[str, Any] = Field(default_factory=dict)


class GraphProjectionCounts(ProjectionModel):
    nodes_received: int = Field(default=0, ge=0)
    relationships_received: int = Field(default=0, ge=0)
    nodes_written: int = Field(default=0, ge=0)
    relationships_written: int = Field(default=0, ge=0)


class GraphProjectionResponse(ProjectionModel):
    contract_version: Literal["1.0"] = "1.0"
    message_type: Literal["graph_projection_response"] = "graph_projection_response"
    projection_id: str = Field(min_length=1, max_length=160)
    project_id: str = Field(min_length=1, max_length=160)
    dataset_version_id: str = Field(min_length=1, max_length=160)
    status: ProjectionStatus
    project3_run_id: str | None = Field(default=None, max_length=160)
    projection_checksum_sha256: str | None = Field(
        default=None, pattern=SHA256_PATTERN
    )
    idempotent_replay: bool = False
    counts: GraphProjectionCounts = Field(default_factory=GraphProjectionCounts)
    error: GraphProjectionError | None = None
    updated_at: datetime

    @model_validator(mode="after")
    def error_matches_status(self) -> "GraphProjectionResponse":
        if self.status in {"failed", "blocked"} and self.error is None:
            raise ValueError("failed or blocked projection responses require an error")
        if self.status in {"accepted", "processing", "completed"} and self.error is not None:
            raise ValueError("non-error projection responses must not include an error")
        return self
