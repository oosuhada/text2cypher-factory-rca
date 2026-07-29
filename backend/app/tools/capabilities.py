"""Built-in project-scoped tools registered by the service bundle."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field

from backend.app.projects import ProjectRegistry
from backend.app.schema_registry import SchemaRegistry

from .registry import ToolContext, ToolRegistry, ToolSpec


class GraphQueryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=4000)
    routing_state: dict[str, Any] = Field(default_factory=dict)


class QueryToolOutput(BaseModel):
    model_config = ConfigDict(extra="allow")

    question: str
    status: str
    answer: str
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    validation: dict[str, Any] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)


class SchemaLookupInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include_properties: bool = True
    include_scenarios: bool = True


class SchemaLookupOutput(BaseModel):
    project_id: str
    version: str
    title: str
    node_labels: list[str]
    relationship_types: list[str]
    properties: dict[str, list[str]] = Field(default_factory=dict)
    query_scenarios: list[dict[str, Any]] = Field(default_factory=list)


class EtlStatusInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include_artifacts: bool = True


class EtlStatusOutput(BaseModel):
    project_id: str
    status: str
    source_type: str
    source_version: str | None = None
    schema_version: str | None = None
    artifacts: dict[str, Any] = Field(default_factory=dict)


class EvaluationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include_failures: bool = False


class EvaluationOutput(BaseModel):
    project_id: str
    available: bool
    evaluation_version: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    failures: list[dict[str, Any]] = Field(default_factory=list)


class SearchDocsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=20)
    current_only: bool = True
    document_types: list[str] = Field(default_factory=list)


class SearchDocsOutput(BaseModel):
    project_id: str
    query: str
    status: str
    answer: str
    framework: str
    framework_version: str
    index_version: str
    top_k: int
    matches: list[dict[str, Any]] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)


def _metrics_path(project_root: Path, project_id: str) -> Path | None:
    candidates = [
        project_root
        / "evaluation"
        / "projects"
        / project_id
        / "metrics.json",
    ]
    if project_id == "cip-dmd":
        candidates.append(project_root / "evaluation" / "metrics.json")
    return next((path for path in candidates if path.exists()), None)


def build_project_tool_registry(
    *,
    project_root: Path,
    project_id: str,
    graph_query_handler: Callable[[GraphQueryInput, ToolContext], dict[str, Any]],
    search_docs_handler: Callable[[SearchDocsInput, ToolContext], dict[str, Any]] | None,
    audit_log_path: Path,
    graph_timeout_seconds: float,
) -> ToolRegistry:
    registry = ToolRegistry(audit_log_path=audit_log_path)
    schemas = SchemaRegistry(project_root / "schemas")
    projects = ProjectRegistry(
        project_root / "data" / "processed" / "projects.sqlite3"
    )

    def schema_lookup(
        payload: SchemaLookupInput,
        context: ToolContext,
    ) -> dict[str, Any]:
        manifest = schemas.load(context.project_id)
        properties = (
            {
                str(node["label"]): sorted(
                    str(name) for name in (node.get("properties") or {})
                )
                for node in manifest.get("nodes", [])
            }
            if payload.include_properties
            else {}
        )
        scenarios = (
            [dict(item) for item in manifest.get("query_scenarios", [])]
            if payload.include_scenarios
            else []
        )
        return {
            "project_id": context.project_id,
            "version": str(manifest["version"]),
            "title": str(manifest.get("title", context.project_id)),
            "node_labels": [
                str(node["label"]) for node in manifest.get("nodes", [])
            ],
            "relationship_types": [
                str(relationship["type"])
                for relationship in manifest.get("relationships", [])
            ],
            "properties": properties,
            "query_scenarios": scenarios,
        }

    def etl_status(
        payload: EtlStatusInput,
        context: ToolContext,
    ) -> dict[str, Any]:
        project = projects.require(context.project_id)
        artifacts = (
            projects.artifacts(context.project_id)
            if payload.include_artifacts
            else {}
        )
        return {
            "project_id": context.project_id,
            "status": str(project["status"]),
            "source_type": str(project["source_type"]),
            "source_version": project.get("source_version"),
            "schema_version": project.get("schema_version"),
            "artifacts": artifacts,
        }

    def evaluation(
        payload: EvaluationInput,
        context: ToolContext,
    ) -> dict[str, Any]:
        path = _metrics_path(project_root, context.project_id)
        if path is None:
            return {
                "project_id": context.project_id,
                "available": False,
                "evaluation_version": None,
                "metrics": {},
                "failures": [],
            }
        document = json.loads(path.read_text(encoding="utf-8"))
        failures = document.get("failures", []) if payload.include_failures else []
        metrics = document.get("metrics", document)
        return {
            "project_id": context.project_id,
            "available": True,
            "evaluation_version": document.get("evaluation_version"),
            "metrics": metrics if isinstance(metrics, dict) else {},
            "failures": failures if isinstance(failures, list) else [],
        }

    registry.register(
        ToolSpec(
            name="graph_query_tool",
            description="Generate, validate and execute a read-only project graph query.",
            input_model=GraphQueryInput,
            output_model=QueryToolOutput,
            handler=graph_query_handler,
            timeout_seconds=graph_timeout_seconds,
            max_retries=0,
        )
    )
    registry.register(
        ToolSpec(
            name="rca_query_tool",
            description="Run the existing evidence-first manufacturing RCA graph query path.",
            input_model=GraphQueryInput,
            output_model=QueryToolOutput,
            handler=graph_query_handler,
            timeout_seconds=graph_timeout_seconds,
            max_retries=0,
        )
    )
    registry.register(
        ToolSpec(
            name="schema_lookup_tool",
            description="Read the versioned project graph schema summary.",
            input_model=SchemaLookupInput,
            output_model=SchemaLookupOutput,
            handler=schema_lookup,
            timeout_seconds=5.0,
        )
    )
    registry.register(
        ToolSpec(
            name="etl_status_tool",
            description="Inspect project lifecycle and ETL artifact status.",
            input_model=EtlStatusInput,
            output_model=EtlStatusOutput,
            handler=etl_status,
            allowed_roles=frozenset({"Data Steward", "Admin"}),
            timeout_seconds=5.0,
        )
    )
    if search_docs_handler is not None:
        registry.register(
            ToolSpec(
                name="search_docs_tool",
                description="Search project documents with LlamaIndex and return source citations.",
                input_model=SearchDocsInput,
                output_model=SearchDocsOutput,
                handler=search_docs_handler,
                timeout_seconds=15.0,
                max_retries=0,
            )
        )
    registry.register(
        ToolSpec(
            name="evaluation_tool",
            description="Read the latest project evaluation metrics and failures.",
            input_model=EvaluationInput,
            output_model=EvaluationOutput,
            handler=evaluation,
            allowed_roles=frozenset(
                {"Analyst", "Domain Expert", "Data Steward", "Admin"}
            ),
            timeout_seconds=5.0,
        )
    )
    return registry
