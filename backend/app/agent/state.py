"""State shared by the Text-to-Cypher LangGraph nodes."""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, Literal, TypedDict


AgentStatus = Literal[
    "running",
    "success",
    "empty",
    "blocked",
    "failed",
    "needs_clarification",
    "unsupported",
]


class CypherState(TypedDict, total=False):
    question: str
    statement: str
    errors: list[str]
    attempts: int
    max_attempts: int
    records: list[dict[str, Any]]
    status: AgentStatus
    next_action: Literal["validate", "correct", "execute", "end"]
    trace: Annotated[list[dict[str, Any]], add]
    statement_history: Annotated[list[dict[str, Any]], add]
    elapsed_ms: int
    deadline_monotonic: float
    validated_statement_sha256: str
    metadata: dict[str, Any]
