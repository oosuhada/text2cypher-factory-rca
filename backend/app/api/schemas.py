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


class NodeIdentity(BaseModel):
    label: str
    identity_property: str


class GraphSchemaResponse(BaseModel):
    schema_context: str
    node_identities: list[NodeIdentity]
    relationship_types: list[str]


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
