"""SQLite-backed project lifecycle, lineage, and active workspace registry."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
from threading import RLock
from typing import Any, Iterator


PROJECT_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]{2,62}$")
PROJECT_STATUSES = {
    "draft",
    "profiling",
    "mapping_review",
    "loading",
    "validating",
    "evaluation_required",
    "ready",
    "failed",
    "archived",
}
STATUS_MIGRATIONS = {
    "mapping_ready": "mapping_review",
    "load_failed": "failed",
}
ALLOWED_TRANSITIONS = {
    "draft": {"profiling", "archived"},
    "profiling": {"mapping_review", "failed", "archived"},
    "mapping_review": {"loading", "profiling", "failed", "archived"},
    "loading": {"validating", "failed", "archived"},
    "validating": {"evaluation_required", "failed", "archived"},
    "evaluation_required": {"ready", "profiling", "failed", "archived"},
    "ready": {"profiling", "evaluation_required", "archived"},
    "failed": {
        "draft",
        "profiling",
        "mapping_review",
        "loading",
        "validating",
        "evaluation_required",
        "archived",
    },
    "archived": set(),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProjectRegistry:
    """Persist project metadata without allowing readiness bypasses."""

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

    @staticmethod
    def _add_column(
        connection: sqlite3.Connection,
        table: str,
        name: str,
        declaration: str,
    ) -> None:
        columns = {
            row["name"]
            for row in connection.execute(f"PRAGMA table_info({table})")
        }
        if name not in columns:
            connection.execute(
                f"ALTER TABLE {table} ADD COLUMN {name} {declaration}"
            )

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
                CREATE TABLE IF NOT EXISTS project_transitions (
                    transition_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    from_status TEXT,
                    to_status TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(project_id)
                );
                CREATE TABLE IF NOT EXISTS project_artifacts (
                    project_id TEXT NOT NULL,
                    artifact_type TEXT NOT NULL,
                    version TEXT NOT NULL,
                    status TEXT NOT NULL,
                    fingerprint TEXT,
                    metadata_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(project_id, artifact_type),
                    FOREIGN KEY(project_id) REFERENCES projects(project_id)
                );
                """
            )
            for name, declaration in (
                ("description", "TEXT NOT NULL DEFAULT ''"),
                ("industry", "TEXT NOT NULL DEFAULT 'manufacturing'"),
                ("owner", "TEXT NOT NULL DEFAULT ''"),
                (
                    "security_classification",
                    "TEXT NOT NULL DEFAULT 'internal'",
                ),
                ("source_type", "TEXT NOT NULL DEFAULT 'file'"),
                ("source_version", "TEXT"),
                ("connector_id", "TEXT"),
                ("prompt_version", "TEXT"),
                ("gold_version", "TEXT"),
                ("evaluation_version", "TEXT"),
                ("favorite", "INTEGER NOT NULL DEFAULT 0"),
            ):
                self._add_column(connection, "projects", name, declaration)
            for old, new in STATUS_MIGRATIONS.items():
                connection.execute(
                    "UPDATE projects SET status = ? WHERE status = ?",
                    (new, old),
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
    def _validate_text(
        value: str,
        field: str,
        *,
        maximum: int = 200,
        allow_empty: bool = False,
    ) -> str:
        normalized = value.strip()
        if not allow_empty and not normalized:
            raise ValueError(f"{field}은 비어 있을 수 없습니다.")
        if len(normalized) > maximum:
            raise ValueError(f"{field}은 {maximum}자를 초과할 수 없습니다.")
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
                source_type="file",
                source_version="CiP-DMD public release",
                status="ready",
                _bootstrap=True,
            )
        elif (
            existing.get("source_version") != "CiP-DMD public release"
            or existing.get("schema_version") != "1.1"
        ):
            existing = self.update(
                "cip-dmd",
                schema_version="1.1",
                source_type="file",
                source_version="CiP-DMD public release",
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
        description: str = "",
        industry: str = "manufacturing",
        owner: str = "",
        security_classification: str = "internal",
        source_type: str = "file",
        source_version: str | None = None,
        connector_id: str | None = None,
        favorite: bool = False,
        _bootstrap: bool = False,
    ) -> dict[str, Any]:
        project_id = self._validate_project_id(project_id)
        name = self._validate_text(name, "name")
        domain_type = self._validate_text(domain_type, "domain_type")
        dataset_name = self._validate_text(dataset_name, "dataset_name")
        description = self._validate_text(
            description, "description", maximum=2000, allow_empty=True
        )
        industry = self._validate_text(industry, "industry")
        owner = self._validate_text(
            owner, "owner", maximum=200, allow_empty=True
        )
        security_classification = self._validate_text(
            security_classification, "security_classification"
        )
        if source_type not in {"file", "neo4j"}:
            raise ValueError("source_type은 file 또는 neo4j여야 합니다.")
        if status not in PROJECT_STATUSES:
            raise ValueError(f"지원하지 않는 프로젝트 상태입니다: {status}")
        if status != "draft" and not _bootstrap:
            raise ValueError(
                "새 프로젝트는 draft 상태로만 생성할 수 있습니다."
            )
        timestamp = _now()
        with self._lock, self._connect() as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO projects (
                        project_id, name, domain_type, dataset_name,
                        schema_version, status, created_at, updated_at,
                        description, industry, owner,
                        security_classification, source_type,
                        source_version, connector_id, favorite
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        description,
                        industry,
                        owner,
                        security_classification,
                        source_type,
                        source_version,
                        connector_id,
                        int(favorite),
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO project_transitions (
                        project_id, from_status, to_status, reason, created_at
                    ) VALUES (?, NULL, ?, ?, ?)
                    """,
                    (
                        project_id,
                        status,
                        "bootstrap" if _bootstrap else "project_created",
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
        description: str | None = None,
        industry: str | None = None,
        owner: str | None = None,
        security_classification: str | None = None,
        source_type: str | None = None,
        source_version: str | None = None,
        connector_id: str | None = None,
        prompt_version: str | None = None,
        gold_version: str | None = None,
        evaluation_version: str | None = None,
        favorite: bool | None = None,
        status: str | None = None,
        transition_reason: str = "metadata_update",
    ) -> dict[str, Any]:
        project = self.require(project_id)
        metadata_changes = (
            name,
            domain_type,
            dataset_name,
            schema_version,
            description,
            industry,
            owner,
            security_classification,
            source_type,
            source_version,
            connector_id,
            prompt_version,
            gold_version,
            evaluation_version,
            favorite,
        )
        if status is not None and any(
            value is not None for value in metadata_changes
        ):
            raise ValueError(
                "상태 전이와 metadata 수정은 한 요청에서 함께 할 수 없습니다."
            )
        if status is not None and status != project["status"]:
            return self.transition(
                project_id, status, reason=transition_reason
            )
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
            "description": (
                self._validate_text(
                    description,
                    "description",
                    maximum=2000,
                    allow_empty=True,
                )
                if description is not None
                else project["description"]
            ),
            "industry": (
                self._validate_text(industry, "industry")
                if industry is not None
                else project["industry"]
            ),
            "owner": (
                self._validate_text(owner, "owner", allow_empty=True)
                if owner is not None
                else project["owner"]
            ),
            "security_classification": (
                self._validate_text(
                    security_classification,
                    "security_classification",
                )
                if security_classification is not None
                else project["security_classification"]
            ),
            "source_type": (
                source_type
                if source_type is not None
                else project["source_type"]
            ),
            "source_version": (
                source_version
                if source_version is not None
                else project["source_version"]
            ),
            "connector_id": (
                connector_id
                if connector_id is not None
                else project["connector_id"]
            ),
            "prompt_version": (
                prompt_version
                if prompt_version is not None
                else project["prompt_version"]
            ),
            "gold_version": (
                gold_version
                if gold_version is not None
                else project["gold_version"]
            ),
            "evaluation_version": (
                evaluation_version
                if evaluation_version is not None
                else project["evaluation_version"]
            ),
            "favorite": (
                int(favorite)
                if favorite is not None
                else int(project.get("favorite", 0))
            ),
        }
        if values["source_type"] not in {"file", "neo4j"}:
            raise ValueError("source_type은 file 또는 neo4j여야 합니다.")
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE projects SET
                    name = ?, domain_type = ?, dataset_name = ?,
                    schema_version = ?, description = ?, industry = ?,
                    owner = ?, security_classification = ?, source_type = ?,
                    source_version = ?, connector_id = ?, prompt_version = ?,
                    gold_version = ?, evaluation_version = ?, favorite = ?,
                    updated_at = ?
                WHERE project_id = ?
                """,
                (
                    *values.values(),
                    _now(),
                    project_id,
                ),
            )
        return self.require(project_id)

    def transition(
        self,
        project_id: str,
        target: str,
        *,
        reason: str,
    ) -> dict[str, Any]:
        project = self.require(project_id)
        target = STATUS_MIGRATIONS.get(target, target)
        if target not in PROJECT_STATUSES:
            raise ValueError(f"지원하지 않는 프로젝트 상태입니다: {target}")
        current = project["status"]
        if current == target:
            return project
        if target not in ALLOWED_TRANSITIONS[current]:
            raise ValueError(
                f"허용되지 않는 상태 전이입니다: {current} → {target}"
            )
        if target == "archived" and self.active_project_id() == project_id:
            raise ValueError("활성 프로젝트는 먼저 다른 프로젝트로 전환하세요.")
        timestamp = _now()
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "UPDATE projects SET status = ?, updated_at = ? "
                "WHERE project_id = ? AND status = ?",
                (target, timestamp, project_id, current),
            )
            if cursor.rowcount != 1:
                raise RuntimeError(
                    "동시에 상태가 변경되었습니다. 최신 상태에서 다시 시도하세요."
                )
            connection.execute(
                """
                INSERT INTO project_transitions (
                    project_id, from_status, to_status, reason, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (project_id, current, target, reason[:500], timestamp),
            )
        return self.require(project_id)

    def transition_history(self, project_id: str) -> list[dict[str, Any]]:
        self.require(project_id)
        with self._connect() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT from_status, to_status, reason, created_at
                    FROM project_transitions
                    WHERE project_id = ?
                    ORDER BY transition_id
                    """,
                    (project_id,),
                )
            ]

    def record_artifact(
        self,
        project_id: str,
        artifact_type: str,
        *,
        version: str,
        status: str = "verified",
        fingerprint: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.require(project_id)
        artifact_type = self._validate_text(artifact_type, "artifact_type")
        version = self._validate_text(version, "version")
        timestamp = _now()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO project_artifacts (
                    project_id, artifact_type, version, status,
                    fingerprint, metadata_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, artifact_type) DO UPDATE SET
                    version = excluded.version,
                    status = excluded.status,
                    fingerprint = excluded.fingerprint,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    project_id,
                    artifact_type,
                    version,
                    status,
                    fingerprint,
                    json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True),
                    timestamp,
                ),
            )
        return self.artifacts(project_id)[artifact_type]

    def artifacts(self, project_id: str) -> dict[str, dict[str, Any]]:
        self.require(project_id)
        with self._connect() as connection:
            rows = list(
                connection.execute(
                    """
                    SELECT artifact_type, version, status, fingerprint,
                           metadata_json, updated_at
                    FROM project_artifacts
                    WHERE project_id = ?
                    ORDER BY artifact_type
                    """,
                    (project_id,),
                )
            )
        return {
            row["artifact_type"]: {
                "artifact_type": row["artifact_type"],
                "version": row["version"],
                "status": row["status"],
                "fingerprint": row["fingerprint"],
                "metadata": json.loads(row["metadata_json"]),
                "updated_at": row["updated_at"],
            }
            for row in rows
        }

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
