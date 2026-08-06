"""Legacy full-page evidence presentation."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from frontend.pages.query_studio import render_response_summary
from frontend.presentation import evidence_to_dot, filter_evidence, flatten_rows_for_table, rows_to_csv

def render_evidence_tab() -> None:
    st.subheader("답변 근거")
    result = st.session_state.get("last_result")
    if not result:
        st.info(
            "Query Studio에서 질문을 실행하면 결과표와 관계 경로가 표시됩니다.",
            icon="ℹ️",
        )
        return

    render_response_summary(result)
    row_metric, node_metric, rel_metric, attempt_metric = st.columns(4)
    row_metric.metric("결과 행", result.get("row_count", 0))
    evidence = result.get("evidence", {})
    node_metric.metric("근거 노드", evidence.get("node_count", 0))
    rel_metric.metric("근거 관계", evidence.get("relationship_count", 0))
    attempt_metric.metric(
        "검증 시도", result.get("validation", {}).get("attempts", 0)
    )

    table_tab, graph_tab, cypher_tab, trace_tab = st.tabs(
        ["결과표", "부분 그래프", "Cypher", "검증 이력"]
    )
    with table_tab:
        rows = result.get("rows", [])
        if rows:
            flattened = flatten_rows_for_table(rows)
            st.dataframe(
                pd.DataFrame(flattened),
                width="stretch",
                hide_index=True,
            )
            st.download_button(
                "CSV 다운로드",
                data=rows_to_csv(rows),
                file_name="p3_query_result.csv",
                mime="text/csv",
            )
        else:
            st.info("표시할 결과 행이 없습니다.")

    with graph_tab:
        if evidence.get("nodes"):
            available_labels = sorted(
                {node["label"] for node in evidence["nodes"]}
            )
            available_relationships = sorted(
                {
                    relationship["type"]
                    for relationship in evidence.get("relationships", [])
                }
            )
            filter_column, relationship_column, layout_column = st.columns(
                [2, 2, 1]
            )
            selected_labels = filter_column.multiselect(
                "노드 유형",
                available_labels,
                default=available_labels,
                key="evidence-label-filter",
            )
            selected_relationships = relationship_column.multiselect(
                "관계 유형",
                available_relationships,
                default=available_relationships,
                key="evidence-relationship-filter",
            )
            layout = layout_column.radio(
                "방향",
                options=("좌→우", "위→아래"),
                horizontal=True,
                key="evidence-layout",
            )
            include_isolated = st.checkbox(
                "연결되지 않은 근거 노드도 표시",
                value=True,
                key="evidence-isolated",
            )
            filtered_evidence = filter_evidence(
                evidence,
                labels=set(selected_labels),
                relationship_types=set(selected_relationships),
                include_isolated=include_isolated,
            )
            filtered_metrics = st.columns(2)
            filtered_metrics[0].caption(
                f"현재 표시 · 노드 {filtered_evidence['node_count']}개"
            )
            filtered_metrics[1].caption(
                f"현재 표시 · 관계 {filtered_evidence['relationship_count']}개"
            )
            st.graphviz_chart(
                evidence_to_dot(
                    filtered_evidence,
                    rankdir="LR" if layout == "좌→우" else "TB",
                ),
                width="stretch",
            )
            legend = " · ".join(
                f"{label} {sum(node['label'] == label for node in filtered_evidence['nodes'])}"
                for label in sorted(
                    {node["label"] for node in filtered_evidence["nodes"]}
                )
            )
            if legend:
                st.caption(f"범례 · {legend}")
            with st.expander("그래프 근거 상세"):
                node_detail, relationship_detail = st.tabs(
                    ["노드", "관계"]
                )
                with node_detail:
                    st.dataframe(
                        pd.DataFrame(
                            flatten_rows_for_table(
                                filtered_evidence["nodes"]
                            )
                        ),
                        width="stretch",
                        hide_index=True,
                    )
                with relationship_detail:
                    if filtered_evidence["relationships"]:
                        st.dataframe(
                            pd.DataFrame(
                                flatten_rows_for_table(
                                    filtered_evidence["relationships"]
                                )
                            ),
                            width="stretch",
                            hide_index=True,
                        )
                    else:
                        st.info("현재 필터에 해당하는 관계가 없습니다.")
            truncation = evidence.get("truncated", {})
            if any(truncation.values()):
                st.info(
                    "가독성을 위해 전체 결과 중 일부 근거만 표시합니다. "
                    f"전체 {evidence.get('source_row_count', 0)}행 중 "
                    f"{evidence.get('visualized_row_count', 0)}행을 시각화했습니다."
                )
        else:
            st.info(
                "이 질의는 집계 결과이거나 경로 ID가 없어 관계를 추측해 표시하지 않습니다."
            )

    with cypher_tab:
        if result.get("cypher"):
            st.code(result["cypher"], language="cypher", line_numbers=True)
        else:
            st.info("실행된 Cypher가 없습니다.")

    with trace_tab:
        validation = result.get("validation", {})
        trace = validation.get("trace", [])
        if trace:
            st.dataframe(
                pd.DataFrame(flatten_rows_for_table(trace)),
                width="stretch",
                hide_index=True,
            )
        errors = validation.get("errors", [])
        if errors:
            st.error("\n".join(str(error) for error in errors))
        elif trace:
            st.success("모든 검증 단계를 통과했습니다.")
