"""Deterministic, dependency-light profiling for tabular source files."""

from __future__ import annotations

import csv
import io
import json
from typing import Any


SUPPORTED_SUFFIXES = {".csv", ".json"}


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


def _rows_from_csv(payload: bytes) -> list[dict[str, Any]]:
    text = payload.decode("utf-8-sig")
    return [dict(row) for row in csv.DictReader(io.StringIO(text))]


def _rows_from_json(payload: bytes) -> list[dict[str, Any]]:
    value = json.loads(payload.decode("utf-8-sig"))
    if isinstance(value, dict):
        value = value.get("rows", value.get("data", [value]))
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ValueError("JSON은 객체 배열 또는 rows/data 객체 배열이어야 합니다.")
    return value


def profile_tabular(filename: str, payload: bytes) -> dict[str, Any]:
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError("CSV와 JSON 파일만 지원합니다.")
    rows = _rows_from_csv(payload) if suffix == ".csv" else _rows_from_json(payload)
    columns = list(dict.fromkeys(key for row in rows for key in row))
    profiles = []
    for column in columns:
        values = [row.get(column) for row in rows]
        missing = sum(value in (None, "") for value in values)
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
        "filename": filename,
        "format": suffix.lstrip("."),
        "row_count": len(rows),
        "column_count": len(columns),
        "columns": profiles,
        "sample_rows": rows[:5],
    }
