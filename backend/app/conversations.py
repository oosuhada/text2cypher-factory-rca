"""Persistent project-scoped conversation history."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from threading import RLock
from typing import Any, Iterator


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ConversationStore:
    """Store UI conversations without coupling them to Streamlit sessions."""

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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    project_id TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    messages_json TEXT NOT NULL,
                    last_result_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (project_id, conversation_id)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_conversation_project_updated
                ON conversations(project_id, updated_at DESC)
                """
            )

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["id"] = result.pop("conversation_id")
        result["messages"] = json.loads(result.pop("messages_json"))
        encoded = result.pop("last_result_json")
        result["last_result"] = json.loads(encoded) if encoded else None
        return result

    def save(
        self, project_id: str, conversation: dict[str, Any]
    ) -> dict[str, Any]:
        messages = conversation.get("messages", [])
        if not isinstance(messages, list) or not messages:
            raise ValueError("비어 있는 대화는 저장할 수 없습니다.")
        conversation_id = str(conversation["id"])
        timestamp = str(conversation.get("updated_at") or _now())
        created_at = str(conversation.get("created_at") or timestamp)
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO conversations (
                    project_id, conversation_id, title, messages_json,
                    last_result_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, conversation_id) DO UPDATE SET
                    title = excluded.title,
                    messages_json = excluded.messages_json,
                    last_result_json = excluded.last_result_json,
                    updated_at = excluded.updated_at
                """,
                (
                    project_id,
                    conversation_id,
                    str(conversation.get("title") or "새 대화")[:160],
                    json.dumps(messages, ensure_ascii=False, default=str),
                    (
                        json.dumps(
                            conversation.get("last_result"),
                            ensure_ascii=False,
                            default=str,
                        )
                        if conversation.get("last_result") is not None
                        else None
                    ),
                    created_at,
                    timestamp,
                ),
            )
        return self.get(project_id, conversation_id)

    def get(
        self, project_id: str, conversation_id: str
    ) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM conversations
                WHERE project_id = ? AND conversation_id = ?
                """,
                (project_id, conversation_id),
            ).fetchone()
        if row is None:
            raise KeyError(f"대화를 찾을 수 없습니다: {conversation_id}")
        return self._decode(row)

    def list(
        self,
        project_id: str,
        *,
        search: str = "",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        normalized = search.strip()
        query = """
            SELECT * FROM conversations
            WHERE project_id = ?
        """
        parameters: list[Any] = [project_id]
        if normalized:
            query += " AND (title LIKE ? OR messages_json LIKE ?)"
            token = f"%{normalized}%"
            parameters.extend([token, token])
        query += " ORDER BY updated_at DESC LIMIT ?"
        parameters.append(max(1, min(int(limit), 100)))
        with self._connect() as connection:
            rows = list(connection.execute(query, parameters))
        return [self._decode(row) for row in rows]

    def delete(self, project_id: str, conversation_id: str) -> bool:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM conversations
                WHERE project_id = ? AND conversation_id = ?
                """,
                (project_id, conversation_id),
            )
        return cursor.rowcount > 0

    def delete_project(self, project_id: str) -> int:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM conversations WHERE project_id = ?",
                (project_id,),
            )
        return cursor.rowcount
