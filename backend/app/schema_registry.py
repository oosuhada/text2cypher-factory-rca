"""Versioned graph-schema manifests and LLM context generation."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
from typing import Any

import yaml


NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
PROPERTY_TYPES = {
    "STRING",
    "INTEGER",
    "FLOAT",
    "BOOLEAN",
    "DATE",
    "DATETIME",
}
CARDINALITIES = {
    "ONE_TO_ONE",
    "ONE_TO_MANY",
    "MANY_TO_ONE",
    "MANY_TO_MANY",
}


class SchemaRegistry:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def _path(self, project_id: str) -> Path:
        if not re.fullmatch(r"[a-z][a-z0-9-]{2,62}", project_id):
            raise ValueError("유효하지 않은 project_id입니다.")
        return self.root / project_id / "schema.yml"

    def load(self, project_id: str) -> dict[str, Any]:
        path = self._path(project_id)
        if not path.exists():
            raise KeyError(f"스키마 manifest가 없습니다: {project_id}")
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("스키마 manifest는 객체여야 합니다.")
        self.validate(payload, expected_project_id=project_id)
        return deepcopy(payload)

    def save(self, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        document = deepcopy(payload)
        document["project_id"] = project_id
        self.validate(document, expected_project_id=project_id)
        path = self._path(project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            yaml.safe_dump(
                document,
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        temporary.replace(path)
        return self.load(project_id)

    def validate(
        self,
        payload: dict[str, Any],
        *,
        expected_project_id: str | None = None,
    ) -> None:
        project_id = payload.get("project_id")
        if expected_project_id and project_id != expected_project_id:
            raise ValueError("manifest project_id가 요청 프로젝트와 다릅니다.")
        if not payload.get("version"):
            raise ValueError("schema version이 필요합니다.")
        if "source_version" in payload and not str(
            payload["source_version"]
        ).strip():
            raise ValueError("source_version은 비어 있을 수 없습니다.")
        nodes = payload.get("nodes")
        relationships = payload.get("relationships")
        if not isinstance(nodes, list) or not nodes:
            raise ValueError("nodes는 비어 있지 않은 배열이어야 합니다.")
        if not isinstance(relationships, list):
            raise ValueError("relationships는 배열이어야 합니다.")
        labels: set[str] = set()
        node_by_label: dict[str, dict[str, Any]] = {}
        for node in nodes:
            label = str(node.get("label", ""))
            if not NAME_PATTERN.fullmatch(label):
                raise ValueError(f"유효하지 않은 노드 라벨입니다: {label}")
            if label in labels:
                raise ValueError(f"중복 노드 라벨입니다: {label}")
            labels.add(label)
            node_by_label[label] = node
            properties = node.get("properties") or {}
            if not isinstance(properties, dict):
                raise ValueError(f"{label}.properties는 객체여야 합니다.")
            for name, property_type in properties.items():
                self._validate_property(label, name, property_type)
            source = node.get("source")
            if source is not None and not isinstance(source, dict):
                raise ValueError(f"{label}.source는 객체여야 합니다.")
        for node in nodes:
            label = node["label"]
            extends = node.get("extends")
            if extends and extends not in labels:
                raise ValueError(f"{label}의 extends 대상이 없습니다: {extends}")
            identity = node.get("identity")
            inherited = (
                (node_by_label.get(extends) or {}).get("properties", {})
                if extends
                else {}
            )
            if identity not in (node.get("properties") or {}) and identity not in inherited:
                raise ValueError(
                    f"{label} identity 속성을 찾을 수 없습니다: {identity}"
                )
            required_properties = node.get("required_properties", [])
            if not isinstance(required_properties, list):
                raise ValueError(
                    f"{label}.required_properties는 배열이어야 합니다."
                )
            available = set(node.get("properties") or {}) | set(inherited)
            missing_required = set(required_properties) - available
            if missing_required:
                raise ValueError(
                    f"{label} 필수 속성을 찾을 수 없습니다: "
                    f"{sorted(missing_required)}"
                )
        for label in labels:
            inheritance_chain: set[str] = set()
            current: str | None = label
            while current is not None:
                if current in inheritance_chain:
                    raise ValueError(
                        f"노드 상속 순환이 발생했습니다: {label}"
                    )
                inheritance_chain.add(current)
                current = node_by_label[current].get("extends")
        relationship_types: set[str] = set()
        for relationship in relationships:
            rel_type = str(relationship.get("type", ""))
            if not NAME_PATTERN.fullmatch(rel_type):
                raise ValueError(f"유효하지 않은 관계 타입입니다: {rel_type}")
            if rel_type in relationship_types:
                raise ValueError(f"중복 관계 타입입니다: {rel_type}")
            relationship_types.add(rel_type)
            if relationship.get("source") not in labels:
                raise ValueError(f"{rel_type} source 라벨이 없습니다.")
            targets = relationship.get("targets")
            if not isinstance(targets, list) or not targets:
                raise ValueError(f"{rel_type} targets가 필요합니다.")
            if any(target not in labels for target in targets):
                raise ValueError(f"{rel_type} target 라벨이 없습니다.")
            cardinality = relationship.get(
                "cardinality", "MANY_TO_MANY"
            )
            if cardinality not in CARDINALITIES:
                raise ValueError(
                    f"{rel_type} cardinality가 유효하지 않습니다: "
                    f"{cardinality}"
                )
            properties = relationship.get("properties") or {}
            if not isinstance(properties, dict):
                raise ValueError(f"{rel_type}.properties는 객체여야 합니다.")
            for name, property_type in properties.items():
                self._validate_property(rel_type, name, property_type)
            required_properties = relationship.get(
                "required_properties", []
            )
            if not isinstance(required_properties, list):
                raise ValueError(
                    f"{rel_type}.required_properties는 배열이어야 합니다."
                )
            missing_required = set(required_properties) - set(properties)
            if missing_required:
                raise ValueError(
                    f"{rel_type} 필수 속성을 찾을 수 없습니다: "
                    f"{sorted(missing_required)}"
                )
            source = relationship.get("source_ref")
            if source is not None and not isinstance(source, dict):
                raise ValueError(f"{rel_type}.source_ref는 객체여야 합니다.")
        scenario_report = self.validate_query_scenarios(payload)
        if scenario_report["status"] == "FAIL":
            joined = "; ".join(scenario_report["errors"])
            raise ValueError(f"질의 관점 스키마 검증 실패: {joined}")

    @staticmethod
    def _validate_property(
        owner: str, name: Any, property_type: Any
    ) -> None:
        if not NAME_PATTERN.fullmatch(str(name)):
            raise ValueError(f"유효하지 않은 속성명입니다: {name}")
        if str(property_type).upper() not in PROPERTY_TYPES:
            raise ValueError(
                f"{owner}.{name}의 지원하지 않는 속성 타입입니다: "
                f"{property_type}"
            )

    @staticmethod
    def _node_properties(
        node_by_label: dict[str, dict[str, Any]], label: str
    ) -> set[str]:
        node = node_by_label[label]
        properties = set(node.get("properties") or {})
        extends = node.get("extends")
        if extends:
            properties |= SchemaRegistry._node_properties(
                node_by_label, extends
            )
        return properties

    def validate_query_scenarios(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        scenarios = payload.get("query_scenarios") or []
        if not isinstance(scenarios, list):
            return {
                "status": "FAIL",
                "scenario_count": 0,
                "passed_count": 0,
                "errors": ["query_scenarios는 배열이어야 합니다."],
                "scenarios": [],
            }
        node_by_label = {
            str(node.get("label", "")): node
            for node in payload.get("nodes") or []
        }
        relationship_types = {
            str(relationship.get("type", ""))
            for relationship in payload.get("relationships") or []
        }
        errors: list[str] = []
        details: list[dict[str, Any]] = []
        scenario_ids: set[str] = set()
        for index, scenario in enumerate(scenarios, start=1):
            scenario_errors: list[str] = []
            if not isinstance(scenario, dict):
                errors.append(f"query_scenarios[{index}]는 객체여야 합니다.")
                continue
            scenario_id = str(scenario.get("id", f"scenario-{index}"))
            question = str(scenario.get("question", "")).strip()
            if scenario_id in scenario_ids:
                scenario_errors.append(f"중복 scenario id: {scenario_id}")
            scenario_ids.add(scenario_id)
            if not question:
                scenario_errors.append("question이 비어 있습니다.")
            required_nodes = scenario.get("required_nodes", [])
            required_relationships = scenario.get(
                "required_relationships", []
            )
            required_properties = scenario.get(
                "required_properties", []
            )
            for field, value in (
                ("required_nodes", required_nodes),
                ("required_relationships", required_relationships),
                ("required_properties", required_properties),
            ):
                if not isinstance(value, list):
                    scenario_errors.append(f"{field}는 배열이어야 합니다.")
            if not scenario_errors:
                missing_nodes = set(required_nodes) - set(node_by_label)
                missing_relationships = (
                    set(required_relationships) - relationship_types
                )
                if missing_nodes:
                    scenario_errors.append(
                        f"없는 노드: {sorted(missing_nodes)}"
                    )
                if missing_relationships:
                    scenario_errors.append(
                        f"없는 관계: {sorted(missing_relationships)}"
                    )
                for reference in required_properties:
                    if (
                        not isinstance(reference, str)
                        or "." not in reference
                    ):
                        scenario_errors.append(
                            f"잘못된 속성 참조: {reference}"
                        )
                        continue
                    label, property_name = reference.split(".", 1)
                    if label not in node_by_label:
                        scenario_errors.append(
                            f"속성 참조 노드가 없음: {reference}"
                        )
                    elif property_name not in self._node_properties(
                        node_by_label, label
                    ):
                        scenario_errors.append(
                            f"속성이 없음: {reference}"
                        )
            details.append(
                {
                    "id": scenario_id,
                    "question": question,
                    "status": "PASS" if not scenario_errors else "FAIL",
                    "errors": scenario_errors,
                }
            )
            errors.extend(
                f"{scenario_id}: {error}" for error in scenario_errors
            )
        return {
            "status": "PASS" if not errors else "FAIL",
            "scenario_count": len(scenarios),
            "passed_count": sum(
                detail["status"] == "PASS" for detail in details
            ),
            "errors": errors,
            "scenarios": details,
        }

    def context(self, project_id: str) -> str:
        manifest = self.load(project_id)
        lines = ["Node properties:"]
        for node in manifest["nodes"]:
            properties = ", ".join(
                f"{name}: {property_type}"
                for name, property_type in (node.get("properties") or {}).items()
            )
            if node.get("extends"):
                lines.append(f"{node['label']} extends {node['extends']}")
            elif properties:
                lines.append(f"{node['label']} {{{properties}}}")
        lines.append("")
        lines.append("Relationships:")
        for relationship in manifest["relationships"]:
            targets = "|".join(relationship["targets"])
            properties = relationship.get("properties") or {}
            property_text = ""
            if properties:
                pairs = ", ".join(
                    f"{name}: {kind}" for name, kind in properties.items()
                )
                property_text = f" {{{pairs}}}"
            lines.append(
                f"(:{relationship['source']})-[:{relationship['type']}"
                f"{property_text}]->(:{targets})"
                f" cardinality={relationship.get('cardinality', 'MANY_TO_MANY')}"
            )
        for key, values in (manifest.get("domain_values") or {}).items():
            lines.extend(["", f"Allowed {key}:", ", ".join(map(str, values))])
        rules = manifest.get("output_rules") or []
        if rules:
            lines.extend(["", "Output contract:"])
            lines.extend(f"- {rule}" for rule in rules)
        scenarios = manifest.get("query_scenarios") or []
        if scenarios:
            lines.extend(["", "Validated business question paths:"])
            for scenario in scenarios:
                relationships = ", ".join(
                    scenario.get("required_relationships") or []
                )
                suffix = (
                    f" via {relationships}" if relationships else ""
                )
                lines.append(
                    f"- {scenario['id']}: {scenario['question']}{suffix}"
                )
        return "\n".join(lines).strip()

    def contract(self, project_id: str) -> dict[str, Any]:
        manifest = self.load(project_id)
        return {
            "project_id": project_id,
            "schema_version": str(manifest["version"]),
            "source_version": manifest.get("source_version"),
            "title": manifest.get("title", project_id),
            "schema_context": self.context(project_id),
            "node_identities": [
                {
                    "label": node["label"],
                    "identity_property": node["identity"],
                }
                for node in manifest["nodes"]
            ],
            "relationship_types": [
                relationship["type"]
                for relationship in manifest["relationships"]
            ],
            "nodes": manifest["nodes"],
            "relationships": manifest["relationships"],
            "query_scenarios": manifest.get("query_scenarios", []),
            "query_validation": self.validate_query_scenarios(manifest),
        }
