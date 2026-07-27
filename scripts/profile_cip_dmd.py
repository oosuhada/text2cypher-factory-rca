#!/usr/bin/env python3
"""Profile CiP-DMD metadata and validate relationships required by P3."""

from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path
from typing import Any


def load_json(file_path: Path) -> list[dict[str, Any]]:
    with file_path.open(encoding="utf-8") as source:
        return json.load(source)


def measurements(record: dict[str, Any]):
    for quality_group in record.get("quality_data", []):
        for measurement in quality_group.get("measurements", []):
            yield quality_group.get("process"), measurement


def process_records(record: dict[str, Any]):
    yield from record.get("process_data", [])


def measurement_map(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        measurement["feature"]: measurement
        for _, measurement in measurements(record)
        if measurement.get("feature")
    }


def normalize_anomaly(value: Any) -> str:
    return str(value)


def has_placeholder_components(record: dict[str, Any]) -> bool:
    return any(
        "part_id_" in str(component_id)
        for component_id in record.get("component_ids", [])
    )


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    raw_root = project_root / "data" / "raw" / "cip_dmd"
    output_path = project_root / "data" / "processed" / "cip_dmd_profile.json"

    cylinders_all = load_json(raw_root / "cylinder" / "meta_data.json")
    cylinders = [
        record for record in cylinders_all if not has_placeholder_components(record)
    ]
    bottoms = load_json(raw_root / "cylinder_bottom" / "meta_data.json")
    rods = load_json(raw_root / "piston_rod" / "meta_data.json")
    reworked_rods = load_json(
        raw_root / "piston_rod" / "reworked_piston_rods_meta_data.json"
    )

    bottom_ids = {record["part_id"] for record in bottoms}
    rod_ids = {record["part_id"] for record in rods}
    reworked_rod_ids = {record["part_id"] for record in reworked_rods}
    all_rod_ids = rod_ids | reworked_rod_ids

    bottom_to_cylinders: dict[str, list[str]] = defaultdict(list)
    rod_to_cylinders: dict[str, list[str]] = defaultdict(list)
    for cylinder in cylinders:
        component_ids = cylinder.get("component_ids", [])
        if len(component_ids) == 2:
            bottom_to_cylinders[component_ids[0]].append(cylinder["part_id"])
            rod_to_cylinders[component_ids[1]].append(cylinder["part_id"])

    process_counts = Counter()
    anomaly_by_process: dict[str, Counter[str]] = defaultdict(Counter)
    for record in [*bottoms, *rods, *reworked_rods]:
        for process in process_records(record):
            process_name = process.get("name", "unknown")
            process_counts[process_name] += 1
            anomaly_by_process[process_name][
                normalize_anomaly(process.get("anomaly"))
            ] += 1

    quality_counts = Counter()
    quality_failures = Counter()
    for entity_group in [cylinders, bottoms, rods, reworked_rods]:
        for record in entity_group:
            for _, measurement in measurements(record):
                feature = measurement.get("feature", "unknown")
                quality_counts[feature] += 1
                if measurement.get("qc_pass") is False:
                    quality_failures[feature] += 1

    pressure_failed = []
    rework_failed = []
    for cylinder in cylinders:
        for _, measurement in measurements(cylinder):
            if measurement.get("feature") == "pressure" and not measurement.get(
                "qc_pass"
            ):
                pressure_failed.append(cylinder["part_id"])
            if measurement.get("feature") == "rework" and not measurement.get(
                "qc_pass"
            ):
                rework_failed.append(cylinder["part_id"])

    roughness_failed_bottoms = []
    anomaly_two_bottoms = []
    bottom_milling_anomaly: dict[str, str] = {}
    for bottom in bottoms:
        for process in process_records(bottom):
            if process.get("name") == "cnc_milling_machine":
                bottom_milling_anomaly[bottom["part_id"]] = normalize_anomaly(
                    process.get("anomaly")
                )
        if any(
            measurement.get("feature") == "surface_roughness"
            and measurement.get("qc_pass") is False
            for _, measurement in measurements(bottom)
        ):
            roughness_failed_bottoms.append(bottom["part_id"])
        if any(
            process.get("name") == "cnc_milling_machine"
            and normalize_anomaly(process.get("anomaly")) == "2"
            for process in process_records(bottom)
        ):
            anomaly_two_bottoms.append(bottom["part_id"])

    cylinder_by_id = {record["part_id"]: record for record in cylinders}
    anomaly_two_linked_cylinders = [
        cylinder_by_id[cylinder_id]
        for part_id in anomaly_two_bottoms
        for cylinder_id in bottom_to_cylinders[part_id]
    ]

    complete_genealogies = []
    for cylinder in cylinders:
        component_ids = cylinder.get("component_ids", [])
        if (
            len(component_ids) == 2
            and component_ids[0] in bottom_ids
            and component_ids[1] in all_rod_ids
        ):
            complete_genealogies.append(cylinder["part_id"])

    profile = {
        "dataset": "CiP-DMD",
        "records": {
            "cylinders_all": len(cylinders_all),
            "cylinders_valid": len(cylinders),
            "cylinder_bottoms": len(bottoms),
            "piston_rods": len(rods),
            "reworked_piston_rods": len(reworked_rods),
        },
        "integrity": {
            "placeholder_cylinders_excluded": len(cylinders_all) - len(cylinders),
            "cylinders_with_bottom_reference": sum(
                len(record.get("component_ids", [])) == 2
                and record["component_ids"][0] in bottom_ids
                for record in cylinders
            ),
            "cylinders_with_rod_reference": sum(
                len(record.get("component_ids", [])) == 2
                and record["component_ids"][1] in all_rod_ids
                for record in cylinders
            ),
            "complete_genealogies": len(complete_genealogies),
            "complete_genealogy_rate": round(
                len(complete_genealogies) / len(cylinders), 6
            ),
        },
        "process_counts": dict(process_counts),
        "anomaly_by_process": {
            process: dict(counter)
            for process, counter in anomaly_by_process.items()
        },
        "quality_counts": dict(quality_counts),
        "quality_failures": dict(quality_failures),
        "scope_validation": {
            "pressure_failed_cylinders": {
                "count": len(pressure_failed),
                "sample_ids": pressure_failed[:5],
                "complete_genealogy_count": sum(
                    cylinder_id in complete_genealogies
                    for cylinder_id in pressure_failed
                ),
            },
            "rework_failed_cylinders": {
                "count": len(rework_failed),
                "sample_ids": rework_failed[:5],
            },
            "surface_roughness_failed_bottoms": {
                "count": len(roughness_failed_bottoms),
                "sample_ids": roughness_failed_bottoms[:5],
                "milling_anomaly_distribution": dict(
                    Counter(
                        bottom_milling_anomaly.get(part_id, "missing")
                        for part_id in roughness_failed_bottoms
                    )
                ),
            },
            "milling_anomaly_2_bottoms": {
                "count": len(anomaly_two_bottoms),
                "sample_ids": anomaly_two_bottoms[:5],
                "linked_assembly_count": len(anomaly_two_linked_cylinders),
                "linked_pressure_qc": dict(
                    Counter(
                        str(measurement_map(cylinder)["pressure"]["qc_pass"])
                        for cylinder in anomaly_two_linked_cylinders
                        if "pressure" in measurement_map(cylinder)
                    )
                ),
            },
            "complete_genealogy_samples": complete_genealogies[:5],
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(profile, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(profile, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
