"""CiP-DMD implementation of the generic ETL adapter contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from neo4j import Driver

from backend.app.etl.extract import (
    QUALITY_CSV_SPECS,
    SOURCE_SPECS,
    audit_quality_csvs,
    extract_records,
)
from backend.app.etl.load import graph_counts, load_payload
from backend.app.etl.transform import transform_records
from backend.app.etl.validate import EXPECTED_COUNTS, validate_payload

from .base import PreparedGraph


class CipDmdAdapter:
    project_id = "cip-dmd"
    dataset_name = "CiP-DMD"
    expected_counts = EXPECTED_COUNTS

    def required_paths(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                [
                    *(spec[0] for spec in SOURCE_SPECS),
                    *QUALITY_CSV_SPECS.keys(),
                ]
            )
        )

    def prepare(self, raw_root: Path) -> PreparedGraph:
        extracted = extract_records(raw_root)
        quality_csv_audit = audit_quality_csvs(raw_root)
        payload = transform_records(extracted)
        validation = validate_payload(payload)
        return PreparedGraph(
            project_id=self.project_id,
            dataset_name=self.dataset_name,
            payload=payload,
            validation=validation,
            source_audit={"quality_csvs": quality_csv_audit},
        )

    def load(
        self,
        driver: Driver,
        database: str,
        prepared: PreparedGraph,
        schema_path: Path,
        *,
        batch_size: int,
    ) -> dict[str, Any]:
        if prepared.project_id != self.project_id:
            raise ValueError("PreparedGraph와 adapter 프로젝트가 다릅니다.")
        return load_payload(
            driver,
            database,
            prepared.payload,
            schema_path,
            batch_size=batch_size,
            project_id=self.project_id,
        )

    def graph_counts(
        self, driver: Driver, database: str
    ) -> dict[str, int]:
        return graph_counts(driver, database, self.project_id)
