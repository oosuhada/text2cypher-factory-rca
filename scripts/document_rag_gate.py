#!/usr/bin/env python3
"""Evaluate Stage 3-4 LlamaIndex ingestion, retrieval and citation safety."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.rag import DocumentRagService


def _ingest_fixtures(storage_root: Path) -> dict[str, DocumentRagService]:
    fixture_manifest = json.loads(
        (PROJECT_ROOT / "evaluation" / "rag_fixtures.json").read_text(
            encoding="utf-8"
        )
    )
    services: dict[str, DocumentRagService] = {}
    for project_id, documents in fixture_manifest["projects"].items():
        service = DocumentRagService(storage_root, project_id)
        for document in documents:
            source = PROJECT_ROOT / document["source_path"]
            service.ingest(
                document_id=document["document_id"],
                title=document["title"],
                version=document["version"],
                document_type=document["document_type"],
                source_filename=source.name,
                content=source.read_text(encoding="utf-8"),
                effective_date=document.get("effective_date"),
                security_classification=document.get(
                    "security_classification", "internal"
                ),
                allowed_roles=document.get("allowed_roles", []),
                is_current=document.get("is_current", True),
            )
        services[project_id] = service
    return services


def evaluate() -> dict:
    baseline = json.loads(
        (PROJECT_ROOT / "evaluation" / "document_rag_baseline.json").read_text(
            encoding="utf-8"
        )
    )
    with TemporaryDirectory() as directory:
        storage_root = Path(directory)
        services = _ingest_fixtures(storage_root)
        rows: list[dict] = []
        retrieved_relevant = 0
        citation_total = 0
        citation_valid = 0
        fabricated_citations = 0
        cross_project_leaks = 0

        for case in baseline["retrieval_cases"]:
            result = services[case["project_id"]].search(
                case["query"],
                roles=case["roles"],
                top_k=5,
                current_only=True,
            )
            expected = (
                case["expected_document_id"],
                case["expected_version"],
            )
            actual = {
                (match["document_id"], match["version"])
                for match in result["matches"]
            }
            relevant = expected in actual
            retrieved_relevant += relevant
            valid_ids = {match["citation_id"] for match in result["matches"]}
            for citation in result["citations"]:
                citation_total += 1
                if citation["citation_id"] in valid_ids:
                    citation_valid += 1
                else:
                    fabricated_citations += 1
            cross_project_leaks += sum(
                match.get("project_id") != case["project_id"]
                for match in result["matches"]
            )
            rows.append(
                {
                    "id": case["id"],
                    "status": result["status"],
                    "expected": list(expected),
                    "actual": sorted([list(item) for item in actual]),
                    "relevant_in_top5": relevant,
                    "citation_count": len(result["citations"]),
                }
            )

        unauthorized_leaks = 0
        empty_case_failures = 0
        for case in baseline["security_cases"]:
            result = services[case["project_id"]].search(
                case["query"],
                roles=case["roles"],
                top_k=5,
                current_only=True,
            )
            if forbidden := case.get("forbidden_document_id"):
                unauthorized_leaks += sum(
                    match["document_id"] == forbidden
                    for match in result["matches"]
                )
            if case.get("expected_status") == "empty":
                if (
                    result["status"] != "empty"
                    or result["matches"]
                    or result["citations"]
                ):
                    empty_case_failures += 1

        equipment = services["equipment-history"]
        current = equipment.search(
            "유압 펌프 교체 후 시험",
            roles=("Analyst",),
            top_k=20,
            current_only=True,
        )
        superseded_current_only_count = sum(
            match["document_id"] == "press-maintenance-manual"
            and match["version"] == "1.0"
            for match in current["matches"]
        )
        all_versions = equipment.search(
            "hydraulic pump replacement low pressure five minutes",
            roles=("Analyst",),
            top_k=20,
            current_only=False,
        )
        old_version_retrievable = any(
            match["document_id"] == "press-maintenance-manual"
            and match["version"] == "1.0"
            for match in all_versions["matches"]
        )

        reloaded = DocumentRagService(storage_root, "equipment-history")
        persistence_result = reloaded.search(
            "압력 안정화 시험",
            roles=("Analyst",),
            top_k=5,
        )
        persistence_ok = bool(persistence_result["matches"])
        readiness = reloaded.readiness()

    routed_case_count = len(baseline["retrieval_cases"])
    recall_at_5 = retrieved_relevant / routed_case_count
    citation_precision = citation_valid / citation_total if citation_total else 1.0
    metrics = {
        "retrieval_case_count": routed_case_count,
        "recall_at_5": recall_at_5,
        "citation_precision": citation_precision,
        "fabricated_citation_count": fabricated_citations,
        "cross_project_leak_count": cross_project_leaks,
        "unauthorized_document_leak_count": unauthorized_leaks,
        "superseded_current_only_count": superseded_current_only_count,
        "empty_case_failure_count": empty_case_failures,
    }
    thresholds = baseline["thresholds"]
    checks = {
        "framework": (
            readiness["framework"] == baseline["framework"]
            and readiness["framework_version"] == baseline["framework_version"]
            and readiness["index_version"] == baseline["index_version"]
        ),
        "recall_at_5": recall_at_5 >= thresholds["recall_at_5"],
        "citation_precision": (
            citation_precision >= thresholds["citation_precision"]
        ),
        "fabricated_citations": (
            fabricated_citations
            <= thresholds["fabricated_citation_count"]
        ),
        "project_isolation": (
            cross_project_leaks <= thresholds["cross_project_leak_count"]
        ),
        "document_authorization": (
            unauthorized_leaks
            <= thresholds["unauthorized_document_leak_count"]
        ),
        "current_version_filter": (
            superseded_current_only_count
            <= thresholds["superseded_current_only_count"]
            and old_version_retrievable
        ),
        "empty_query_has_no_citation": empty_case_failures == 0,
        "persisted_index_reload": persistence_ok,
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "baseline_version": baseline["version"],
        "framework": {
            "name": readiness["framework"],
            "version": readiness["framework_version"],
            "index_version": readiness["index_version"],
            "embedding_model": readiness["embedding_model"],
        },
        "metrics": metrics,
        "thresholds": thresholds,
        "checks": checks,
        "rows": rows,
    }


def main() -> int:
    report = evaluate()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
