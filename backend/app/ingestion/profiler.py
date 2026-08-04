"""Deterministic, dependency-light profiling for tabular source files."""

from __future__ import annotations

import json
from typing import Any

from .readers import NORMALIZED_SUFFIXES, read_tabular_bytes

SUPPORTED_SUFFIXES = NORMALIZED_SUFFIXES
PROFILE_VERSION = "1.0"


def _infer_type(values: list[Any]) -> str:
    populated = [value for value in values if value not in (None, "")]
    if not populated:
        return "EMPTY"
    lowered = {str(value).strip().lower() for value in populated}
    if lowered <= {"true", "false", "0", "1"}:
        return "BOOLEAN"
    try:
        for value in populated:
            int(str(value))
        return "INTEGER"
    except (TypeError, ValueError):
        pass
    try:
        for value in populated:
            float(str(value))
        return "FLOAT"
    except (TypeError, ValueError):
        return "STRING"


def profile_tabular(filename: str, payload: bytes) -> dict[str, Any]:
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError("CSV와 JSON 파일만 지원합니다.")
    rows = read_tabular_bytes(filename, payload)
    columns = list(dict.fromkeys(key for row in rows for key in row))
    duplicate_row_count = len(rows) - len(
        {
            json.dumps(row, sort_keys=True, default=str)
            for row in rows
        }
    )
    profiles = []
    missing_cell_count = 0
    for column in columns:
        values = [row.get(column) for row in rows]
        missing = sum(value in (None, "") for value in values)
        missing_cell_count += missing
        unique = len({str(value) for value in values if value not in (None, "")})
        profiles.append(
            {
                "name": column,
                "inferred_type": _infer_type(values),
                "missing_count": missing,
                "missing_rate": round(missing / len(rows), 6) if rows else 0.0,
                "unique_count": unique,
                "identity_candidate": bool(rows) and missing == 0 and unique == len(rows),
                "samples": [
                    value for value in values if value not in (None, "")
                ][:3],
            }
        )
    return {
        "profile_version": PROFILE_VERSION,
        "filename": filename,
        "format": suffix.lstrip("."),
        "row_count": len(rows),
        "column_count": len(columns),
        "columns": profiles,
        "sample_rows": rows[:5],
        "quality": {
            "missing_cell_count": missing_cell_count,
            "duplicate_row_count": duplicate_row_count,
            "issue_count": missing_cell_count + duplicate_row_count,
        },
    }
