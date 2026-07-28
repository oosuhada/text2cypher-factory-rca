#!/usr/bin/env python3
"""Create the second-domain project through the same upload/mapping path."""

from __future__ import annotations

import base64
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE_VERSION = "synthetic-equipment-history-v1"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.ingestion import DatasetWorkspace
from backend.app.mapping import MappingWorkspace
from backend.app.projects import ProjectRegistry
from backend.app.schema_registry import SchemaRegistry


def main() -> None:
    projects = ProjectRegistry(ROOT / "data" / "processed" / "projects.sqlite3")
    if projects.get("equipment-history") is None:
        projects.create(
            project_id="equipment-history",
            name="Equipment Maintenance History",
            domain_type="equipment-history",
            dataset_name="Public-style maintenance example",
        )
    datasets = DatasetWorkspace(
        ROOT / "data" / "processed" / "project_uploads"
    )
    source = ROOT / "examples" / "equipment_history" / "events.csv"
    upload = datasets.profile_upload(
        "equipment-history",
        [
            {
                "filename": source.name,
                "content_base64": base64.b64encode(source.read_bytes()).decode(),
            }
        ],
    )
    schemas = SchemaRegistry(ROOT / "schemas")
    mappings = MappingWorkspace(
        ROOT / "data" / "processed" / "project_mappings",
        datasets,
        schemas,
    )
    mapping = json.loads(
        (ROOT / "examples" / "equipment_history" / "mapping.json").read_text(
            encoding="utf-8"
        )
    )
    result = mappings.approve(
        "equipment-history", upload["upload_id"], mapping
    )
    projects.update(
        "equipment-history",
        schema_version="1.0",
        source_version=SOURCE_VERSION,
    )
    current_status = projects.require("equipment-history")["status"]
    if current_status == "draft":
        projects.transition(
            "equipment-history",
            "profiling",
            reason="example_source_profiled",
        )
        current_status = "profiling"
    if current_status == "profiling":
        projects.transition(
            "equipment-history",
            "mapping_review",
            reason="example_mapping_approved",
        )
    print(
        json.dumps(
            {
                "project_id": "equipment-history",
                "upload_id": upload["upload_id"],
                "status": result["status"],
                "node_types": len(result["manifest"]["nodes"]),
                "relationship_types": len(result["manifest"]["relationships"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
