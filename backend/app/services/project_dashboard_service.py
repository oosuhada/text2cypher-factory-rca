"""Project-scoped operational metrics for reusable graph schemas."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from neo4j import Driver, READ_ACCESS

from .dashboard_service import (
    filter_runtime_events,
    load_query_audit,
    summarize_runtime,
)


class ProjectDashboardService:
    """Return metrics without leaking nodes from another project."""

    def __init__(
        self,
        driver: Driver,
        database: str,
        project_id: str,
        audit_log_path: Path,
    ):
        self.driver = driver
        self.database = database
        self.project_id = project_id
        self.audit_log_path = audit_log_path

    def _query(self, cypher: str) -> list[dict[str, Any]]:
        with self.driver.session(
            database=self.database,
            default_access_mode=READ_ACCESS,
        ) as session:
            return [
                dict(record)
                for record in session.run(
                    cypher,
                    project_id=self.project_id,
                )
            ]

    def snapshot(
        self, runtime_filters: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        totals = self._query(
            """
            MATCH (node {project_id: $project_id})
            WITH count(node) AS nodes
            OPTIONAL MATCH (source {project_id: $project_id})
              -[relationship]->(target {project_id: $project_id})
            RETURN nodes, count(relationship) AS relationships
            """
        )[0]
        node_counts = self._query(
            """
            MATCH (node {project_id: $project_id})
            UNWIND labels(node) AS label
            RETURN label, count(node) AS count
            ORDER BY label
            """
        )
        relationship_counts = self._query(
            """
            MATCH (source {project_id: $project_id})
              -[relationship]->(target {project_id: $project_id})
            RETURN type(relationship) AS relationship_type,
                   count(relationship) AS count
            ORDER BY count DESC, relationship_type
            """
        )
        all_events = load_query_audit(self.audit_log_path)
        runtime_filters = runtime_filters or {}
        scoped_events = filter_runtime_events(
            all_events,
            providers=runtime_filters.get("providers"),
            statuses=runtime_filters.get("statuses"),
            days=runtime_filters.get("days"),
            project_id=self.project_id,
        )
        return {
            "project_id": self.project_id,
            "totals": totals,
            "node_counts": node_counts,
            "relationship_counts": relationship_counts,
            "equipment_runs": [],
            "anomaly_runs": [],
            "quality_failures": [],
            "integrity": {
                "project_scoped": True,
                "orphan_process_runs": None,
                "orphan_measurements": None,
                "quality_failure_count": None,
            },
            "evaluation": {},
            "blind_evaluation": None,
            "status_evaluation": None,
            "etl": None,
            "runtime": summarize_runtime(scoped_events),
            "runtime_scope": {
                "providers": runtime_filters.get("providers") or [],
                "statuses": runtime_filters.get("statuses") or [],
                "days": runtime_filters.get("days"),
                "source_event_count": len(all_events),
                "filtered_event_count": len(scoped_events),
            },
            "provenance": {
                "graph_project_id": self.project_id,
                "metrics_file": None,
                "metrics_sha256": None,
                "audit_file": self.audit_log_path.name,
                "audit_event_count": len(all_events),
            },
        }
