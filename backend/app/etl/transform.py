"""Normalize nested CiP-DMD records into graph-shaped batch payloads."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
from typing import Any


PROCESS_ALIASES = {"cnc_mill": "cnc_milling_machine"}
PROCESS_DISPLAY_NAMES = {
    "saw": "Sawing",
    "cnc_milling_machine": "CNC Milling",
    "cnc_lathe": "CNC Turning",
    "assembly": "Assembly",
}
EQUIPMENT_BY_PROCESS = {
    "saw": {
        "equipment_id": "kasto-sba-2",
        "name": "Kasto SBA 2",
        "equipment_type": "saw",
    },
    "cnc_milling_machine": {
        "equipment_id": "dmc-50h",
        "name": "DMC 50H",
        "equipment_type": "cnc_milling_machine",
    },
    "cnc_lathe": {
        "equipment_id": "index-c65",
        "name": "Index C65",
        "equipment_type": "cnc_lathe",
    },
}
ANOMALY_CLASSES = {
    "0": {
        "code": "0",
        "name": "Normal process",
        "description": "Normal process",
        "is_normal": True,
    },
    "1": {
        "code": "1",
        "name": "Misaligned raw cutting material",
        "description": (
            "Raw cutting material was badly aligned at the saw; "
            "the resulting cylinder bottom may be cut too short."
        ),
        "is_normal": False,
    },
    "2": {
        "code": "2",
        "name": "Uneven milling-jig clamping",
        "description": "Part was unevenly clamped in the milling jig.",
        "is_normal": False,
    },
    "3": {
        "code": "3",
        "name": "Miscellaneous process error",
        "description": (
            "Miscellaneous errors happened during the process and are "
            "not visible in process data."
        ),
        "is_normal": False,
    },
}


@dataclass
class GraphPayload:
    parts: list[dict[str, Any]]
    processes: list[dict[str, Any]]
    equipment: list[dict[str, Any]]
    anomaly_classes: list[dict[str, Any]]
    process_runs: list[dict[str, Any]]
    measurements: list[dict[str, Any]]
    assemblies: list[dict[str, Any]]
    quarantined: list[dict[str, Any]]
    source_stats: dict[str, dict[str, int]]

    def counts(self) -> dict[str, int]:
        return {
            "Part": len(self.parts),
            "Process": len(self.processes),
            "Equipment": len(self.equipment),
            "AnomalyClass": len(self.anomaly_classes),
            "ProcessRun": len(self.process_runs),
            "QualityMeasurement": len(self.measurements),
            "QualityFailure": sum(
                not row["qc_pass"] for row in self.measurements
            ),
            "ASSEMBLED_FROM": len(self.assemblies),
            "UNDERWENT": len(self.process_runs),
            "INSTANCE_OF": len(self.process_runs),
            "RUN_ON": len(self.process_runs),
            "CLASSIFIED_AS": len(self.process_runs),
            "HAS_MEASUREMENT": len(self.measurements),
            "FOR_PROCESS": len(self.measurements),
        }

    def summary(self) -> dict[str, Any]:
        return {
            "counts": self.counts(),
            "quarantined_count": len(self.quarantined),
            "quarantined_samples": self.quarantined[:10],
            "source_stats": self.source_stats,
        }


def normalize_process(name: str) -> str:
    normalized = PROCESS_ALIASES.get(name, name)
    if normalized not in PROCESS_DISPLAY_NAMES:
        raise ValueError(f"Unsupported process name: {name!r}")
    return normalized


def parse_numeric(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def is_placeholder(record: dict[str, Any]) -> bool:
    return any(
        "part_id_" in str(component_id)
        for component_id in record.get("component_ids", [])
    )


def deduplicate_records(
    records: list[dict[str, Any]], source_name: str
) -> tuple[list[dict[str, Any]], int]:
    by_id: dict[str, dict[str, Any]] = {}
    duplicates = 0
    for record in records:
        part_id = str(record.get("part_id", ""))
        if not part_id:
            raise ValueError(f"Missing part_id in {source_name}")
        if part_id not in by_id:
            by_id[part_id] = record
        elif by_id[part_id] == record:
            duplicates += 1
        else:
            raise ValueError(
                f"Conflicting records for part_id {part_id} in {source_name}"
            )
    return list(by_id.values()), duplicates


def transform_records(
    extracted: list[tuple[str, str, bool, list[dict[str, Any]]]],
) -> GraphPayload:
    indexed_parts: dict[str, dict[str, Any]] = {}
    source_stats: dict[str, dict[str, int]] = {}

    for source_file, subtype, reworked, raw_records in extracted:
        placeholder_count = sum(
            subtype == "Cylinder" and is_placeholder(record)
            for record in raw_records
        )
        usable = [
            record
            for record in raw_records
            if not (subtype == "Cylinder" and is_placeholder(record))
        ]
        unique_records, duplicate_count = deduplicate_records(
            usable, source_file
        )
        source_stats[source_file] = {
            "raw_records": len(raw_records),
            "placeholder_records": placeholder_count,
            "exact_duplicate_records": duplicate_count,
            "projected_parts": len(unique_records),
        }

        for record in unique_records:
            part_id = str(record["part_id"])
            if part_id in indexed_parts:
                raise ValueError(
                    f"part_id {part_id} appears in multiple source files"
                )
            indexed_parts[part_id] = {
                "record": record,
                "subtype": subtype,
                "reworked": reworked,
                "source_file": source_file,
            }

    parts: list[dict[str, Any]] = []
    process_runs: list[dict[str, Any]] = []
    measurements: list[dict[str, Any]] = []
    processes: dict[str, dict[str, str]] = {}

    for part_id, item in indexed_parts.items():
        record = item["record"]
        part_type = str(record["part_type"])
        parts.append(
            {
                "part_id": part_id,
                "part_type": part_type,
                "subtype": item["subtype"],
                "reworked": bool(item["reworked"]),
                "source_file": item["source_file"],
            }
        )

        run_occurrences: Counter[str] = Counter()
        for sequence, process_run in enumerate(
            record.get("process_data", []), start=1
        ):
            process_name = normalize_process(str(process_run["name"]))
            anomaly_code = str(process_run["anomaly"])
            if anomaly_code not in ANOMALY_CLASSES:
                raise ValueError(
                    f"Unsupported anomaly class: {anomaly_code!r}"
                )
            processes[process_name] = {
                "name": process_name,
                "display_name": PROCESS_DISPLAY_NAMES[process_name],
            }
            occurrence = run_occurrences[process_name]
            run_occurrences[process_name] += 1
            process_runs.append(
                {
                    "run_id": f"{part_id}:{process_name}:{occurrence}",
                    "part_id": part_id,
                    "process_name": process_name,
                    "sequence": sequence,
                    "anomaly": anomaly_code,
                    "anomaly_code": anomaly_code,
                    "equipment_id": (
                        EQUIPMENT_BY_PROCESS.get(process_name) or {}
                    ).get("equipment_id"),
                    "start_time": process_run.get("start_time"),
                    "end_time": process_run.get("end_time"),
                    "sensor_file_count": len(
                        process_run.get("data_paths", [])
                    ),
                }
            )

        measurement_occurrences: Counter[tuple[str, str]] = Counter()
        for quality_group in record.get("quality_data", []):
            process_name = normalize_process(str(quality_group["process"]))
            processes[process_name] = {
                "name": process_name,
                "display_name": PROCESS_DISPLAY_NAMES[process_name],
            }
            for measurement in quality_group.get("measurements", []):
                feature = str(measurement["feature"])
                key = (process_name, feature)
                occurrence = measurement_occurrences[key]
                measurement_occurrences[key] += 1
                value_text = str(measurement["value"])
                measurements.append(
                    {
                        "measurement_id": (
                            f"{part_id}:{process_name}:{feature}:{occurrence}"
                        ),
                        "part_id": part_id,
                        "process_name": process_name,
                        "feature": feature,
                        "value_text": value_text,
                        "value_numeric": parse_numeric(value_text),
                        "qc_pass": bool(measurement["qc_pass"]),
                    }
                )

    assemblies: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    for part_id, item in indexed_parts.items():
        if item["subtype"] != "Cylinder":
            continue
        component_ids = item["record"].get("component_ids", [])
        for index, role, expected_subtype in (
            (0, "bottom", "CylinderBottom"),
            (1, "rod", "PistonRod"),
        ):
            component_id = (
                str(component_ids[index]) if len(component_ids) > index else ""
            )
            component = indexed_parts.get(component_id)
            if component is None:
                quarantined.append(
                    {
                        "reason": "missing_component_reference",
                        "cylinder_id": part_id,
                        "component_id": component_id,
                        "component_role": role,
                    }
                )
                continue
            if component["subtype"] != expected_subtype:
                quarantined.append(
                    {
                        "reason": "unexpected_component_type",
                        "cylinder_id": part_id,
                        "component_id": component_id,
                        "component_role": role,
                        "actual_subtype": component["subtype"],
                    }
                )
                continue
            assemblies.append(
                {
                    "cylinder_id": part_id,
                    "component_id": component_id,
                    "component_role": role,
                }
            )

    return GraphPayload(
        parts=parts,
        processes=sorted(processes.values(), key=lambda row: row["name"]),
        equipment=sorted(
            EQUIPMENT_BY_PROCESS.values(),
            key=lambda row: row["equipment_id"],
        ),
        anomaly_classes=sorted(
            ANOMALY_CLASSES.values(), key=lambda row: row["code"]
        ),
        process_runs=process_runs,
        measurements=measurements,
        assemblies=assemblies,
        quarantined=quarantined,
        source_stats=source_stats,
    )
