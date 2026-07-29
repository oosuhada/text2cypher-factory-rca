"""Persistent LangGraph checkpoint backends for resumable agent runs."""

from __future__ import annotations

import os
from pathlib import Path
import sqlite3
from threading import Lock
from typing import Any, Literal

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver

from .state import RunIdentity


CheckpointBackend = Literal["disabled", "memory", "sqlite"]


class RunCheckpointStore:
    """Own a checkpointer and its database lifecycle."""

    def __init__(
        self,
        saver: BaseCheckpointSaver[Any] | None,
        *,
        backend: CheckpointBackend,
        path: Path | None = None,
        connection: sqlite3.Connection | None = None,
    ):
        self.saver = saver
        self.backend = backend
        self.path = path
        self._connection = connection
        self._close_lock = Lock()
        self._closed = False

    @classmethod
    def disabled(cls) -> "RunCheckpointStore":
        return cls(None, backend="disabled")

    @classmethod
    def memory(cls) -> "RunCheckpointStore":
        return cls(InMemorySaver(), backend="memory")

    @classmethod
    def sqlite(cls, path: Path) -> "RunCheckpointStore":
        os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")
        resolved = path.expanduser().resolve()
        resolved.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(
            resolved,
            check_same_thread=False,
            timeout=30.0,
        )
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute("PRAGMA busy_timeout=30000")
        saver = SqliteSaver(connection)
        return cls(
            saver,
            backend="sqlite",
            path=resolved,
            connection=connection,
        )

    def close(self) -> None:
        with self._close_lock:
            if self._closed:
                return
            self._closed = True
            if self._connection is not None:
                self._connection.close()

    def delete_thread(self, thread_id: str) -> None:
        if self.saver is None:
            return
        self.saver.delete_thread(thread_id)

    def describe(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "path": str(self.path) if self.path else None,
            "persistent": self.backend == "sqlite",
        }


def checkpoint_config(identity: RunIdentity) -> dict[str, dict[str, str]]:
    # checkpoint_ns is reserved by LangGraph for subgraph traversal. Application
    # namespaces are encoded in thread_id instead and retained in run metadata.
    return {"configurable": {"thread_id": identity.thread_id}}


def build_checkpoint_store(
    project_root: Path,
    project_id: str,
    *,
    backend: str | None = None,
) -> RunCheckpointStore:
    resolved_backend = (
        backend
        or os.getenv("P3_LANGGRAPH_CHECKPOINT_BACKEND", "sqlite")
    ).strip().lower()
    if resolved_backend in {"disabled", "none", "off"}:
        return RunCheckpointStore.disabled()
    if resolved_backend == "memory":
        return RunCheckpointStore.memory()
    if resolved_backend != "sqlite":
        raise ValueError(
            "P3_LANGGRAPH_CHECKPOINT_BACKEND must be one of "
            "disabled, memory, sqlite."
        )

    override = os.getenv("P3_LANGGRAPH_CHECKPOINT_PATH")
    path = (
        Path(override)
        if override
        else project_root
        / "data"
        / "processed"
        / "projects"
        / project_id
        / "langgraph"
        / "checkpoints.sqlite3"
    )
    return RunCheckpointStore.sqlite(path)
