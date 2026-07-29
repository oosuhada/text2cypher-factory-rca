"""Versioned LangGraph state shared by current and future agent tools."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from operator import add
from typing import Annotated, Any, Literal, TypedDict, cast


AGENT_STATE_SCHEMA_VERSION = 1

AgentStatus = Literal[
    "running",
    "success",
    "empty",
    "blocked",
    "failed",
    "needs_clarification",
    "unsupported",
    "paused",
]


class OrganizationContext(TypedDict, total=False):
    organization_id: str


class UserContext(TypedDict, total=False):
    user_id: str
    roles: list[str]


class ProjectContext(TypedDict, total=False):
    project_id: str
    schema_version: str | None
    prompt_version: str | None


class RunContext(TypedDict, total=False):
    run_id: str
    thread_id: str
    checkpoint_namespace: str
    created_at: str
    updated_at: str
    status: AgentStatus


class RoutingState(TypedDict, total=False):
    status: Literal[
        "not_started",
        "explicit_project",
        "routed",
        "needs_clarification",
    ]
    selected_project_id: str | None
    confidence: float | None
    candidates: list[dict[str, Any]]
    reason: str | None


class SchemaState(TypedDict, total=False):
    project_id: str
    schema_version: str | None
    prompt_version: str | None
    context_sha256: str | None


class EvidenceState(TypedDict, total=False):
    graph: dict[str, Any]
    documents: list[dict[str, Any]]


class RecommendationState(TypedDict, total=False):
    status: Literal["not_requested", "pending", "ready", "blocked"]
    items: list[dict[str, Any]]
    caveats: list[str]


class ApprovalState(TypedDict, total=False):
    status: Literal[
        "not_required",
        "pending",
        "approved",
        "rejected",
        "expired",
        "cancelled",
    ]
    approval_id: str | None
    approval_type: str | None
    requested_at: str | None
    decided_at: str | None
    decided_by: str | None
    reason: str | None


@dataclass(frozen=True)
class RunIdentity:
    organization_id: str
    user_id: str
    project_id: str
    run_id: str
    thread_id: str
    checkpoint_namespace: str = "text2cypher"
    roles: tuple[str, ...] = ()


class AgentRunState(TypedDict, total=False):
    state_schema_version: int
    organization: OrganizationContext
    user: UserContext
    project: ProjectContext
    run: RunContext
    routing: RoutingState
    schema: SchemaState
    tool_trace: Annotated[list[dict[str, Any]], add]
    evidence: EvidenceState
    recommendation: RecommendationState
    approval: ApprovalState

    question: str
    statement: str
    errors: list[str]
    attempts: int
    max_attempts: int
    records: list[dict[str, Any]]
    status: AgentStatus
    next_action: Literal["generate", "validate", "correct", "execute", "end"]
    trace: Annotated[list[dict[str, Any]], add]
    statement_history: Annotated[list[dict[str, Any]], add]
    elapsed_ms: int
    deadline_at_epoch: float
    validated_statement_sha256: str
    metadata: dict[str, Any]


class CypherState(AgentRunState, total=False):
    """Backward-compatible name for the expanded agent run state."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _legacy_run_id(state: dict[str, Any]) -> str:
    payload = json.dumps(
        {
            "question": state.get("question", ""),
            "project_id": state.get("metadata", {}).get("project_id", "unknown"),
            "statement": state.get("statement", ""),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return f"legacy-{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:20]}"


def initial_state_sections(
    identity: RunIdentity,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = utc_now()
    merged_metadata = {
        "project_id": identity.project_id,
        "organization_id": identity.organization_id,
        "user_id": identity.user_id,
        "run_id": identity.run_id,
        "thread_id": identity.thread_id,
        **(metadata or {}),
    }
    return {
        "state_schema_version": AGENT_STATE_SCHEMA_VERSION,
        "organization": {"organization_id": identity.organization_id},
        "user": {
            "user_id": identity.user_id,
            "roles": list(identity.roles),
        },
        "project": {
            "project_id": identity.project_id,
            "schema_version": merged_metadata.get("schema_version"),
            "prompt_version": merged_metadata.get("prompt_version"),
        },
        "run": {
            "run_id": identity.run_id,
            "thread_id": identity.thread_id,
            "checkpoint_namespace": identity.checkpoint_namespace,
            "created_at": now,
            "updated_at": now,
            "status": "running",
        },
        "routing": {
            "status": "explicit_project",
            "selected_project_id": identity.project_id,
            "confidence": 1.0,
            "candidates": [],
            "reason": "project supplied by the current application context",
        },
        "schema": {
            "project_id": identity.project_id,
            "schema_version": merged_metadata.get("schema_version"),
            "prompt_version": merged_metadata.get("prompt_version"),
            "context_sha256": merged_metadata.get("schema_context_sha256"),
        },
        "tool_trace": [],
        "evidence": {
            "graph": {
                "nodes": [],
                "relationships": [],
                "node_count": 0,
                "relationship_count": 0,
            },
            "documents": [],
        },
        "recommendation": {
            "status": "not_requested",
            "items": [],
            "caveats": [],
        },
        "approval": {
            "status": "not_required",
            "approval_id": None,
            "approval_type": None,
            "requested_at": None,
            "decided_at": None,
            "decided_by": None,
            "reason": None,
        },
        "metadata": merged_metadata,
    }


def migrate_agent_state(raw_state: dict[str, Any]) -> CypherState:
    """Upgrade a persisted state snapshot to the current state contract."""
    state = deepcopy(raw_state)
    version = int(state.get("state_schema_version", 0))
    if version > AGENT_STATE_SCHEMA_VERSION:
        raise ValueError(
            "Persisted agent state is newer than this application: "
            f"{version} > {AGENT_STATE_SCHEMA_VERSION}."
        )

    if version == 0:
        metadata = dict(state.get("metadata", {}))
        project_id = str(metadata.get("project_id") or "cip-dmd")
        run_id = str(metadata.get("run_id") or _legacy_run_id(state))
        thread_id = str(metadata.get("thread_id") or run_id)
        identity = RunIdentity(
            organization_id=str(metadata.get("organization_id") or "local"),
            user_id=str(metadata.get("user_id") or "anonymous"),
            project_id=project_id,
            run_id=run_id,
            thread_id=thread_id,
            checkpoint_namespace=str(
                metadata.get("checkpoint_namespace") or "text2cypher"
            ),
            roles=tuple(metadata.get("roles") or ()),
        )
        defaults = initial_state_sections(identity, metadata)
        defaults.update(state)
        state = defaults
        state["state_schema_version"] = 1

    run = dict(state.get("run", {}))
    run.setdefault("updated_at", utc_now())
    run.setdefault("status", state.get("status", "running"))
    state["run"] = run
    state.setdefault("tool_trace", [])
    state.setdefault("evidence", {"graph": {}, "documents": []})
    state.setdefault(
        "recommendation",
        {"status": "not_requested", "items": [], "caveats": []},
    )
    state.setdefault(
        "approval",
        {
            "status": "not_required",
            "approval_id": None,
            "approval_type": None,
            "requested_at": None,
            "decided_at": None,
            "decided_by": None,
            "reason": None,
        },
    )
    return cast(CypherState, state)
