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
                if not NAME_PATTERN.fullmatch(str(name)):
                    raise ValueError(f"유효하지 않은 속성명입니다: {name}")
                if str(property_type).upper() not in PROPERTY_TYPES:
                    raise ValueError(
                        f"지원하지 않는 속성 타입입니다: {property_type}"
                    )
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
            )
        for key, values in (manifest.get("domain_values") or {}).items():
            lines.extend(["", f"Allowed {key}:", ", ".join(map(str, values))])
        rules = manifest.get("output_rules") or []
        if rules:
            lines.extend(["", "Output contract:"])
            lines.extend(f"- {rule}" for rule in rules)
        return "\n".join(lines).strip()

    def contract(self, project_id: str) -> dict[str, Any]:
        manifest = self.load(project_id)
        return {
            "project_id": project_id,
            "schema_version": str(manifest["version"]),
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
        }

