"""Safe, in-memory inspection for candidate CiP-DMD source files."""

from __future__ import annotations

import csv
from io import StringIO
import json
from pathlib import Path
from typing import Any


MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def inspect_uploaded_source(name: str, payload: bytes) -> dict[str, Any]:
    suffix = Path(name).suffix.lower()
    result: dict[str, Any] = {
        "file_name": Path(name).name,
        "size_bytes": len(payload),
        "format": suffix.lstrip(".") or "unknown",
        "status": "FAIL",
        "record_count": 0,
        "columns": [],
        "message": "",
    }
    if len(payload) > MAX_UPLOAD_BYTES:
        result["message"] = "10MB를 초과해 브라우저 사전검증 대상에서 제외됩니다."
        return result
    try:
        if suffix == ".json":
            document = json.loads(payload.decode("utf-8-sig"))
            if not isinstance(document, list) or not all(
                isinstance(row, dict) for row in document
            ):
                raise ValueError("JSON 최상위 구조는 객체 배열이어야 합니다.")
            columns = sorted(
                {
                    str(key)
                    for row in document[:100]
                    for key in row.keys()
                }
            )
            result.update(
                {
                    "record_count": len(document),
                    "columns": columns,
                    "status": "PASS" if "part_id" in columns else "REVIEW",
                    "message": (
                        "CiP-DMD 메타데이터 후보입니다."
                        if "part_id" in columns
                        else "JSON은 유효하지만 part_id가 없어 매핑 검토가 필요합니다."
                    ),
                }
            )
        elif suffix == ".csv":
            text = payload.decode("utf-8-sig")
            sample = text[:8192]
            dialect = csv.Sniffer().sniff(sample, delimiters=";,")
            reader = csv.DictReader(StringIO(text), dialect=dialect)
            rows = list(reader)
            columns = [str(column) for column in (reader.fieldnames or [])]
            has_join_key = any(
                column == "part_id" or column.startswith("part_id_")
                for column in columns
            )
            result.update(
                {
                    "record_count": len(rows),
                    "columns": columns,
                    "status": "PASS" if has_join_key else "REVIEW",
                    "message": (
                        "공통 ID가 확인된 품질 CSV 후보입니다."
                        if has_join_key
                        else "CSV는 유효하지만 part_id 계열 공통 키가 없습니다."
                    ),
                }
            )
        else:
            result["message"] = "JSON 또는 CSV만 사전검증할 수 있습니다."
    except (UnicodeDecodeError, json.JSONDecodeError, csv.Error, ValueError) as error:
        result["message"] = f"파싱 실패: {error}"
    return result
