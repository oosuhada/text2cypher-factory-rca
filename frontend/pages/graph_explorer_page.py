"""Interactive Neo4j graph exploration workspace."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from backend.app.schema_registry import SchemaRegistry
from frontend.app_services import ServiceBundle
from frontend.graph_explorer import (
    bound_evidence,
    build_visual_spec,
    graph_performance_policy,
    merge_catalog_payload,
    node_caption,
    selected_entity_details,
    shortest_path_ids,
    validate_project_scope,
)
from frontend.presentation import (
    evidence_to_dot,
    filter_evidence,
    flatten_rows_for_table,
    normalize_catalog_evidence,
)
from frontend.runtime import PROJECT_ROOT

def render_graph_explorer(services: ServiceBundle) -> None:
    project_id = st.session_state.get("active_project_id", "cip-dmd")
    st.subheader("Interactive Graph Explorer")
    st.caption(
        "노드를 검색하고 선택해 최대 3-hop까지 확장합니다. 모든 조회는 "
        f"현재 프로젝트 `{project_id}` 범위와 읽기 전용 계약을 따릅니다."
    )
    if services.graph is None:
        st.error("그래프 탐색 서비스가 구성되지 않았습니다.")
        return

    try:
        contract = SchemaRegistry(PROJECT_ROOT / "schemas").contract(
            project_id
        )
    except (KeyError, ValueError) as error:
        st.error(f"프로젝트 그래프 스키마를 불러오지 못했습니다: {error}")
        return
    identity_by_label = {
        row["label"]: row["identity_property"]
        for row in contract["node_identities"]
    }
    labels = tuple(identity_by_label)
    if not labels:
        st.info("탐색 가능한 노드 라벨이 없습니다.")
        return

    label_names = {
        "Cylinder": "완제품 Cylinder",
        "CylinderBottom": "구성품 Cylinder Bottom",
        "PistonRod": "구성품 Piston Rod",
        "Part": "전체 Part",
        "Process": "공정",
        "ProcessRun": "공정 실행",
        "Equipment": "장비",
        "AnomalyClass": "이상 유형",
        "QualityMeasurement": "품질 측정",
        "QualityFailure": "품질 불합격",
    }
    start_column, depth_column, limit_column = st.columns([2, 1, 1])
    with start_column:
        label = st.selectbox(
            "시작 노드 유형",
            options=labels,
            index=(
                labels.index("Cylinder")
                if "Cylinder" in labels
                else 0
            ),
            format_func=lambda value: label_names.get(value, value),
            key=f"graph-explorer-label-{project_id}",
        )
    with depth_column:
        default_depth = st.select_slider(
            "N-hop",
            options=(1, 2, 3),
            value=2,
            key=f"graph-explorer-depth-{project_id}",
        )
    with limit_column:
        result_limit = st.selectbox(
            "경로 제한",
            options=(25, 50, 75, 100),
            index=2,
            key=f"graph-explorer-limit-{project_id}",
        )

    with st.form(f"graph-node-search-form-{project_id}"):
        search_column, button_column = st.columns([4, 1])
        with search_column:
            search_term = st.text_input(
                "노드 검색",
                placeholder="ID, 이름, 공정, 이상 유형 또는 측정 항목 검색",
                label_visibility="collapsed",
            )
        with button_column:
            search_submitted = st.form_submit_button(
                "검색",
                type="primary",
                width="stretch",
            )
    if search_submitted:
        if not search_term.strip():
            st.warning("검색어를 입력하세요.")
        else:
            try:
                with st.spinner("일치하는 그래프 노드를 찾고 있습니다."):
                    st.session_state["explorer_search_result"] = (
                        services.graph.search_nodes(
                            label=label,
                            query=search_term.strip(),
                            limit=20,
                        )
                    )
            except Exception as error:
                st.error(f"노드 검색에 실패했습니다: {error}")

    search_result = st.session_state.get("explorer_search_result")
    if search_result and search_result.get("label") == label:
        nodes = search_result.get("nodes", [])
        if nodes:
            identity_property = search_result["identity_property"]

            def search_option_label(index: int) -> str:
                node = nodes[index]
                properties = node.get("properties", {})
                identity_value = properties.get(identity_property, node["id"])
                secondary = (
                    properties.get("display_name")
                    or properties.get("name")
                    or properties.get("part_type")
                    or properties.get("feature")
                )
                return " · ".join(
                    value
                    for value in (str(identity_value), str(secondary or ""))
                    if value
                )

            selection_column, depth_column, action_column = st.columns(
                [2, 1, 1]
            )
            with selection_column:
                selected_index = st.selectbox(
                    f"검색 결과 {len(nodes)}개",
                    options=range(len(nodes)),
                    format_func=search_option_label,
                    key=f"graph-search-selection-{project_id}-{label}",
                )
            with depth_column:
                st.caption("검색 결과를 시작점으로 사용합니다.")
            with action_column:
                explore_selected = st.button(
                    "그래프 열기",
                    type="primary",
                    width="stretch",
                    key=f"graph-open-search-{project_id}",
                )
            if explore_selected:
                selected_node = nodes[selected_index]
                selected_identity = str(
                    selected_node.get("properties", {}).get(
                        identity_property, ""
                    )
                )
                try:
                    with st.spinner("선택한 노드의 관계를 조회하고 있습니다."):
                        payload = services.graph.subgraph(
                            label=label,
                            identity=selected_identity,
                            depth=default_depth,
                            limit=result_limit,
                        )
                    validate_project_scope(payload, project_id)
                    st.session_state["explorer_result"] = {
                        "label": label,
                        "identity": selected_identity,
                        "depth": default_depth,
                        "payload": payload,
                    }
                    st.session_state["explorer_selected_node_ids"] = [
                        str(selected_node["id"])
                    ]
                    st.session_state[
                        "explorer_selected_relationship_ids"
                    ] = []
                    st.session_state["explorer_expansion_history"] = [
                        {
                            "label": label,
                            "identity": selected_identity,
                            "depth": default_depth,
                        }
                    ]
                    st.session_state["explorer_widget_revision"] += 1
                    st.rerun()
                except Exception as error:
                    st.error(f"관계 탐색에 실패했습니다: {error}")
        else:
            st.info("일치하는 노드가 없습니다. 다른 검색어를 입력해보세요.")

    with st.expander("정확한 ID로 바로 탐색"):
        with st.form(f"graph-explorer-form-{project_id}"):
            identity_column, depth_column = st.columns([1.5, 1])
            with identity_column:
                identity = st.text_input(
                    f"식별값 · {identity_by_label[label]}",
                    value="300002" if label == "Cylinder" else "",
                    placeholder="예: 300002",
                )
            with depth_column:
                st.caption(
                    f"{default_depth}-hop · 최대 {result_limit}개 경로"
                )
            submitted = st.form_submit_button(
                "관계 탐색",
                type="primary",
                width="stretch",
            )

    if submitted:
        if not identity.strip():
            st.warning("탐색할 식별값을 입력하세요.")
        else:
            try:
                with st.spinner("Neo4j에서 연결 관계를 조회하고 있습니다."):
                    payload = services.graph.subgraph(
                        label=label,
                        identity=identity.strip(),
                        depth=default_depth,
                        limit=result_limit,
                    )
                validate_project_scope(payload, project_id)
                st.session_state["explorer_result"] = {
                    "label": label,
                    "identity": identity.strip(),
                    "depth": default_depth,
                    "payload": payload,
                }
                root = payload.get("root")
                st.session_state["explorer_selected_node_ids"] = (
                    [str(root["id"])] if isinstance(root, dict) else []
                )
                st.session_state[
                    "explorer_selected_relationship_ids"
                ] = []
                st.session_state["explorer_expansion_history"] = [
                    {
                        "label": label,
                        "identity": identity.strip(),
                        "depth": default_depth,
                    }
                ]
                st.session_state["explorer_widget_revision"] += 1
                st.rerun()
            except Exception as error:
                st.error(f"관계 탐색에 실패했습니다: {error}")

    explorer_result = st.session_state.get("explorer_result")
    if not explorer_result:
        st.markdown(
            """
            <div class="p3-section-note">
              시작 예시: 노드 유형을 <b>Cylinder</b>로 선택하고
              <b>300002</b>를 입력하면 구성품·공정·장비·품질 관계를
              실제 그래프에서 확인할 수 있습니다.
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    payload = explorer_result["payload"]
    try:
        validate_project_scope(payload, project_id)
    except ValueError as error:
        st.error(str(error), icon="🔒")
        return
    if payload.get("root") is None:
        st.info(
            f"{explorer_result['label']} "
            f"'{explorer_result['identity']}'에 해당하는 노드가 없습니다."
        )
        return

    evidence = normalize_catalog_evidence(payload)
    available_labels = sorted(
        {str(node["label"]) for node in evidence["nodes"]}
    )
    available_relationships = sorted(
        {
            str(relationship["type"])
            for relationship in evidence["relationships"]
        }
    )
    filters = st.session_state.get("explorer_filters", {})
    with st.expander("표시 필터와 레이아웃", expanded=False):
        filter_column, relation_column, layout_column = st.columns(3)
        with filter_column:
            selected_labels = st.multiselect(
                "노드 유형",
                options=available_labels,
                default=[
                    value
                    for value in filters.get(
                        "labels", available_labels
                    )
                    if value in available_labels
                ],
                key=f"graph-label-filter-{project_id}",
            )
        with relation_column:
            selected_relationship_types = st.multiselect(
                "관계 유형",
                options=available_relationships,
                default=[
                    value
                    for value in filters.get(
                        "relationship_types",
                        available_relationships,
                    )
                    if value in available_relationships
                ],
                key=f"graph-relation-filter-{project_id}",
            )
        with layout_column:
            layout = st.selectbox(
                "레이아웃",
                options=(
                    "forcedirected",
                    "hierarchical",
                    "circular",
                    "grid",
                ),
                format_func=lambda value: {
                    "forcedirected": "Force directed",
                    "hierarchical": "Hierarchical",
                    "circular": "Circular",
                    "grid": "Grid",
                }[value],
                key=f"graph-layout-{project_id}",
            )
            include_isolated = st.toggle(
                "고립 노드 표시",
                value=bool(filters.get("include_isolated", True)),
                key=f"graph-isolated-{project_id}",
            )
    st.session_state["explorer_filters"] = {
        "labels": selected_labels,
        "relationship_types": selected_relationship_types,
        "include_isolated": include_isolated,
    }
    filtered = filter_evidence(
        evidence,
        labels=set(selected_labels),
        relationship_types=set(selected_relationship_types),
        include_isolated=include_isolated,
    )
    if not filtered["nodes"]:
        st.info(
            "현재 필터에 표시할 노드가 없습니다. 노드 유형 필터를 "
            "하나 이상 선택하세요."
        )
        return
    performance = graph_performance_policy(filtered["node_count"])
    filtered = bound_evidence(
        filtered,
        performance.recommended_limit,
        priority_node_ids=st.session_state.get(
            "explorer_selected_node_ids", []
        ),
    )
    visible_node_ids = {
        str(node["id"]) for node in filtered["nodes"]
    }
    visible_relationship_ids = {
        str(relationship.get("id", ""))
        for relationship in filtered["relationships"]
    }
    selected_node_ids = [
        node_id
        for node_id in st.session_state.get(
            "explorer_selected_node_ids", []
        )
        if node_id in visible_node_ids
    ]
    selected_relationship_ids = [
        relationship_id
        for relationship_id in st.session_state.get(
            "explorer_selected_relationship_ids", []
        )
        if relationship_id in visible_relationship_ids
    ]

    node_lookup = {
        str(node["id"]): node for node in filtered["nodes"]
    }
    focus_column, focus_action_column, path_column = st.columns(
        [3, 1, 1]
    )
    with focus_column:
        focus_node_id = st.selectbox(
            "화면에서 선택할 노드",
            options=tuple(node_lookup),
            index=(
                tuple(node_lookup).index(selected_node_ids[0])
                if selected_node_ids
                and selected_node_ids[0] in node_lookup
                else 0
            ),
            format_func=lambda node_id: node_caption(
                node_lookup[node_id], identity_by_label
            ).replace("\n", " · "),
            key=f"graph-focus-node-{project_id}",
        )
    with focus_action_column:
        st.write("")
        if st.button(
            "선택 동기화",
            width="stretch",
            key=f"graph-focus-action-{project_id}",
        ):
            st.session_state["explorer_selected_node_ids"] = [
                focus_node_id
            ]
            st.session_state[
                "explorer_selected_relationship_ids"
            ] = []
            st.session_state["explorer_widget_revision"] += 1
            st.rerun()
    with path_column:
        highlight_path = st.toggle(
            "루트 경로 강조",
            value=True,
            key=f"graph-path-highlight-{project_id}",
        )

    path_node_ids: set[str] = set()
    path_relationship_ids: set[str] = set()
    if highlight_path and selected_node_ids:
        path_node_ids, path_relationship_ids = shortest_path_ids(
            filtered,
            filtered.get("root_id"),
            selected_node_ids[0],
        )
    visual_spec = build_visual_spec(
        filtered,
        identity_by_label=identity_by_label,
        root_id=filtered.get("root_id"),
        selected_node_ids=selected_node_ids,
        selected_relationship_ids=selected_relationship_ids,
        highlighted_node_ids=path_node_ids,
        highlighted_relationship_ids=path_relationship_ids,
        label_mode=performance.label_mode,
    )

    node_metric, relation_metric, depth_metric, renderer_metric = st.columns(
        4
    )
    node_metric.metric("표시 노드", filtered["node_count"])
    relation_metric.metric("표시 관계", filtered["relationship_count"])
    depth_metric.metric("누적 확장", len(
        st.session_state.get("explorer_expansion_history", [])
    ))
    renderer_metric.metric("렌더러", performance.renderer.upper())
    st.caption(performance.message)
    if filtered.get("sampled_out_node_count"):
        st.warning(
            f"브라우저 안정성을 위해 "
            f"{filtered['sampled_out_node_count']:,}개 노드를 제외하고 "
            "루트·선택 노드를 우선 표시했습니다."
        )

    graph_column, detail_column = st.columns([3, 1])
    widget_selection = {
        "node_ids": selected_node_ids,
        "relationship_ids": selected_relationship_ids,
    }
    with graph_column:
        if not visual_spec["nodes"]:
            st.info("현재 필터에 표시할 노드가 없습니다.")
        else:
            try:
                from neo4j_viz import (
                    GraphSelection,
                    Node,
                    Relationship,
                    Renderer,
                    VisualizationGraph,
                )
                from neo4j_viz.streamlit import display_widget

                graph = VisualizationGraph(
                    nodes=[
                        Node(**node) for node in visual_spec["nodes"]
                    ],
                    relationships=[
                        Relationship(**relationship)
                        for relationship in visual_spec["relationships"]
                    ],
                )
                widget = graph.render_widget(
                    layout=layout,
                    renderer=(
                        Renderer.WEB_GL
                        if performance.renderer == "webgl"
                        else Renderer.CANVAS
                    ),
                    height="640px",
                    max_allowed_nodes=performance.recommended_limit,
                    theme="light",
                )
                widget.selected = GraphSelection(
                    nodeIds=selected_node_ids,
                    relationshipIds=selected_relationship_ids,
                )
                widget_key = (
                    f"graph-widget-{project_id}-{layout}-"
                    f"{st.session_state['explorer_widget_revision']}"
                )
                display_widget(widget, key=widget_key)
                widget_selection = {
                    "node_ids": list(widget.selected.nodeIds),
                    "relationship_ids": list(
                        widget.selected.relationshipIds
                    ),
                }
                st.caption(
                    "드래그로 이동 · 휠로 확대/축소 · 클릭으로 선택 · "
                    "우측 상단에서 레이아웃 전환"
                )
            except Exception as error:
                st.warning(
                    "인터랙티브 렌더러를 사용할 수 없어 안전한 "
                    f"Graphviz 보기로 전환했습니다: {error}"
                )
                st.graphviz_chart(
                    evidence_to_dot(filtered), width="stretch"
                )
    selected_node_ids = [
        node_id
        for node_id in widget_selection["node_ids"]
        if node_id in visible_node_ids
    ]
    selected_relationship_ids = [
        relationship_id
        for relationship_id in widget_selection["relationship_ids"]
        if relationship_id in visible_relationship_ids
    ]
    st.session_state["explorer_selected_node_ids"] = selected_node_ids
    st.session_state[
        "explorer_selected_relationship_ids"
    ] = selected_relationship_ids
    details = selected_entity_details(
        filtered,
        selected_node_ids,
        selected_relationship_ids,
    )
    with detail_column:
        st.markdown("#### 선택 상세")
        if details["nodes"]:
            selected_node = details["nodes"][0]
            st.markdown(
                f"**{node_caption(selected_node, identity_by_label)}**"
                .replace("\n", " · ")
            )
            st.json(selected_node.get("properties") or {}, expanded=True)
            selected_label = str(selected_node["label"])
            selected_identity_property = identity_by_label.get(
                selected_label
            )
            selected_identity = (
                (selected_node.get("properties") or {}).get(
                    selected_identity_property
                )
                if selected_identity_property
                else None
            )
            expand_depth = st.select_slider(
                "이 노드에서 확장",
                options=(1, 2, 3),
                value=1,
                key=f"graph-expand-depth-{project_id}",
            )
            if st.button(
                f"{expand_depth}-hop 추가",
                type="primary",
                width="stretch",
                key=f"graph-expand-action-{project_id}",
                disabled=selected_identity in (None, ""),
            ):
                try:
                    with st.spinner("선택 노드의 이웃을 확장합니다."):
                        incoming = services.graph.subgraph(
                            label=selected_label,
                            identity=str(selected_identity),
                            depth=expand_depth,
                            limit=result_limit,
                        )
                    validate_project_scope(incoming, project_id)
                    explorer_result["payload"] = merge_catalog_payload(
                        payload, incoming
                    )
                    st.session_state[
                        "explorer_result"
                    ] = explorer_result
                    st.session_state[
                        "explorer_expansion_history"
                    ].append(
                        {
                            "label": selected_label,
                            "identity": str(selected_identity),
                            "depth": expand_depth,
                        }
                    )
                    st.rerun()
                except Exception as error:
                    st.error(f"이웃 확장에 실패했습니다: {error}")
        elif details["relationships"]:
            relationship = details["relationships"][0]
            st.markdown(f"**:{relationship.get('type', 'RELATED')}**")
            st.caption(
                f"{relationship['source']} → {relationship['target']}"
            )
            st.json(
                relationship.get("properties") or {},
                expanded=True,
            )
        else:
            st.info("그래프에서 노드나 관계를 클릭하세요.")

    if evidence.get("truncated"):
        st.warning(
            f"서버 안전 한도에 따라 최대 {result_limit}개 경로만 "
            "조회했습니다. 검색어·필터·N-hop을 좁혀 탐색하세요."
        )
    node_tab, relationship_tab, history_tab = st.tabs(
        ["노드 목록", "관계 목록", "확장 이력"]
    )
    with node_tab:
        st.dataframe(
            pd.DataFrame(flatten_rows_for_table(filtered["nodes"])),
            width="stretch",
            hide_index=True,
        )
    with relationship_tab:
        if filtered["relationships"]:
            st.dataframe(
                pd.DataFrame(
                    flatten_rows_for_table(filtered["relationships"])
                ),
                width="stretch",
                hide_index=True,
            )
        else:
            st.info("선택한 깊이에서 연결 관계를 찾지 못했습니다.")
    with history_tab:
        st.dataframe(
            pd.DataFrame(
                st.session_state.get(
                    "explorer_expansion_history", []
                )
            ),
            width="stretch",
            hide_index=True,
        )
