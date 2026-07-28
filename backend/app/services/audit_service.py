"""Project-scoped, redacted operational audit timeline."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from backend.app.jobs import PipelineJobStore

from .dashboard_service import load_query_audit


QUERY_FIELDS = (
    "run_id",
    "timestamp",
    "question",
    "cypher",
    "provider",
    "model_name",
    "project_id",
    "schema_version",
    "prompt_version",
    "status",
    "row_count",
    "attempts",
    "elapsed_ms",
    "corrected",
    "evidence_node_count",
    "evidence_relationship_count",
    "error_count",
    "execution_verified",
    "call_count",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "model_elapsed_ms",
    "estimated_cost_usd",
)


def _stable_id(prefix: str, *parts: object) -> str:
    digest = sha256(
        "|".join(str(part) for part in parts).encode("utf-8")
    ).hexdigest()[:20]
    return f"{prefix}-{digest}"


def redact_query_event(
    event: dict[str, Any], project_id: str
) -> dict[str, Any]:
    """Use an explicit allowlist so prompts, headers and credentials cannot leak."""

    safe = {key: event.get(key) for key in QUERY_FIELDS if key in event}
    safe["project_id"] = str(event.get("project_id") or project_id)
    safe["run_id"] = str(
        event.get("run_id")
        or _stable_id(
            "query",
            safe.get("timestamp"),
            safe.get("question"),
            safe["project_id"],
        )
    )
    safe["event_type"] = "query"
    safe["title"] = str(safe.get("question") or "자연어 질의")
    return safe


class AuditService:
    def __init__(self, project_root: Path):
        self.project_root = project_root.resolve()
        self.processed_root = self.project_root / "data" / "processed"
        self.jobs = PipelineJobStore(
            self.processed_root / "pipeline_jobs.sqlite3"
        )

    def _audit_path(self, project_id: str) -> Path:
        if project_id == "cip-dmd":
            return self.processed_root / "query_audit.jsonl"
        return (
            self.processed_root
            / "projects"
            / project_id
            / "query_audit.jsonl"
        )

    def _query_events(self, project_id: str) -> list[dict[str, Any]]:
        return [
            redact_query_event(event, project_id)
            for event in load_query_audit(self._audit_path(project_id))
            if str(event.get("project_id") or project_id) == project_id
        ]

    def _pipeline_events(self, project_id: str) -> list[dict[str, Any]]:
        return [
            {
                "run_id": job["job_id"],
                "event_type": "etl",
                "project_id": project_id,
                "timestamp": (
                    job.get("finished_at")
                    or job.get("updated_at")
                    or job.get("created_at")
                ),
                "title": job.get("kind", "pipeline job"),
                "status": job.get("status"),
                "step": job.get("current_step"),
                "progress": job.get("progress"),
                "processed_rows": job.get("processed_rows"),
                "total_rows": job.get("total_rows"),
                "attempt": job.get("attempt"),
                "message": job.get("message"),
                "error": job.get("error"),
                "logs": self.jobs.logs(job["job_id"]),
            }
            for job in self.jobs.list(project_id, limit=100)
        ]

    def _legacy_etl_events(
        self, project_id: str
    ) -> list[dict[str, Any]]:
        if project_id != "cip-dmd":
            return []
        events = []
        for path in sorted(
            (self.processed_root / "etl_runs").glob("etl_*.json")
        ):
            try:
                report = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            events.append(
                {
                    "run_id": f"etl-{path.stem.removeprefix('etl_')}",
                    "event_type": "etl",
                    "project_id": project_id,
                    "timestamp": (
                        report.get("finished_at")
                        or report.get("started_at")
                    ),
                    "title": f"CiP-DMD ETL · {report.get('mode')}",
                    "status": report.get("status"),
                    "mode": report.get("mode"),
                    "schema_version": (
                        report.get("payload") or {}
                    ).get("schema_version"),
                    "counts": (
                        report.get("validation") or {}
                    ).get("counts", {}),
                    "quarantined_count": (
                        report.get("validation") or {}
                    ).get("quarantined_count", 0),
                    "idempotency": report.get("idempotency"),
                }
            )
        return events[-100:]

    def _evaluation_events(
        self, project_id: str
    ) -> list[dict[str, Any]]:
        if project_id != "cip-dmd":
            return []
        path = self.project_root / "evaluation" / "results" / "latest.json"
        if not path.exists():
            return []
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        fingerprint = str(
            report.get("evaluation_fingerprint") or path.stat().st_mtime_ns
        )
        return [
            {
                "run_id": f"evaluation-{fingerprint[:20]}",
                "event_type": "evaluation",
                "project_id": project_id,
                "timestamp": report.get("evaluated_at"),
                "title": "Blind Text-to-Cypher 평가",
                "status": "complete",
                "provider": report.get("provider"),
                "model_name": report.get("model"),
                "schema_version": report.get("schema_version"),
                "prompt_version": report.get("prompt_version"),
                "evaluation_version": report.get("evaluation_version"),
                "question_count": report.get("question_count"),
                "comparison": report.get("comparison", []),
                "total_usage": report.get("total_usage", {}),
            }
        ]

    def events(
        self,
        project_id: str,
        *,
        event_type: str | None = None,
        search: str = "",
        limit: int = 300,
    ) -> list[dict[str, Any]]:
        events = [
            *self._query_events(project_id),
            *self._pipeline_events(project_id),
            *self._legacy_etl_events(project_id),
            *self._evaluation_events(project_id),
        ]
        if event_type:
            events = [
                event
                for event in events
                if event.get("event_type") == event_type
            ]
        normalized = search.strip().casefold()
        if normalized:
            events = [
                event
                for event in events
                if normalized
                in " ".join(
                    str(event.get(key, ""))
                    for key in ("run_id", "title", "status", "question")
                ).casefold()
            ]
        events.sort(
            key=lambda event: str(event.get("timestamp") or ""),
            reverse=True,
        )
        return events[: max(1, min(int(limit), 1000))]

    def run(self, project_id: str, run_id: str) -> dict[str, Any]:
        for event in self.events(project_id, limit=1000):
            if event["run_id"] == run_id:
                return event
        raise KeyError(f"감사 실행을 찾을 수 없습니다: {run_id}")
