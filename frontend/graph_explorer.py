"""Pure graph-explorer state, styling, and safety helpers."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Iterable


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
DEFAULT_NODE_COLOR = "#475569"
PATH_NODE_COLOR = "#E11D48"
ROOT_NODE_COLOR = "#0F766E"
SELECTED_NODE_COLOR = "#7C3AED"
PATH_RELATIONSHIP_COLOR = "#E11D48"
DEFAULT_RELATIONSHIP_COLOR = "#94A3B8"


@dataclass(frozen=True)
class PerformancePolicy:
    renderer: str
    label_mode: str
    sampling_required: bool
    recommended_limit: int
    message: str


def graph_performance_policy(node_count: int) -> PerformancePolicy:
    """Return explicit rendering boundaries for 1k and 10k workloads."""

    if node_count <= 1_000:
        return PerformancePolicy(
            renderer="canvas",
            label_mode="full",
            sampling_required=False,
            recommended_limit=1_000,
            message="1천 노드 이하는 전체 라벨 Canvas 탐색 범위입니다.",
        )
    if node_count <= 10_000:
        return PerformancePolicy(
            renderer="webgl",
            label_mode="selected",
            sampling_required=True,
            recommended_limit=2_000,
            message=(
                "1천 노드 초과는 WebGL과 서버 샘플링을 사용하고 "
                "선택한 노드만 라벨을 표시합니다."
            ),
        )
    return PerformancePolicy(
        renderer="webgl",
        label_mode="none",
        sampling_required=True,
        recommended_limit=1_000,
        message=(
            "1만 노드 초과는 직접 렌더링하지 않습니다. 집계·검색·"
            "N-hop 제한으로 결과를 1천 노드 이하로 줄여야 합니다."
        ),
    )


def bound_evidence(
    evidence: dict[str, Any],
    limit: int,
    *,
    priority_node_ids: Iterable[str] = (),
) -> dict[str, Any]:
    """Bound a rendered graph while preserving root and selected nodes first."""

    if limit < 1:
        raise ValueError("limit은 1 이상이어야 합니다.")
    nodes = list(evidence.get("nodes", []))
    if len(nodes) <= limit:
        return {
            **evidence,
            "sampled_out_node_count": 0,
        }
    priority = [
        str(value)
        for value in (
            evidence.get("root_id"),
            *tuple(priority_node_ids),
        )
        if value
    ]
    node_by_id = {str(node["id"]): node for node in nodes}
    ordered_ids = list(
        dict.fromkeys(
            [
                *priority,
                *(str(node["id"]) for node in nodes),
            ]
        )
    )
    kept_ids = {
        node_id
        for node_id in ordered_ids[:limit]
        if node_id in node_by_id
    }
    kept_nodes = [
        node for node in nodes if str(node["id"]) in kept_ids
    ]
    kept_relationships = [
        relationship
        for relationship in evidence.get("relationships", [])
        if str(relationship["source"]) in kept_ids
        and str(relationship["target"]) in kept_ids
    ]
    return {
        **evidence,
        "nodes": kept_nodes,
        "relationships": kept_relationships,
        "node_count": len(kept_nodes),
        "relationship_count": len(kept_relationships),
        "truncated": True,
        "sampled_out_node_count": len(nodes) - len(kept_nodes),
    }


def merge_catalog_payload(
    current: dict[str, Any] | None,
    incoming: dict[str, Any],
) -> dict[str, Any]:
    """Merge independently fetched neighborhoods without duplicating entities."""

    if not current:
        return {
            **incoming,
            "nodes": list(incoming.get("nodes", [])),
            "relationships": list(incoming.get("relationships", [])),
        }
    nodes = {
        str(node["id"]): node
        for node in current.get("nodes", [])
    }
    nodes.update(
        {
            str(node["id"]): node
            for node in incoming.get("nodes", [])
        }
    )
    relationships = {
        str(relationship["id"]): relationship
        for relationship in current.get("relationships", [])
    }
    relationships.update(
        {
            str(relationship["id"]): relationship
            for relationship in incoming.get("relationships", [])
        }
    )
    return {
        **current,
        "root": current.get("root") or incoming.get("root"),
        "nodes": list(nodes.values()),
        "relationships": list(relationships.values()),
        "node_count": len(nodes),
        "relationship_count": len(relationships),
        "depth": max(
            int(current.get("depth", 0)),
            int(incoming.get("depth", 0)),
        ),
        "truncated": bool(
            current.get("truncated") or incoming.get("truncated")
        ),
    }


def validate_project_scope(
    payload: dict[str, Any],
    project_id: str,
) -> None:
    """Reject cross-project entities before they reach the visualization."""

    if project_id == "cip-dmd":
        return
    invalid_nodes = [
        str(node.get("id"))
        for node in payload.get("nodes", [])
        if (node.get("properties") or {}).get("project_id") != project_id
    ]
    invalid_relationships = [
        str(relationship.get("id"))
        for relationship in payload.get("relationships", [])
        if (relationship.get("properties") or {}).get("project_id")
        != project_id
    ]
    if invalid_nodes or invalid_relationships:
        raise ValueError(
            "프로젝트 범위를 벗어난 그래프 결과가 차단되었습니다. "
            f"nodes={invalid_nodes[:3]}, "
            f"relationships={invalid_relationships[:3]}"
        )


def shortest_path_ids(
    evidence: dict[str, Any],
    source_id: str | None,
    target_id: str | None,
) -> tuple[set[str], set[str]]:
    """Find one shortest undirected path in the currently visible evidence."""

    if not source_id or not target_id:
        return set(), set()
    if source_id == target_id:
        return {source_id}, set()
    adjacency: dict[str, list[tuple[str, str]]] = {}
    for relationship in evidence.get("relationships", []):
        relationship_id = str(relationship.get("id", ""))
        source = str(relationship["source"])
        target = str(relationship["target"])
        adjacency.setdefault(source, []).append((target, relationship_id))
        adjacency.setdefault(target, []).append((source, relationship_id))
    queue = deque([source_id])
    parents: dict[str, tuple[str, str] | None] = {source_id: None}
    while queue:
        current = queue.popleft()
        for neighbor, relationship_id in adjacency.get(current, []):
            if neighbor in parents:
                continue
            parents[neighbor] = (current, relationship_id)
            if neighbor == target_id:
                queue.clear()
                break
            queue.append(neighbor)
    if target_id not in parents:
        return set(), set()
    node_ids = {target_id}
    relationship_ids: set[str] = set()
    cursor = target_id
    while parents[cursor] is not None:
        parent, relationship_id = parents[cursor]  # type: ignore[misc]
        node_ids.add(parent)
        relationship_ids.add(relationship_id)
        cursor = parent
    return node_ids, relationship_ids


def _first_label(node: dict[str, Any]) -> str:
    label = node.get("label")
    if label:
        return str(label)
    labels = list(node.get("labels", []))
    return str(labels[0]) if labels else "Node"


def node_caption(
    node: dict[str, Any],
    identity_by_label: dict[str, str] | None = None,
) -> str:
    label = _first_label(node)
    properties = node.get("properties") or {}
    identity_property = (identity_by_label or {}).get(label)
    primary = (
        properties.get(identity_property) if identity_property else None
    ) or next(
        (
            properties.get(key)
            for key in (
                "part_id",
                "run_id",
                "equipment_id",
                "measurement_id",
                "code",
                "display_name",
                "name",
            )
            if properties.get(key) not in (None, "")
        ),
        str(node.get("id", "")),
    )
    return f"{label}\n{primary}"


def build_visual_spec(
    evidence: dict[str, Any],
    *,
    identity_by_label: dict[str, str] | None = None,
    root_id: str | None = None,
    selected_node_ids: Iterable[str] = (),
    selected_relationship_ids: Iterable[str] = (),
    highlighted_node_ids: Iterable[str] = (),
    highlighted_relationship_ids: Iterable[str] = (),
    label_mode: str = "full",
) -> dict[str, list[dict[str, Any]]]:
    """Create renderer-neutral nodes and edges with selection/path styling."""

    selected_nodes = set(map(str, selected_node_ids))
    selected_relationships = set(map(str, selected_relationship_ids))
    highlighted_nodes = set(map(str, highlighted_node_ids))
    highlighted_relationships = set(
        map(str, highlighted_relationship_ids)
    )
    nodes = []
    for node in evidence.get("nodes", []):
        node_id = str(node["id"])
        label = _first_label(node)
        is_selected = node_id in selected_nodes
        is_highlighted = node_id in highlighted_nodes
        color = NODE_COLORS.get(label, DEFAULT_NODE_COLOR)
        if node_id == root_id:
            color = ROOT_NODE_COLOR
        if is_highlighted:
            color = PATH_NODE_COLOR
        if is_selected:
            color = SELECTED_NODE_COLOR
        caption = (
            node_caption(node, identity_by_label)
            if label_mode == "full" or is_selected
            else label
            if label_mode == "selected"
            else ""
        )
        nodes.append(
            {
                "id": node_id,
                "caption": caption,
                "color": color,
                "size": 34 if is_selected else 28 if is_highlighted else 22,
                "properties": {
                    "label": label,
                    **(node.get("properties") or {}),
                },
            }
        )
    relationships = []
    for relationship in evidence.get("relationships", []):
        relationship_id = str(relationship.get("id", ""))
        is_selected = relationship_id in selected_relationships
        is_highlighted = (
            relationship_id in highlighted_relationships
        )
        relationships.append(
            {
                "id": relationship_id,
                "source": str(relationship["source"]),
                "target": str(relationship["target"]),
                "caption": str(relationship.get("type", "")),
                "color": (
                    PATH_RELATIONSHIP_COLOR
                    if is_highlighted
                    else "#7C3AED"
                    if is_selected
                    else DEFAULT_RELATIONSHIP_COLOR
                ),
                "width": 5 if is_selected else 4 if is_highlighted else 2,
                "properties": {
                    "type": relationship.get("type"),
                    **(relationship.get("properties") or {}),
                },
            }
        )
    return {"nodes": nodes, "relationships": relationships}


def selected_entity_details(
    evidence: dict[str, Any],
    selected_node_ids: Iterable[str],
    selected_relationship_ids: Iterable[str],
) -> dict[str, list[dict[str, Any]]]:
    node_ids = set(map(str, selected_node_ids))
    relationship_ids = set(map(str, selected_relationship_ids))
    return {
        "nodes": [
            node
            for node in evidence.get("nodes", [])
            if str(node.get("id")) in node_ids
        ],
        "relationships": [
            relationship
            for relationship in evidence.get("relationships", [])
            if str(relationship.get("id")) in relationship_ids
        ],
    }
