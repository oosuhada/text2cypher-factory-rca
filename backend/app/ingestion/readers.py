"""Dependency-light readers for normalized tabular source files."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any


NORMALIZED_SUFFIXES = {".csv", ".json"}


def read_tabular_bytes(
    filename: str, payload: bytes
) -> list[dict[str, Any]]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".csv":
        text = payload.decode("utf-8-sig")
        return [dict(row) for row in csv.DictReader(io.StringIO(text))]
    if suffix == ".json":
        value = json.loads(payload.decode("utf-8-sig"))
        if isinstance(value, dict):
            value = value.get("rows", value.get("data", [value]))
        if not isinstance(value, list) or any(
            not isinstance(row, dict) for row in value
        ):
            raise ValueError(
                "JSON은 객체 배열 또는 rows/data 객체 배열이어야 합니다."
            )
        return [dict(row) for row in value]
    raise ValueError("정규화된 CSV 또는 JSON 파일이 필요합니다.")


def read_tabular_path(path: Path) -> list[dict[str, Any]]:
    return read_tabular_bytes(path.name, path.read_bytes())

