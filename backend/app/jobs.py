"""Persistent ingestion job state for the enterprise onboarding UI."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from threading import RLock
from typing import Any, Iterator
from uuid import uuid4


TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}
ACTIVE_STATUSES = {"queued", "running"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PipelineJobStore:
    def __init__(self, path: Path):
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS pipeline_jobs (
                    job_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    current_step TEXT NOT NULL,
                    progress INTEGER NOT NULL,
                    processed_rows INTEGER NOT NULL,
                    total_rows INTEGER,
                    attempt INTEGER NOT NULL,
                    parent_job_id TEXT,
                    message TEXT NOT NULL,
                    error TEXT,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS pipeline_job_logs (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    level TEXT NOT NULL,
                    step TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES pipeline_jobs(job_id)
                );
                """
            )

    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["result"] = json.loads(result.pop("result_json"))
        return result

    def create(
        self,
        project_id: str,
        kind: str,
        *,
        message: str,
        total_rows: int | None = None,
        parent_job_id: str | None = None,
        attempt: int = 1,
    ) -> dict[str, Any]:
        timestamp = _now()
        job_id = str(uuid4())
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO pipeline_jobs (
                    job_id, project_id, kind, status, current_step,
                    progress, processed_rows, total_rows, attempt,
                    parent_job_id, message, error, result_json,
                    created_at, started_at, finished_at, updated_at
                ) VALUES (?, ?, ?, 'queued', 'queued', 0, 0, ?, ?, ?, ?,
                          NULL, '{}', ?, NULL, NULL, ?)
                """,
                (
                    job_id,
                    project_id,
                    kind,
                    total_rows,
                    attempt,
                    parent_job_id,
                    message[:1000],
                    timestamp,
                    timestamp,
                ),
            )
        self.log(job_id, "info", "queued", message)
        return self.get(job_id)

    def get(self, job_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM pipeline_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"작업을 찾을 수 없습니다: {job_id}")
        return self._row(row)

    def list(
        self, project_id: str, *, limit: int = 20
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = list(
                connection.execute(
                    """
                    SELECT * FROM pipeline_jobs
                    WHERE project_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (project_id, max(1, min(limit, 100))),
                )
            )
        return [self._row(row) for row in rows]

    def log(
        self, job_id: str, level: str, step: str, message: str
    ) -> None:
        self.get(job_id)
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO pipeline_job_logs (
                    job_id, level, step, message, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (job_id, level, step, message[:2000], _now()),
            )

    def logs(self, job_id: str) -> list[dict[str, Any]]:
        self.get(job_id)
        with self._connect() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT level, step, message, created_at
                    FROM pipeline_job_logs
                    WHERE job_id = ?
                    ORDER BY log_id
                    """,
                    (job_id,),
                )
            ]

    def update(
        self,
        job_id: str,
        *,
        status: str | None = None,
        current_step: str | None = None,
        progress: int | None = None,
        processed_rows: int | None = None,
        total_rows: int | None = None,
        message: str | None = None,
        error: str | None = None,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        current = self.get(job_id)
        resolved_status = status or current["status"]
        if resolved_status not in ACTIVE_STATUSES | TERMINAL_STATUSES:
            raise ValueError(f"지원하지 않는 작업 상태입니다: {resolved_status}")
        if current["status"] in TERMINAL_STATUSES:
            raise ValueError("종료된 작업은 변경할 수 없습니다.")
        resolved_progress = (
            current["progress"] if progress is None else int(progress)
        )
        if not 0 <= resolved_progress <= 100:
            raise ValueError("progress는 0~100이어야 합니다.")
        timestamp = _now()
        started_at = current["started_at"]
        if resolved_status == "running" and not started_at:
            started_at = timestamp
        finished_at = (
            timestamp if resolved_status in TERMINAL_STATUSES else None
        )
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE pipeline_jobs SET
                    status = ?, current_step = ?, progress = ?,
                    processed_rows = ?, total_rows = ?, message = ?,
                    error = ?, result_json = ?, started_at = ?,
                    finished_at = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (
                    resolved_status,
                    current_step or current["current_step"],
                    resolved_progress,
                    (
                        current["processed_rows"]
                        if processed_rows is None
                        else int(processed_rows)
                    ),
                    (
                        current["total_rows"]
                        if total_rows is None
                        else int(total_rows)
                    ),
                    (message or current["message"])[:1000],
                    error,
                    json.dumps(
                        current["result"] if result is None else result,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    started_at,
                    finished_at,
                    timestamp,
                    job_id,
                ),
            )
        if message:
            self.log(
                job_id,
                "error" if resolved_status == "failed" else "info",
                current_step or current["current_step"],
                message,
            )
        return self.get(job_id)

    def start(self, job_id: str, step: str, message: str) -> dict[str, Any]:
        return self.update(
            job_id,
            status="running",
            current_step=step,
            progress=5,
            message=message,
        )

    def succeed(
        self,
        job_id: str,
        *,
        step: str,
        message: str,
        result: dict[str, Any],
        processed_rows: int = 0,
        total_rows: int | None = None,
    ) -> dict[str, Any]:
        return self.update(
            job_id,
            status="succeeded",
            current_step=step,
            progress=100,
            processed_rows=processed_rows,
            total_rows=total_rows,
            message=message,
            result=result,
        )

    def fail(
        self, job_id: str, *, step: str, error: str
    ) -> dict[str, Any]:
        return self.update(
            job_id,
            status="failed",
            current_step=step,
            message="작업이 실패했습니다.",
            error=error[:4000],
        )

    def cancel(self, job_id: str) -> dict[str, Any]:
        return self.update(
            job_id,
            status="cancelled",
            current_step="cancelled",
            message="사용자가 작업을 취소했습니다.",
        )

    def retry(self, job_id: str) -> dict[str, Any]:
        previous = self.get(job_id)
        if previous["status"] not in {"failed", "cancelled"}:
            raise ValueError("실패하거나 취소된 작업만 재시도할 수 있습니다.")
        return self.create(
            previous["project_id"],
            previous["kind"],
            message=f"{previous['kind']} 재시도",
            total_rows=previous["total_rows"],
            parent_job_id=job_id,
            attempt=int(previous["attempt"]) + 1,
        )

