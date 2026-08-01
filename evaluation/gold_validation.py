"""Deterministic Gold-result snapshots and result-set comparison."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from collections import Counter
from typing import Any, Iterable, Mapping

import yaml


def load_gold_questions(path: Path) -> list[dict[str, Any]]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    questions = payload.get("questions", [])
    if len(questions) != 15:
        raise ValueError(f"Expected 15 Gold questions, found {len(questions)}")
    return questions


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return round(value, 8)
    if isinstance(value, Mapping):
        return {
            str(key): _json_safe(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple, set)):
        normalized = [_json_safe(item) for item in value]
        return sorted(normalized, key=canonical_json)
    if hasattr(value, "iso_format"):
        return value.iso_format()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def normalize_records(
    records: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    normalized = [_json_safe(dict(record)) for record in records]
    return sorted(normalized, key=canonical_json)


def rows_fingerprint(rows: list[dict[str, Any]]) -> str:
    return hashlib.sha256(canonical_json(rows).encode("utf-8")).hexdigest()


def build_snapshot(
    question: Mapping[str, Any],
    records: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    rows = normalize_records(records)
    expected_status = question.get("expected_status", "success")
    actual_status = "empty" if not rows else "success"
    if actual_status != expected_status:
        raise ValueError(
            f"{question['id']} expected {expected_status}, "
            f"got {actual_status}"
        )
    return {
        "question_id": question["id"],
        "category": question["category"],
        "question": question["question"],
        "expected_status": expected_status,
        "row_count": len(rows),
        "rows_sha256": rows_fingerprint(rows),
        "normalized_rows": rows,
    }


def compare_snapshot(
    expected: Mapping[str, Any],
    actual: Mapping[str, Any],
) -> dict[str, Any]:
    expected_rows = expected.get("normalized_rows", [])
    actual_rows = actual.get("normalized_rows", [])
    identity_match = (
        expected.get("question_id") == actual.get("question_id")
        and expected.get("expected_status")
        == actual.get("expected_status")
        and expected.get("row_count") == actual.get("row_count")
    )
    strict_match = (
        identity_match
        and expected.get("rows_sha256") == actual.get("rows_sha256")
        and expected_rows == actual_rows
    )
    semantic_match = identity_match and _value_rows_match(
        expected_rows, actual_rows
    )
    return {
        # Business-answer accuracy ignores aliases and permits extra evidence
        # columns, while strict_match separately preserves the output contract.
        "match": semantic_match,
        "semantic_match": semantic_match,
        "strict_match": strict_match,
        "contract_only_mismatch": semantic_match and not strict_match,
        "question_id": actual.get("question_id"),
        "expected_row_count": expected.get("row_count"),
        "actual_row_count": actual.get("row_count"),
        "expected_sha256": expected.get("rows_sha256"),
        "actual_sha256": actual.get("rows_sha256"),
        "missing_rows": [
            row for row in expected_rows if row not in actual_rows
        ][:5],
        "unexpected_rows": [
            row for row in actual_rows if row not in expected_rows
        ][:5],
    }


def _row_value_signature(row: Mapping[str, Any]) -> Counter[str]:
    return Counter(
        canonical_json(_json_safe(value)) for value in row.values()
    )


def _contains_expected_values(
    expected: Counter[str], actual: Counter[str]
) -> bool:
    return all(actual[value] >= count for value, count in expected.items())


def _value_rows_match(
    expected_rows: list[dict[str, Any]],
    actual_rows: list[dict[str, Any]],
) -> bool:
    """Match rows by values, ignoring aliases and allowing extra evidence."""
    if len(expected_rows) != len(actual_rows):
        return False
    expected_signatures = [
        _row_value_signature(row) for row in expected_rows
    ]
    actual_signatures = [_row_value_signature(row) for row in actual_rows]
    candidates = [
        [
            actual_index
            for actual_index, actual_signature in enumerate(
                actual_signatures
            )
            if _contains_expected_values(
                expected_signature, actual_signature
            )
        ]
        for expected_signature in expected_signatures
    ]
    if any(not options for options in candidates):
        return False

    matched_expected_by_actual: dict[int, int] = {}

    def assign(expected_index: int, seen: set[int]) -> bool:
        for actual_index in candidates[expected_index]:
            if actual_index in seen:
                continue
            seen.add(actual_index)
            previous = matched_expected_by_actual.get(actual_index)
            if previous is None or assign(previous, seen):
                matched_expected_by_actual[actual_index] = expected_index
                return True
        return False

    for expected_index in sorted(
        range(len(expected_rows)), key=lambda index: len(candidates[index])
    ):
        if not assign(expected_index, set()):
            return False
    return True


def load_snapshot(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_snapshot(path: Path, snapshot: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
