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
    "paused",
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
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    question: str
    answer: str
    status: QueryStatus
    cypher: str = ""
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)
    validation: dict[str, Any] = Field(default_factory=dict)
    usage: dict[str, Any] = Field(default_factory=dict)
    caveat: str | None = None
    provider: str = "unknown"
    fallback_reason: str | None = None
    run_id: str | None = None
    thread_id: str | None = None
    state_schema_version: int | None = None
    organization: dict[str, Any] = Field(default_factory=dict)
    user: dict[str, Any] = Field(default_factory=dict)
    project: dict[str, Any] = Field(default_factory=dict)
    run: dict[str, Any] = Field(default_factory=dict)
    routing: dict[str, Any] = Field(default_factory=dict)
    agent_schema: dict[str, Any] = Field(default_factory=dict, alias="schema")
    recommendation: dict[str, Any] = Field(default_factory=dict)
    approval: dict[str, Any] = Field(default_factory=dict)


class AgentRunStateResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    state_schema_version: int
    status: str
    run: dict[str, Any]
    checkpoint: dict[str, Any] = Field(default_factory=dict)


class HealthCheck(BaseModel):
    check: str
    status: str
    detail: str
    required: bool


class HealthResponse(BaseModel):
    status: Literal["ready", "degraded"]
    checks: list[HealthCheck]


class ErrorDetail(BaseModel):
    code: str
    category: Literal[
        "request",
        "authorization",
        "state",
        "dependency",
        "internal",
    ]
    message: str
    retryable: bool
    request_id: str


class ErrorEnvelope(BaseModel):
    detail: Any
    error: ErrorDetail


class RuntimeResponse(BaseModel):
    provider: str
    model_name: str
    transport: Literal["service"]
    active_project_id: str
    ui_load_enabled: bool


ProjectStatus = Literal[
    "draft",
    "profiling",
    "mapping_review",
    "loading",
    "validating",
    "evaluation_required",
    "ready",
    "failed",
    "archived",
]


class ProjectCreate(BaseModel):
    project_id: str = Field(min_length=3, max_length=63)
    name: str = Field(min_length=1, max_length=200)
    domain_type: str = Field(min_length=1, max_length=200)
    dataset_name: str = Field(min_length=1, max_length=200)
    schema_version: str | None = Field(default=None, max_length=80)
    status: Literal["draft"] = "draft"
    description: str = Field(default="", max_length=2000)
    industry: str = Field(default="manufacturing", min_length=1, max_length=200)
    owner: str = Field(default="", max_length=200)
    security_classification: str = Field(
        default="internal", min_length=1, max_length=80
    )
    source_type: Literal["file", "neo4j"] = "file"


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    domain_type: str | None = Field(
        default=None, min_length=1, max_length=200
    )
    dataset_name: str | None = Field(
        default=None, min_length=1, max_length=200
    )
    schema_version: str | None = Field(default=None, max_length=80)
    status: Literal["archived"] | None = None
    description: str | None = Field(default=None, max_length=2000)
    industry: str | None = Field(default=None, min_length=1, max_length=200)
    owner: str | None = Field(default=None, max_length=200)
    security_classification: str | None = Field(
        default=None, min_length=1, max_length=80
    )
    favorite: bool | None = None


class ProjectResponse(BaseModel):
    project_id: str
    name: str
    domain_type: str
    dataset_name: str
    schema_version: str | None
    status: ProjectStatus
    description: str = ""
    industry: str = "manufacturing"
    owner: str = ""
    security_classification: str = "internal"
    source_type: Literal["file", "neo4j"] = "file"
    source_version: str | None = None
    connector_id: str | None = None
    prompt_version: str | None = None
    gold_version: str | None = None
    evaluation_version: str | None = None
    favorite: bool = False
    created_at: str
    updated_at: str
    is_active: bool = False


class ProjectReadinessResponse(BaseModel):
    project_id: str
    lifecycle_status: ProjectStatus
    source_type: Literal["file", "neo4j"]
    upload_count: int
    mapping_approved: bool
    schema_available: bool
    node_count: int
    relationship_count: int
    can_query: bool
    can_load: bool
    eligible_for_ready: bool
    next_action: Literal[
        "upload",
        "connect",
        "map",
        "load",
        "validate",
        "evaluate",
        "activate",
        "query",
    ]
    checks: dict[str, dict[str, Any]]
    versions: dict[str, str | None]
    artifacts: dict[str, dict[str, Any]]
    transitions: list[dict[str, Any]]


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


class Neo4jConnectorRequest(BaseModel):
    uri: str = Field(min_length=8, max_length=500)
    database: str = Field(default="neo4j", min_length=1, max_length=100)
    username: str = Field(default="neo4j", min_length=1, max_length=100)
    password_env: str = Field(min_length=3, max_length=128)


class Neo4jConnectorResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    connector_id: str
    project_id: str
    kind: Literal["neo4j"]
    uri: str
    database: str
    username: str
    password_env: str
    status: Literal["validated", "approved"]
    schema_fingerprint: str
    counts: dict[str, int]
    validated_at: str


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
    project_id: str | None = Field(default=None, min_length=3, max_length=63)
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
