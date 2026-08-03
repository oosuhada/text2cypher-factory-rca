"""SQLite-backed project metadata and active workspace selection."""

from __future__ import annotations

from datetime import datetime, timezone
from contextlib import contextmanager
import re
import sqlite3
from pathlib import Path
from threading import RLock
from typing import Any, Iterator


PROJECT_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]{2,62}$")
PROJECT_STATUSES = {"draft", "ready", "archived"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProjectRegistry:
    def __init__(self, path: Path):
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
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
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    domain_type TEXT NOT NULL,
                    dataset_name TEXT NOT NULL,
                    schema_version TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS registry_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def _validate_project_id(project_id: str) -> str:
        normalized = project_id.strip().lower()
        if not PROJECT_ID_PATTERN.fullmatch(normalized):
            raise ValueError(
                "project_id는 영문 소문자로 시작하고 소문자·숫자·하이픈 "
                "3~63자로 구성해야 합니다."
            )
        return normalized

    @staticmethod
    def _validate_text(value: str, field: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{field}은 비어 있을 수 없습니다.")
        if len(normalized) > 200:
            raise ValueError(f"{field}은 200자를 초과할 수 없습니다.")
        return normalized

    @staticmethod
    def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        return dict(row) if row is not None else None

    def ensure_default(self) -> dict[str, Any]:
        existing = self.get("cip-dmd")
        if existing is None:
            existing = self.create(
                project_id="cip-dmd",
                name="CiP-DMD Manufacturing RCA",
                domain_type="manufacturing-process",
                dataset_name="CiP-DMD",
                schema_version="1.1",
                status="ready",
            )
        if self.active_project_id() is None:
            self.activate(existing["project_id"])
        return existing

    def create(
        self,
        *,
        project_id: str,
        name: str,
        domain_type: str,
        dataset_name: str,
        schema_version: str | None = None,
        status: str = "draft",
    ) -> dict[str, Any]:
        project_id = self._validate_project_id(project_id)
        name = self._validate_text(name, "name")
        domain_type = self._validate_text(domain_type, "domain_type")
        dataset_name = self._validate_text(dataset_name, "dataset_name")
        if status not in PROJECT_STATUSES:
            raise ValueError(f"지원하지 않는 프로젝트 상태입니다: {status}")
        timestamp = _now()
        with self._lock, self._connect() as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO projects (
                        project_id, name, domain_type, dataset_name,
                        schema_version, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        name,
                        domain_type,
                        dataset_name,
                        schema_version,
                        status,
                        timestamp,
                        timestamp,
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError(
                    f"이미 존재하는 project_id입니다: {project_id}"
                ) from error
        return self.require(project_id)

    def list(self, *, include_archived: bool = False) -> list[dict[str, Any]]:
        query = "SELECT * FROM projects"
        parameters: tuple[Any, ...] = ()
        if not include_archived:
            query += " WHERE status != ?"
            parameters = ("archived",)
        query += " ORDER BY updated_at DESC, project_id"
        active = self.active_project_id()
        with self._connect() as connection:
            rows = [dict(row) for row in connection.execute(query, parameters)]
        for row in rows:
            row["is_active"] = row["project_id"] == active
        return rows

    def get(self, project_id: str) -> dict[str, Any] | None:
        project_id = self._validate_project_id(project_id)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM projects WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        result = self._row(row)
        if result is not None:
            result["is_active"] = project_id == self.active_project_id()
        return result

    def require(self, project_id: str) -> dict[str, Any]:
        project = self.get(project_id)
        if project is None:
            raise KeyError(f"프로젝트를 찾을 수 없습니다: {project_id}")
        return project

    def update(
        self,
        project_id: str,
        *,
        name: str | None = None,
        domain_type: str | None = None,
        dataset_name: str | None = None,
        schema_version: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        project = self.require(project_id)
        values = {
            "name": (
                self._validate_text(name, "name")
                if name is not None
                else project["name"]
            ),
            "domain_type": (
                self._validate_text(domain_type, "domain_type")
                if domain_type is not None
                else project["domain_type"]
            ),
            "dataset_name": (
                self._validate_text(dataset_name, "dataset_name")
                if dataset_name is not None
                else project["dataset_name"]
            ),
            "schema_version": (
                schema_version
                if schema_version is not None
                else project["schema_version"]
            ),
            "status": status or project["status"],
        }
        if values["status"] not in PROJECT_STATUSES:
            raise ValueError(
                f"지원하지 않는 프로젝트 상태입니다: {values['status']}"
            )
        if (
            values["status"] == "archived"
            and self.active_project_id() == project_id
        ):
            raise ValueError("활성 프로젝트는 먼저 다른 프로젝트로 전환하세요.")
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE projects SET
                    name = ?, domain_type = ?, dataset_name = ?,
                    schema_version = ?, status = ?, updated_at = ?
                WHERE project_id = ?
                """,
                (
                    values["name"],
                    values["domain_type"],
                    values["dataset_name"],
                    values["schema_version"],
                    values["status"],
                    _now(),
                    project_id,
                ),
            )
        return self.require(project_id)

    def active_project_id(self) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM registry_settings WHERE key = ?",
                ("active_project_id",),
            ).fetchone()
        return str(row["value"]) if row is not None else None

    def active(self) -> dict[str, Any] | None:
        project_id = self.active_project_id()
        return self.get(project_id) if project_id else None

    def activate(self, project_id: str) -> dict[str, Any]:
        project = self.require(project_id)
        if project["status"] == "archived":
            raise ValueError("보관된 프로젝트는 활성화할 수 없습니다.")
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO registry_settings (key, value)
                VALUES ('active_project_id', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (project_id,),
            )
        return self.require(project_id)
