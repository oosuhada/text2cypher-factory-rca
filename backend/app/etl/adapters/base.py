"""Contracts shared by domain-specific ETL adapters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from neo4j import Driver


@dataclass
class PreparedGraph:
    project_id: str
    dataset_name: str
    payload: Any
    validation: dict[str, Any]
    source_audit: dict[str, Any]

    def summary(self) -> dict[str, Any]:
        payload_summary = (
            self.payload.summary()
            if hasattr(self.payload, "summary")
            else {}
        )
        return {
            "project_id": self.project_id,
            "dataset": self.dataset_name,
            "validation": self.validation,
            "payload": payload_summary,
            "source_audit": self.source_audit,
        }


@runtime_checkable
class EtlAdapter(Protocol):
    project_id: str
    dataset_name: str
    expected_counts: dict[str, int]

    def required_paths(self) -> tuple[str, ...]: ...

    def prepare(self, raw_root: Path) -> PreparedGraph: ...

    def load(
        self,
        driver: Driver,
        database: str,
        prepared: PreparedGraph,
        schema_path: Path,
        *,
        batch_size: int,
    ) -> dict[str, Any]: ...

    def graph_counts(
        self, driver: Driver, database: str
    ) -> dict[str, int]: ...
