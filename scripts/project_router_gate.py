#!/usr/bin/env python3
"""Evaluate the Stage 3-2 project router against its checked-in dataset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.agent.project_router import ProjectRouter, route_accuracy
from backend.app.projects import ProjectRegistry
from backend.app.schema_registry import SchemaRegistry


def build_evaluation_router(root: Path, registry_path: Path | None = None) -> ProjectRouter:
    if registry_path is not None:
        return ProjectRouter(
            ProjectRegistry(registry_path),
            SchemaRegistry(root / "schemas"),
        )
    raise ValueError("registry_path is required")


def evaluate(root: Path = PROJECT_ROOT) -> dict:
    document = yaml.safe_load(
        (root / "evaluation" / "project_router.yml").read_text(
            encoding="utf-8"
        )
    )
    with TemporaryDirectory() as directory:
        registry = ProjectRegistry(Path(directory) / "projects.sqlite3")
        registry.ensure_default()
        registry.create(
            project_id="equipment-history",
            name="Equipment Maintenance History",
            domain_type="maintenance",
            dataset_name="Synthetic Equipment History",
            schema_version="1.0",
            status="ready",
            description="설비 정비, 수리, 교체, 점검, 다운타임과 기술자 이력",
            source_version="synthetic-equipment-history-v1",
            _bootstrap=True,
        )
        router = ProjectRouter(registry, SchemaRegistry(root / "schemas"))
        report = route_accuracy(router, document["cases"])

    thresholds = document["thresholds"]
    checks = {
        "top1_accuracy": report["top1_accuracy"]
        >= thresholds["top1_accuracy"],
        "topk_accuracy": report["topk_accuracy"]
        >= thresholds["topk_accuracy"],
        "clarification_accuracy": report["clarification_accuracy"]
        >= thresholds["clarification_accuracy"],
    }
    failures = [
        row
        for row in report["rows"]
        if (
            row["expected_status"] == "routed"
            and not row["top1_correct"]
        )
        or (
            row["expected_status"] == "needs_clarification"
            and row["actual_status"] != "needs_clarification"
        )
    ]
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "baseline_version": document["version"],
        "thresholds": thresholds,
        "metrics": {
            key: report[key]
            for key in (
                "case_count",
                "routed_case_count",
                "clarification_case_count",
                "top1_accuracy",
                "topk_accuracy",
                "clarification_accuracy",
            )
        },
        "checks": checks,
        "failure_count": len(failures),
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    arguments = parser.parse_args()
    report = evaluate()
    if arguments.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            "Project Router Gate "
            f"{report['status']} · Top-1 "
            f"{report['metrics']['top1_accuracy']:.1%} · Top-k "
            f"{report['metrics']['topk_accuracy']:.1%} · Clarification "
            f"{report['metrics']['clarification_accuracy']:.1%}"
        )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
