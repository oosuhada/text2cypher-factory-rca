"""Versioned HTTP request and response contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


QueryStatus = Literal[
    "success",
    "empty",
    "blocked",
    "failed",
    "needs_clarification",
    "unsupported",
]


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    project_id: str | None = Field(default=None, min_length=3, max_length=63)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("question은 공백일 수 없습니다.")
        return normalized


class QueryResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    question: str
    answer: str
    status: QueryStatus
    cypher: str = ""
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    evidence: dict[str, Any] = Field(default_factory=dict)
    validation: dict[str, Any] = Field(default_factory=dict)
    usage: dict[str, Any] = Field(default_factory=dict)
    caveat: str | None = None
    provider: str = "unknown"
    fallback_reason: str | None = None


class HealthCheck(BaseModel):
    check: str
    status: str
    detail: str
    required: bool


class HealthResponse(BaseModel):
    status: Literal["ready", "degraded"]
    checks: list[HealthCheck]


class RuntimeResponse(BaseModel):
    provider: str
    model_name: str
    transport: Literal["service"]
    active_project_id: str


ProjectStatus = Literal["draft", "ready", "archived"]


class ProjectCreate(BaseModel):
    project_id: str = Field(min_length=3, max_length=63)
    name: str = Field(min_length=1, max_length=200)
    domain_type: str = Field(min_length=1, max_length=200)
    dataset_name: str = Field(min_length=1, max_length=200)
    schema_version: str | None = Field(default=None, max_length=80)
    status: ProjectStatus = "draft"


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    domain_type: str | None = Field(
        default=None, min_length=1, max_length=200
    )
    dataset_name: str | None = Field(
        default=None, min_length=1, max_length=200
    )
    schema_version: str | None = Field(default=None, max_length=80)
    status: ProjectStatus | None = None


class ProjectResponse(BaseModel):
    project_id: str
    name: str
    domain_type: str
    dataset_name: str
    schema_version: str | None
    status: ProjectStatus
    created_at: str
    updated_at: str
    is_active: bool = False


class UploadFilePayload(BaseModel):
    filename: str = Field(min_length=1, max_length=160)
    content_base64: str = Field(min_length=1)


class DatasetUploadRequest(BaseModel):
    files: list[UploadFilePayload] = Field(min_length=1, max_length=10)


class GraphMappingRequest(BaseModel):
    upload_id: str = Field(min_length=36, max_length=36)
    schema_version: str = Field(default="1.0", min_length=1, max_length=80)
    mapping: dict[str, Any]


class ProjectLoadRequest(BaseModel):
    upload_id: str = Field(min_length=36, max_length=36)
    confirm_project_id: str = Field(min_length=3, max_length=63)


class NodeIdentity(BaseModel):
    label: str
    identity_property: str


class GraphSchemaResponse(BaseModel):
    project_id: str = "cip-dmd"
    schema_version: str = "1.1"
    title: str = "Manufacturing graph"
    schema_context: str
    node_identities: list[NodeIdentity]
    relationship_types: list[str]
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    relationships: list[dict[str, Any]] = Field(default_factory=list)


class NodeSearchResponse(BaseModel):
    label: str
    query: str
    identity_property: str
    nodes: list[dict[str, Any]]
    count: int


FeedbackDecision = Literal["verified", "disputed", "needs_followup"]


class FeedbackRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    cypher: str = Field(default="", max_length=20_000)
    query_status: str = Field(default="unknown", max_length=80)
    provider: str = Field(default="unknown", max_length=120)
    row_count: int = Field(default=0, ge=0)
    decision: FeedbackDecision
    reviewer: str = Field(default="domain-expert", max_length=120)
    note: str = Field(default="", max_length=2000)

    @field_validator("question")
    @classmethod
    def normalize_feedback_question(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("question은 공백일 수 없습니다.")
        return normalized


class FeedbackRecord(BaseModel):
    review_id: str
    timestamp: str
    query_fingerprint: str
    question: str
    cypher: str
    query_status: str
    provider: str
    row_count: int
    decision: FeedbackDecision
    reviewer: str
    note: str


class FeedbackSummary(BaseModel):
    total_reviews: int
    unique_queries_reviewed: int
    decision_counts: dict[str, int]
    recent: list[FeedbackRecord]
    storage: str


class SubgraphResponse(BaseModel):
    root: dict[str, Any] | None
    nodes: list[dict[str, Any]]
    relationships: list[dict[str, Any]]
    node_count: int
    relationship_count: int
    depth: int
    truncated: bool
