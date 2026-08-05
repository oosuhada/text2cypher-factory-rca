"""Convert raw Agent state into a factual, UI-ready response."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from backend.app.agent.state import CypherState


PART_FIELDS = {
    "cylinder_id": "Cylinder",
    "bottom_id": "CylinderBottom",
    "rod_id": "PistonRod",
    "part_id": "Part",
    "component_id": "Part",
}


def _display(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return f"{len(value)}개"
    if isinstance(value, dict):
        return f"{len(value)}개 필드"
    return str(value)


def _answer_for(state: CypherState) -> str:
    status = state.get("status", "failed")
    records = state.get("records", [])
    if status == "empty":
        return "조건에 해당하는 데이터를 찾지 못했습니다."
    if status == "blocked":
        return "읽기 전용 시스템이므로 데이터 변경 요청을 실행하지 않았습니다."
    if status == "needs_clarification":
        return "질문 조건이 부족합니다. 부품 종류, 공정 또는 품질 항목을 지정해 주세요."
    if status == "unsupported":
        return (
            "Gold 데모는 등록된 추천 질문만 지원합니다. "
            "자동 또는 Vertex Gemini 모드로 전환해 주세요."
        )
    if status != "success":
        return "생성된 쿼리가 검증을 통과하지 못해 답변을 보류했습니다."

    first = records[0]
    preview = [
        f"{key}={_display(value)}"
        for key, value in first.items()
        if not isinstance(value, (dict, list))
    ][:5]
    if preview:
        return (
            f"조회 결과 {len(records)}행입니다. 첫 번째 결과: "
            + ", ".join(preview)
            + "."
        )
    return f"조회 결과 {len(records)}행입니다. 상세 내용은 결과 표에서 확인할 수 있습니다."


class EvidenceBuilder:
    def __init__(self, max_nodes: int = 250, max_relationships: int = 500):
        self.max_nodes = max_nodes
        self.max_relationships = max_relationships
        self.nodes: dict[str, dict[str, Any]] = {}
        self.relationships: dict[str, dict[str, Any]] = {}
        self.nodes_truncated = False
        self.relationships_truncated = False

    def add_node(
        self,
        label: str,
        raw_id: Any,
        properties: dict[str, Any] | None = None,
        source_field: str | None = None,
    ) -> str | None:
        if raw_id in (None, ""):
            return None
        node_id = f"{label}:{raw_id}"
        if node_id in self.nodes:
            if properties:
                self.nodes[node_id]["properties"].update(
                    {
                        key: value
                        for key, value in properties.items()
                        if value is not None
                    }
                )
            return node_id
        if len(self.nodes) >= self.max_nodes:
            self.nodes_truncated = True
            return None
        self.nodes[node_id] = {
            "id": node_id,
            "label": label,
            "properties": {
                key: value
                for key, value in (properties or {}).items()
                if value is not None
            },
            "source_field": source_field,
        }
        return node_id

    def add_relationship(
        self,
        relationship_type: str,
        source: str | None,
        target: str | None,
        properties: dict[str, Any] | None = None,
    ) -> None:
        if not source or not target:
            return
        relationship_id = f"{source}|{relationship_type}|{target}"
        if relationship_id in self.relationships:
            return
        if len(self.relationships) >= self.max_relationships:
            self.relationships_truncated = True
            return
        self.relationships[relationship_id] = {
            "id": relationship_id,
            "type": relationship_type,
            "source": source,
            "target": target,
            "properties": properties or {},
        }

    @staticmethod
    def _component_label(record: dict[str, Any]) -> str:
        component_type = str(record.get("component_type", "")).lower()
        return {
            "cylinder": "Cylinder",
            "cylinder_bottom": "CylinderBottom",
            "piston_rod": "PistonRod",
        }.get(component_type, "Part")

    def _process_evidence(
        self, item: dict[str, Any], parent: str | None
    ) -> None:
        run_id = item.get("run_id")
        run = self.add_node(
            "ProcessRun",
            run_id,
            {
                "run_id": run_id,
                "sequence": item.get("sequence"),
                "start_time": item.get("start_time"),
                "end_time": item.get("end_time"),
            },
            "process_runs.run_id",
        )
        self.add_relationship("UNDERWENT", parent, run)

        process_name = item.get("process_name")
        process = self.add_node(
            "Process",
            process_name,
            {"name": process_name},
            "process_runs.process_name",
        )
        self.add_relationship("INSTANCE_OF", run, process)

        equipment_name = item.get("equipment")
        equipment = self.add_node(
            "Equipment",
            equipment_name,
            {"name": equipment_name},
            "process_runs.equipment",
        )
        self.add_relationship("RUN_ON", run, equipment)

        anomaly_code = item.get("anomaly_code", item.get("anomaly"))
        anomaly = self.add_node(
            "AnomalyClass",
            anomaly_code,
            {
                "code": anomaly_code,
                "name": item.get("anomaly_name"),
            },
            "process_runs.anomaly_code",
        )
        self.add_relationship("CLASSIFIED_AS", run, anomaly)

    def _measurement_evidence(
        self, item: dict[str, Any], parent: str | None
    ) -> None:
        measurement_id = item.get("measurement_id")
        if not measurement_id:
            return
        label = (
            "QualityFailure"
            if item.get("qc_pass") is False
            else "QualityMeasurement"
        )
        measurement = self.add_node(
            label,
            measurement_id,
            {
                "measurement_id": measurement_id,
                "feature": item.get("feature"),
                "value": item.get("value"),
                "qc_pass": item.get("qc_pass"),
            },
            "quality_measurements.measurement_id",
        )
        self.add_relationship("HAS_MEASUREMENT", parent, measurement)
        process_name = item.get("process_name")
        process = self.add_node(
            "Process",
            process_name,
            {"name": process_name},
            "quality_measurements.process_name",
        )
        self.add_relationship("FOR_PROCESS", measurement, process)

    def add_record(self, record: dict[str, Any]) -> None:
        node_by_field: dict[str, str | None] = {}
        for field, default_label in PART_FIELDS.items():
            raw_id = record.get(field)
            if raw_id is None:
                continue
            label = (
                self._component_label(record)
                if field == "component_id"
                else default_label
            )
            node_by_field[field] = self.add_node(
                label,
                raw_id,
                {
                    "part_id": raw_id,
                    "part_type": record.get("component_type")
                    if field == "component_id"
                    else None,
                },
                field,
            )

        cylinder = node_by_field.get("cylinder_id")
        component = (
            node_by_field.get("component_id")
            or node_by_field.get("bottom_id")
            or node_by_field.get("rod_id")
        )
        self.add_relationship("ASSEMBLED_FROM", cylinder, component)
        parent = component or node_by_field.get("part_id") or cylinder

        bottom_ids = record.get("bottom_ids")
        if isinstance(bottom_ids, list):
            if len(bottom_ids) > 5:
                self.nodes_truncated = True
            for bottom_id in bottom_ids[:5]:
                self.add_node(
                    "CylinderBottom",
                    bottom_id,
                    {"part_id": bottom_id},
                    "bottom_ids",
                )

        process_runs = record.get("process_runs", [])
        if isinstance(process_runs, list):
            for item in process_runs:
                if isinstance(item, dict):
                    self._process_evidence(item, parent)

        top_level_run = record.get("run_id")
        if top_level_run:
            self._process_evidence(
                {
                    "run_id": top_level_run,
                    "equipment": record.get("equipment"),
                    "anomaly_code": record.get("anomaly_code"),
                    "anomaly_name": record.get("anomaly_name"),
                },
                parent,
            )

        measurements = record.get("quality_measurements", [])
        if isinstance(measurements, list):
            for item in measurements:
                if isinstance(item, dict):
                    self._measurement_evidence(item, parent)

        failures = record.get("failures", [])
        if isinstance(failures, list):
            for item in failures:
                if isinstance(item, dict):
                    failure = dict(item)
                    failure["qc_pass"] = False
                    self._measurement_evidence(failure, parent)

        pressure_id = record.get("final_pressure_measurement_id")
        if pressure_id:
            self._measurement_evidence(
                {
                    "measurement_id": pressure_id,
                    "feature": "pressure",
                    "value": record.get("final_pressure_value"),
                    "qc_pass": False,
                    "process_name": "assembly",
                },
                cylinder,
            )

        equipment = record.get("equipment")
        if equipment:
            self.add_node(
                "Equipment",
                equipment,
                {"name": equipment},
                "equipment",
            )
        anomaly_code = record.get(
            "anomaly_code", record.get("anomaly_class")
        )
        if anomaly_code is not None:
            self.add_node(
                "AnomalyClass",
                anomaly_code,
                {
                    "code": anomaly_code,
                    "name": record.get("anomaly_name"),
                },
                "anomaly_code",
            )

        equipment_id = record.get("equipment_id")
        equipment_node = self.add_node(
            "Equipment",
            equipment_id,
            {
                "equipment_id": equipment_id,
                "name": record.get("equipment_name"),
                "equipment_type": record.get("equipment_type"),
            },
            "equipment_id",
        )
        event_id = record.get("event_id")
        event_node = self.add_node(
            "MaintenanceEvent",
            event_id,
            {
                "event_id": event_id,
                "event_date": record.get("event_date"),
                "event_type": record.get("event_type"),
                "component": record.get("component"),
                "downtime_hours": record.get("downtime_hours"),
                "cost_usd": record.get("cost_usd"),
                "resolved": record.get("resolved"),
            },
            "event_id",
        )
        technician_id = record.get("technician_id")
        technician_node = self.add_node(
            "Technician",
            technician_id,
            {
                "technician_id": technician_id,
                "name": record.get("technician_name"),
            },
            "technician_id",
        )
        self.add_relationship(
            "HAS_MAINTENANCE", equipment_node, event_node
        )
        self.add_relationship("PERFORMED", technician_node, event_node)

    def build(self, records: Iterable[dict[str, Any]]) -> dict[str, Any]:
        materialized = list(records)
        for record in materialized:
            self.add_record(record)
        return {
            "nodes": list(self.nodes.values()),
            "relationships": list(self.relationships.values()),
            "node_count": len(self.nodes),
            "relationship_count": len(self.relationships),
            "truncated": {
                "nodes": self.nodes_truncated,
                "relationships": self.relationships_truncated,
            },
        }


def build_evidence_graph(
    records: list[dict[str, Any]],
    max_nodes: int = 120,
    max_relationships: int = 200,
    max_rows: int = 10,
) -> dict[str, Any]:
    selected_records = records[:max_rows]
    evidence = EvidenceBuilder(
        max_nodes=max_nodes,
        max_relationships=max_relationships,
    ).build(selected_records)
    evidence["source_row_count"] = len(records)
    evidence["visualized_row_count"] = len(selected_records)
    evidence["truncated"]["rows"] = len(records) > len(selected_records)
    return evidence


def format_agent_result(state: CypherState) -> dict[str, Any]:
    records = state.get("records", [])
    status = state.get("status", "failed")
    metadata = state.get("metadata", {})
    verified_hash = state.get("validated_statement_sha256", "")
    trace = state.get("trace", [])
    execution_verified = any(
        event.get("step") == "execute_cypher"
        and event.get("executed") is True
        and event.get("verified_statement_sha256") == verified_hash
        for event in trace
    )
    evidence = (
        build_evidence_graph(records)
        if status == "success"
        else {
            "nodes": [],
            "relationships": [],
            "node_count": 0,
            "relationship_count": 0,
            "truncated": {
                "nodes": False,
                "relationships": False,
                "rows": False,
            },
            "source_row_count": len(records),
            "visualized_row_count": 0,
        }
    )
    evidence["provenance"] = {
        "project_id": metadata.get("project_id"),
        "schema_version": metadata.get("schema_version"),
        "prompt_version": metadata.get("prompt_version"),
        "verified_statement_sha256": verified_hash or None,
    }
    return {
        "question": state.get("question", ""),
        "answer": _answer_for(state),
        "status": status,
        "cypher": state.get("statement", ""),
        "rows": records,
        "row_count": len(records),
        "metadata": metadata,
        "evidence": evidence,
        "validation": {
            "attempts": state.get("attempts", 0),
            "errors": state.get("errors", []),
            "trace": trace,
            "statement_history": state.get("statement_history", []),
            "elapsed_ms": state.get("elapsed_ms", 0),
            "verified_statement_sha256": verified_hash or None,
            "execution_verified": execution_verified,
        },
        "caveat": (
            "연결 관계와 집계를 기반으로 한 검토 후보이며 "
            "물리적 인과관계를 확정하지 않습니다."
            if status == "success"
            else None
        ),
    }
