"""Project-aware orchestration over domain ETL adapters."""

from __future__ import annotations

from pathlib import Path

from neo4j import Driver

from .adapters import EtlAdapter, PreparedGraph


class EtlPipeline:
    def __init__(self, adapter: EtlAdapter, schema_path: Path):
        self.adapter = adapter
        self.schema_path = schema_path

    def dry_run(self, raw_root: Path) -> PreparedGraph:
        return self.adapter.prepare(raw_root)

    def load(
        self,
        driver: Driver,
        database: str,
        prepared: PreparedGraph,
        *,
        batch_size: int = 500,
    ) -> dict:
        if batch_size < 1:
            raise ValueError("batch_size는 1 이상이어야 합니다.")
        return self.adapter.load(
            driver,
            database,
            prepared,
            self.schema_path,
            batch_size=batch_size,
        )

    def graph_counts(
        self, driver: Driver, database: str
    ) -> dict[str, int]:
        return self.adapter.graph_counts(driver, database)

