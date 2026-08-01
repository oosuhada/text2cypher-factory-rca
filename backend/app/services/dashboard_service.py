"""Read-only dashboard queries backed by the actual Neo4j graph."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from neo4j import Driver, READ_ACCESS

from .diagnostics import format_timestamp, latest_successful_etl


def load_query_audit(
    path: Path, limit: int = 1000
) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def summarize_runtime(events: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(events)
    status_counts: dict[str, int] = {}
    for event in events:
        status = str(event.get("status", "unknown"))
        status_counts[status] = status_counts.get(status, 0) + 1
    successes = sum(
        status_counts.get(status, 0) for status in ("success", "empty")
    )
    corrected = [event for event in events if event.get("corrected")]
    corrected_successes = [
        event
        for event in corrected
        if event.get("status") in {"success", "empty"}
    ]
    average_elapsed = (
        sum(float(event.get("elapsed_ms", 0)) for event in events) / total
        if total
        else 0.0
    )
    return {
        "query_count": total,
        "success_rate": successes / total if total else None,
        "average_elapsed_ms": round(average_elapsed, 1),
        "correction_count": len(corrected),
        "correction_success_rate": (
            len(corrected_successes) / len(corrected)
            if corrected
            else None
        ),
        "status_counts": [
            {"status": status, "count": count}
            for status, count in sorted(status_counts.items())
        ],
        "recent_queries": list(reversed(events[-20:])),
        "model_call_count": int(
            sum(float(event.get("call_count", 0)) for event in events)
        ),
        "input_tokens": int(
            sum(float(event.get("input_tokens", 0)) for event in events)
        ),
        "output_tokens": int(
            sum(float(event.get("output_tokens", 0)) for event in events)
        ),
        "estimated_cost_usd": round(
            sum(
                float(event.get("estimated_cost_usd", 0))
                for event in events
            ),
            8,
        ),
    }


def summarize_status_classification(report: dict[str, Any]) -> dict[str, Any]:
    questions = (
        report.get("variants", {})
        .get("self_correction", {})
        .get("questions", [])
    )
    labels = sorted(
        {
            str(question.get(field, "unknown"))
            for question in questions
            for field in ("expected_status", "actual_status")
        }
    )
    matrix = {
        expected: {actual: 0 for actual in labels} for expected in labels
    }
    for question in questions:
        matrix[str(question["expected_status"])][
            str(question["actual_status"])
        ] += 1
    per_class = []
    for label in labels:
        true_positive = matrix[label][label]
        false_positive = sum(
            matrix[expected][label]
            for expected in labels
            if expected != label
        )
        false_negative = sum(
            matrix[label][actual]
            for actual in labels
            if actual != label
        )
        precision = (
            true_positive / (true_positive + false_positive)
            if true_positive + false_positive
            else None
        )
        recall = (
            true_positive / (true_positive + false_negative)
            if true_positive + false_negative
            else None
        )
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision is not None
            and recall is not None
            and precision + recall
            else None
        )
        per_class.append(
            {
                "status": label,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "support": sum(matrix[label].values()),
            }
        )
    applicable_f1 = [
        row["f1"] for row in per_class if row["f1"] is not None
    ]
    correct = sum(matrix[label][label] for label in labels)
    return {
        "labels": labels,
        "matrix": [
            {"expected": expected, **matrix[expected]}
            for expected in labels
        ],
        "per_class": per_class,
        "accuracy": correct / len(questions) if questions else None,
        "macro_f1": (
            sum(applicable_f1) / len(applicable_f1)
            if applicable_f1
            else None
        ),
    }


class DashboardService:
    def __init__(
        self,
        driver: Driver,
        database: str,
        metrics_path: Path,
        audit_log_path: Path,
        processed_root: Path,
    ):
        self.driver = driver
        self.database = database
        self.metrics_path = metrics_path
        self.audit_log_path = audit_log_path
        self.processed_root = processed_root

    def _query(self, cypher: str) -> list[dict[str, Any]]:
        with self.driver.session(
            database=self.database,
            default_access_mode=READ_ACCESS,
        ) as session:
            return [dict(record) for record in session.run(cypher)]

    def snapshot(self) -> dict[str, Any]:
        totals = self._query(
            """
            MATCH (node)
            WITH count(node) AS nodes
            MATCH ()-[relationship]->()
            RETURN nodes, count(relationship) AS relationships
            """
        )[0]
        node_counts = self._query(
            """
            UNWIND [
              'Part', 'Process', 'Equipment', 'AnomalyClass',
              'ProcessRun', 'QualityMeasurement', 'QualityFailure'
            ] AS label
            CALL (label) {
              MATCH (node)
              WHERE label IN labels(node)
              RETURN count(node) AS count
            }
            RETURN label, count
            ORDER BY label
            """
        )
        relationship_counts = self._query(
            """
            MATCH ()-[relationship]->()
            RETURN type(relationship) AS relationship_type,
                   count(relationship) AS count
            ORDER BY count DESC, relationship_type
            """
        )
        equipment_runs = self._query(
            """
            MATCH (run:ProcessRun)-[:RUN_ON]->(equipment:Equipment)
            RETURN equipment.name AS equipment, count(run) AS run_count
            ORDER BY run_count DESC
            """
        )
        anomaly_runs = self._query(
            """
            MATCH (run:ProcessRun)-[:CLASSIFIED_AS]->(anomaly:AnomalyClass)
            RETURN anomaly.code AS anomaly_code,
                   anomaly.name AS anomaly_name,
                   count(run) AS run_count
            ORDER BY anomaly_code
            """
        )
        quality_failures = self._query(
            """
            MATCH (failure:QualityMeasurement:QualityFailure)
            RETURN failure.feature AS feature,
                   count(failure) AS failure_count
            ORDER BY failure_count DESC, feature
            """
        )
        genealogy = self._query(
            """
            MATCH (cylinder:Cylinder)
            OPTIONAL MATCH (cylinder)-[:ASSEMBLED_FROM]->(component:Part)
            WITH cylinder, count(component) AS component_count
            RETURN count(cylinder) AS total_cylinders,
                   sum(CASE WHEN component_count = 2 THEN 1 ELSE 0 END)
                     AS complete_genealogy,
                   sum(CASE WHEN component_count <> 2 THEN 1 ELSE 0 END)
                     AS incomplete_genealogy
            """
        )[0]
        orphan_runs = self._query(
            """
            MATCH (run:ProcessRun)
            WHERE NOT (:Part)-[:UNDERWENT]->(run)
            RETURN count(run) AS count
            """
        )[0]["count"]
        orphan_measurements = self._query(
            """
            MATCH (measurement:QualityMeasurement)
            WHERE NOT (:Part)-[:HAS_MEASUREMENT]->(measurement)
            RETURN count(measurement) AS count
            """
        )[0]["count"]
        metrics = json.loads(self.metrics_path.read_text(encoding="utf-8"))
        blind_results_path = (
            self.metrics_path.parent / "results" / "latest.json"
        )
        blind_evaluation = (
            json.loads(blind_results_path.read_text(encoding="utf-8"))
            if blind_results_path.exists()
            else None
        )
        audit_events = load_query_audit(self.audit_log_path)
        etl_report = latest_successful_etl(self.processed_root)
        return {
            "totals": totals,
            "node_counts": node_counts,
            "relationship_counts": relationship_counts,
            "equipment_runs": equipment_runs,
            "anomaly_runs": anomaly_runs,
            "quality_failures": quality_failures,
            "integrity": {
                **genealogy,
                "genealogy_rate": (
                    genealogy["complete_genealogy"]
                    / genealogy["total_cylinders"]
                ),
                "orphan_process_runs": orphan_runs,
                "orphan_measurements": orphan_measurements,
                "quality_failure_count": sum(
                    row["failure_count"] for row in quality_failures
                ),
            },
            "evaluation": metrics,
            "blind_evaluation": blind_evaluation,
            "status_evaluation": (
                summarize_status_classification(blind_evaluation)
                if blind_evaluation
                else None
            ),
            "etl": (
                {
                    "status": etl_report.get("status"),
                    "mode": etl_report.get("mode"),
                    "started_at": format_timestamp(
                        etl_report.get("started_at")
                    ),
                    "finished_at": format_timestamp(
                        etl_report.get("finished_at")
                    ),
                    "idempotency_status": (
                        etl_report.get("idempotency") or {}
                    ).get("status", "미검증"),
                    "quarantined_count": (
                        etl_report.get("validation") or {}
                    ).get("quarantined_count", 0),
                    "counts": (
                        etl_report.get("validation") or {}
                    ).get("counts", {}),
                    "report_path": etl_report.get("_report_path"),
                }
                if etl_report
                else None
            ),
            "runtime": summarize_runtime(audit_events),
        }
