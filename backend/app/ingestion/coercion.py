"""Shared graph-property coercion used by dry-run and loader."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


def coerce_value(value: Any, property_type: str) -> Any:
    if value in (None, ""):
        return None
    normalized_type = property_type.upper()
    if normalized_type == "INTEGER":
        return int(value)
    if normalized_type == "FLOAT":
        return float(value)
    if normalized_type == "BOOLEAN":
        if isinstance(value, bool):
            return value
        normalized = str(value).strip().lower()
        if normalized in {"true", "1"}:
            return True
        if normalized in {"false", "0"}:
            return False
        raise ValueError(f"BOOLEAN 값으로 변환할 수 없습니다: {value}")
    if normalized_type == "DATE":
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value).strip())
    if normalized_type == "DATETIME":
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(str(value).strip())
    return str(value) if normalized_type == "STRING" else value
