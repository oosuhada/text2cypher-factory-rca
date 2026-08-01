"""Extract CiP-DMD metadata from the fixed source files."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


SOURCE_SPECS = (
    ("cylinder/meta_data.json", "Cylinder", False),
    ("cylinder_bottom/meta_data.json", "CylinderBottom", False),
    ("piston_rod/meta_data.json", "PistonRod", False),
    (
        "piston_rod/reworked_piston_rods_meta_data.json",
        "PistonRod",
        True,
    ),
)

QUALITY_CSV_SPECS = {
    "cylinder_bottom/saw/quality_data/quality_data.csv": {
        "rows": 985,
        "columns": ["part_id", "weight", "anomaly"],
    },
    "cylinder_bottom/cnc_milling_machine/quality_data/quality_data.csv": {
        "rows": 846,
        "columns": [
            "part_id",
            "surface_roughness",
            "parallelism",
            "groove_depth",
            "groove_diameter",
        ],
    },
    "cylinder/assembly/quality_data/quality_data.csv": {
        "rows": 802,
        "columns": [
            "part_id_cylinder_bottom",
            "part_id_piston_rod",
            "rework",
            "pressure",
        ],
    },
    "piston_rod/cnc_lathe/quality_data/quality_data.csv": {
        "rows": 673,
        "columns": ["part_id", "coaxiality", "diameter", "length"],
    },
}


def load_json(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as source:
        data = json.load(source)
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON list: {path}")
    return data


def extract_records(
    raw_root: Path,
) -> list[tuple[str, str, bool, list[dict[str, Any]]]]:
    extracted = []
    for relative_path, subtype, reworked in SOURCE_SPECS:
        source_path = raw_root / relative_path
        if not source_path.exists():
            raise FileNotFoundError(f"CiP-DMD source is missing: {source_path}")
        extracted.append(
            (
                relative_path,
                subtype,
                reworked,
                load_json(source_path),
            )
        )
    return extracted


def audit_quality_csvs(raw_root: Path) -> dict[str, dict[str, Any]]:
    audit: dict[str, dict[str, Any]] = {}
    for relative_path, expected in QUALITY_CSV_SPECS.items():
        source_path = raw_root / relative_path
        with source_path.open(
            newline="", encoding="utf-8-sig"
        ) as source:
            reader = csv.DictReader(source, delimiter=";")
            rows = list(reader)
            columns = reader.fieldnames or []
        result = {
            "rows": len(rows),
            "columns": columns,
            "expected_rows": expected["rows"],
            "expected_columns": expected["columns"],
            "status": (
                "PASS"
                if len(rows) == expected["rows"]
                and columns == expected["columns"]
                else "FAIL"
            ),
        }
        if result["status"] != "PASS":
            raise ValueError(
                f"Quality CSV audit failed for {relative_path}: {result}"
            )
        audit[relative_path] = result
    return audit
