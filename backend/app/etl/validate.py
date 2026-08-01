"""Validate transformed payloads before any database write."""

from __future__ import annotations

from typing import Any

from .transform import GraphPayload


EXPECTED_COUNTS = {
    "Part": 2736,
    "Process": 4,
    "Equipment": 3,
    "AnomalyClass": 4,
    "ProcessRun": 2758,
    "QualityMeasurement": 7570,
    "QualityFailure": 443,
    "ASSEMBLED_FROM": 1569,
    "UNDERWENT": 2758,
    "INSTANCE_OF": 2758,
    "RUN_ON": 2758,
    "CLASSIFIED_AS": 2758,
    "HAS_MEASUREMENT": 7570,
    "FOR_PROCESS": 7570,
}


def assert_unique(rows: list[dict[str, Any]], key: str) -> None:
    values = [row[key] for row in rows]
    if len(values) != len(set(values)):
        raise ValueError(f"Duplicate {key} values remain after transformation")


def validate_payload(payload: GraphPayload) -> dict[str, Any]:
    assert_unique(payload.parts, "part_id")
    assert_unique(payload.processes, "name")
    assert_unique(payload.equipment, "equipment_id")
    assert_unique(payload.anomaly_classes, "code")
    assert_unique(payload.process_runs, "run_id")
    assert_unique(payload.measurements, "measurement_id")

    actual = payload.counts()
    mismatches = {
        name: {"expected": expected, "actual": actual.get(name)}
        for name, expected in EXPECTED_COUNTS.items()
        if actual.get(name) != expected
    }
    if mismatches:
        raise ValueError(f"Unexpected graph projection counts: {mismatches}")

    if len(payload.quarantined) != 35:
        raise ValueError(
            "Expected 35 missing component references, "
            f"found {len(payload.quarantined)}"
        )

    part_ids = {row["part_id"] for row in payload.parts}
    if any(row["part_id"] not in part_ids for row in payload.process_runs):
        raise ValueError("A ProcessRun references an unknown Part")
    if any(row["part_id"] not in part_ids for row in payload.measurements):
        raise ValueError("A QualityMeasurement references an unknown Part")
    equipment_ids = {row["equipment_id"] for row in payload.equipment}
    if any(
        row["equipment_id"] is not None
        and row["equipment_id"] not in equipment_ids
        for row in payload.process_runs
    ):
        raise ValueError("A ProcessRun references an unknown Equipment")

    return {
        "status": "PASS",
        "counts": actual,
        "quarantined_count": len(payload.quarantined),
    }
