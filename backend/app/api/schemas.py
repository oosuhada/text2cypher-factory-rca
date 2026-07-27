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


class SubgraphResponse(BaseModel):
    root: dict[str, Any] | None
    nodes: list[dict[str, Any]]
    relationships: list[dict[str, Any]]
    node_count: int
    relationship_count: int
    depth: int
    truncated: bool
