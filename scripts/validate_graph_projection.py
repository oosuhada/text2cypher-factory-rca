#!/usr/bin/env python3
"""Project CiP-DMD metadata onto the stage-3 graph schema and validate counts."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any


PROCESS_ALIASES = {
    "cnc_mill": "cnc_milling_machine",
}
EQUIPMENT_BY_PROCESS = {
    "saw": "kasto-sba-2",
    "cnc_milling_machine": "dmc-50h",
    "cnc_lathe": "index-c65",
}
ANOMALY_CODES = {"0", "1", "2", "3"}

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


def load_json(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_process(name: str) -> str:
    return PROCESS_ALIASES.get(name, name)


def is_placeholder(record: dict[str, Any]) -> bool:
    return any(
        "part_id_" in str(component_id)
        for component_id in record.get("component_ids", [])
    )


def deduplicate_records(
    records: list[dict[str, Any]], source_name: str
) -> tuple[list[dict[str, Any]], int]:
    by_id: dict[str, dict[str, Any]] = {}
    duplicate_count = 0
    for record in records:
        part_id = str(record["part_id"])
        if part_id not in by_id:
            by_id[part_id] = record
            continue
        if by_id[part_id] != record:
            raise ValueError(
                f"Conflicting duplicate part_id {part_id!r} in {source_name}"
            )
        duplicate_count += 1
    return list(by_id.values()), duplicate_count


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    raw_root = project_root / "data" / "raw" / "cip_dmd"
    output_path = (
        project_root / "data" / "processed" / "cip_dmd_graph_projection.json"
    )

    source_specs = [
        ("cylinder/meta_data.json", "Cylinder", False),
        ("cylinder_bottom/meta_data.json", "CylinderBottom", False),
        ("piston_rod/meta_data.json", "PistonRod", False),
        (
            "piston_rod/reworked_piston_rods_meta_data.json",
            "PistonRod",
            True,
        ),
    ]

    parts: dict[str, dict[str, Any]] = {}
    source_stats: dict[str, dict[str, int]] = {}
    cylinders: list[dict[str, Any]] = []

    for relative_path, subtype, reworked in source_specs:
        source_records = load_json(raw_root / relative_path)
        placeholder_count = sum(
            subtype == "Cylinder" and is_placeholder(record)
            for record in source_records
        )
        source_records = [
            record
            for record in source_records
            if not (subtype == "Cylinder" and is_placeholder(record))
        ]
        unique_records, duplicate_count = deduplicate_records(
            source_records, relative_path
        )
        source_stats[relative_path] = {
            "raw_records": len(source_records) + placeholder_count,
            "placeholder_records": placeholder_count,
            "exact_duplicate_records": duplicate_count,
            "projected_parts": len(unique_records),
        }

        for record in unique_records:
            part_id = str(record["part_id"])
            if part_id in parts:
                raise ValueError(f"part_id {part_id!r} appears in multiple sources")
            parts[part_id] = {
                "record": record,
                "subtype": subtype,
                "reworked": reworked,
                "source_file": relative_path,
            }
            if subtype == "Cylinder":
                cylinders.append(record)

    process_names: set[str] = set()
    run_ids: set[str] = set()
    measurement_ids: set[str] = set()
    failure_count = 0
    used_equipment_ids: set[str] = set()
    used_anomaly_codes: set[str] = set()

    for part_id, item in parts.items():
        record = item["record"]
        run_occurrences: Counter[str] = Counter()
        for process_run in record.get("process_data", []):
            process_name = normalize_process(str(process_run["name"]))
            process_names.add(process_name)
            used_equipment_ids.add(EQUIPMENT_BY_PROCESS[process_name])
            anomaly_code = str(process_run["anomaly"])
            if anomaly_code not in ANOMALY_CODES:
                raise ValueError(f"Unknown anomaly class: {anomaly_code}")
            used_anomaly_codes.add(anomaly_code)
            occurrence = run_occurrences[process_name]
            run_occurrences[process_name] += 1
            run_id = f"{part_id}:{process_name}:{occurrence}"
            if run_id in run_ids:
                raise ValueError(f"Duplicate run_id: {run_id}")
            run_ids.add(run_id)

        measurement_occurrences: Counter[tuple[str, str]] = Counter()
        for quality_group in record.get("quality_data", []):
            process_name = normalize_process(str(quality_group["process"]))
            process_names.add(process_name)
            for measurement in quality_group.get("measurements", []):
                feature = str(measurement["feature"])
                key = (process_name, feature)
                occurrence = measurement_occurrences[key]
                measurement_occurrences[key] += 1
                measurement_id = (
                    f"{part_id}:{process_name}:{feature}:{occurrence}"
                )
                if measurement_id in measurement_ids:
                    raise ValueError(
                        f"Duplicate measurement_id: {measurement_id}"
                    )
                measurement_ids.add(measurement_id)
                failure_count += not bool(measurement["qc_pass"])

    assembled_from = 0
    missing_component_references: list[dict[str, str]] = []
    for cylinder in cylinders:
        component_ids = cylinder.get("component_ids", [])
        for index, role in ((0, "bottom"), (1, "rod")):
            if len(component_ids) <= index:
                missing_component_references.append(
                    {
                        "cylinder_id": str(cylinder["part_id"]),
                        "component_id": "",
                        "role": role,
                    }
                )
                continue
            component_id = str(component_ids[index])
            if component_id not in parts:
                missing_component_references.append(
                    {
                        "cylinder_id": str(cylinder["part_id"]),
                        "component_id": component_id,
                        "role": role,
                    }
                )
                continue
            assembled_from += 1

    counts = {
        "Part": len(parts),
        "Process": len(process_names),
        "Equipment": len(used_equipment_ids),
        "AnomalyClass": len(ANOMALY_CODES),
        "ProcessRun": len(run_ids),
        "QualityMeasurement": len(measurement_ids),
        "QualityFailure": failure_count,
        "ASSEMBLED_FROM": assembled_from,
        "UNDERWENT": len(run_ids),
        "INSTANCE_OF": len(run_ids),
        "RUN_ON": len(run_ids),
        "CLASSIFIED_AS": len(run_ids),
        "HAS_MEASUREMENT": len(measurement_ids),
        "FOR_PROCESS": len(measurement_ids),
    }
    mismatches = {
        key: {"expected": expected, "actual": counts.get(key)}
        for key, expected in EXPECTED_COUNTS.items()
        if counts.get(key) != expected
    }
    if mismatches:
        raise AssertionError(f"Graph projection count mismatch: {mismatches}")

    node_count = sum(
        counts[label]
        for label in (
            "Part",
            "Process",
            "Equipment",
            "AnomalyClass",
            "ProcessRun",
            "QualityMeasurement",
        )
    )
    relationship_count = sum(
        counts[relationship]
        for relationship in (
            "ASSEMBLED_FROM",
            "UNDERWENT",
            "INSTANCE_OF",
            "RUN_ON",
            "CLASSIFIED_AS",
            "HAS_MEASUREMENT",
            "FOR_PROCESS",
        )
    )
    result = {
        "dataset": "CiP-DMD",
        "schema_version": "stage-3-v1.1",
        "status": "PASS",
        "source_stats": source_stats,
        "process_names": sorted(process_names),
        "equipment_ids": sorted(used_equipment_ids),
        "anomaly_codes": sorted(used_anomaly_codes),
        "counts": counts,
        "totals": {
            "nodes": node_count,
            "relationships": relationship_count,
        },
        "integrity": {
            "unique_part_ids": True,
            "unique_run_ids": True,
            "unique_measurement_ids": True,
            "missing_component_reference_count": len(
                missing_component_references
            ),
            "missing_component_reference_samples": (
                missing_component_references[:10]
            ),
        },
    }
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
