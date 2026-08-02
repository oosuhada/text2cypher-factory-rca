"""Pure presentation helpers used by Streamlit and tests."""

from __future__ import annotations

import csv
import io
import json
from typing import Any


NODE_COLORS = {
    "Cylinder": "#0F766E",
    "CylinderBottom": "#2563EB",
    "PistonRod": "#4F46E5",
    "Part": "#475569",
    "ProcessRun": "#D97706",
    "Process": "#F59E0B",
    "Equipment": "#7C3AED",
    "AnomalyClass": "#DC2626",
    "QualityMeasurement": "#059669",
    "QualityFailure": "#E11D48",
}


def _dot_string(value: Any) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def filter_evidence(
    evidence: dict[str, Any],
    labels: set[str] | None = None,
    relationship_types: set[str] | None = None,
    include_isolated: bool = True,
) -> dict[str, Any]:
    selected_nodes = [
        node
        for node in evidence.get("nodes", [])
        if labels is None or node.get("label") in labels
    ]
    selected_ids = {node["id"] for node in selected_nodes}
    selected_relationships = [
        relationship
        for relationship in evidence.get("relationships", [])
        if relationship["source"] in selected_ids
        and relationship["target"] in selected_ids
        and (
            relationship_types is None
            or relationship.get("type") in relationship_types
        )
    ]
    if not include_isolated:
        connected_ids = {
            endpoint
            for relationship in selected_relationships
            for endpoint in (
                relationship["source"],
                relationship["target"],
            )
        }
        selected_nodes = [
            node for node in selected_nodes if node["id"] in connected_ids
        ]
    return {
        **evidence,
        "nodes": selected_nodes,
        "relationships": selected_relationships,
        "node_count": len(selected_nodes),
        "relationship_count": len(selected_relationships),
    }


def normalize_catalog_evidence(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Convert GraphCatalogService nodes to the shared evidence contract."""

    nodes = []
    for node in payload.get("nodes", []):
        labels = list(node.get("labels", []))
        label = next(
            (candidate for candidate in labels if candidate != "Part"),
            labels[0] if labels else "Node",
        )
        nodes.append({**node, "label": label})
    relationships = list(payload.get("relationships", []))
    return {
        "nodes": nodes,
        "relationships": relationships,
        "node_count": len(nodes),
        "relationship_count": len(relationships),
        "truncated": payload.get("truncated", False),
    }


def evidence_to_dot(
    evidence: dict[str, Any], rankdir: str = "LR"
) -> str:
    if rankdir not in {"LR", "TB"}:
        raise ValueError("rankdir must be LR or TB")
    lines = [
        "digraph Evidence {",
        f'graph [rankdir="{rankdir}", bgcolor="transparent", '
        'pad="0.2", nodesep="0.35"];',
        'node [shape="box", style="rounded,filled", fontname="Arial", '
        'fontcolor="white", fontsize="10", margin="0.12"];',
        'edge [fontname="Arial", fontsize="8", color="#64748B", '
        'fontcolor="#475569", arrowsize="0.7"];',
    ]
    for node in evidence.get("nodes", []):
        label = str(node.get("label", "Node"))
        properties = node.get("properties", {})
        primary = (
            properties.get("part_id")
            or properties.get("name")
            or properties.get("run_id")
            or properties.get("measurement_id")
            or properties.get("code")
            or str(node.get("id", "")).split(":", 1)[-1]
        )
        display = f"{label}\\n{primary}"
        color = NODE_COLORS.get(label, "#475569")
        lines.append(
            f"{_dot_string(node['id'])} "
            f"[label={_dot_string(display)}, fillcolor={_dot_string(color)}];"
        )
    for relationship in evidence.get("relationships", []):
        lines.append(
            f"{_dot_string(relationship['source'])} -> "
            f"{_dot_string(relationship['target'])} "
            f"[label={_dot_string(relationship['type'])}];"
        )
    lines.append("}")
    return "\n".join(lines)


def flatten_rows_for_table(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            key: (
                json.dumps(value, ensure_ascii=False)
                if isinstance(value, (dict, list))
                else value
            )
            for key, value in row.items()
        }
        for row in rows
    ]


def rows_to_csv(rows: list[dict[str, Any]]) -> bytes:
    flattened = flatten_rows_for_table(rows)
    if not flattened:
        return b""
    fields = list(
        dict.fromkeys(key for row in flattened for key in row.keys())
    )
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    writer.writerows(flattened)
    return buffer.getvalue().encode("utf-8-sig")
