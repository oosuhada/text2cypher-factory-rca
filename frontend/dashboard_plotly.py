"""Plotly figure builders for the Streamlit operations dashboard."""

from __future__ import annotations

from typing import Any, Iterable

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def _frame(rows: Iterable[dict[str, Any]] | None) -> pd.DataFrame:
    return pd.DataFrame(list(rows or []))


def _empty_figure(title: str, message: str = "표시할 데이터가 없습니다.") -> go.Figure:
    figure = go.Figure()
    figure.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
    )
    figure.update_layout(
        title=title,
        height=360,
        xaxis={"visible": False},
        yaxis={"visible": False},
    )
    return figure


def _horizontal_bar(
    rows: Iterable[dict[str, Any]] | None,
    *,
    category: str,
    value: str,
    title: str,
    category_label: str,
    value_label: str,
    hover_data: list[str] | None = None,
) -> go.Figure:
    frame = _frame(rows)
    if frame.empty or category not in frame or value not in frame:
        return _empty_figure(title)
    frame = frame.sort_values(value, ascending=True)
    figure = px.bar(
        frame,
        x=value,
        y=category,
        orientation="h",
        hover_data=hover_data or [],
        labels={category: category_label, value: value_label},
        title=title,
    )
    figure.update_layout(height=max(340, 38 * len(frame) + 110), showlegend=False)
    return figure


def build_node_counts_figure(rows: Iterable[dict[str, Any]] | None) -> go.Figure:
    return _horizontal_bar(
        rows,
        category="label",
        value="count",
        title="노드 유형별 규모",
        category_label="노드 유형",
        value_label="노드 수",
    )


def build_relationship_counts_figure(
    rows: Iterable[dict[str, Any]] | None,
) -> go.Figure:
    return _horizontal_bar(
        rows,
        category="relationship_type",
        value="count",
        title="관계 유형별 규모",
        category_label="관계 유형",
        value_label="관계 수",
    )


def build_equipment_runs_figure(rows: Iterable[dict[str, Any]] | None) -> go.Figure:
    return _horizontal_bar(
        rows,
        category="equipment",
        value="run_count",
        title="장비별 공정 실행",
        category_label="장비",
        value_label="실행 수",
    )


def build_anomaly_runs_figure(rows: Iterable[dict[str, Any]] | None) -> go.Figure:
    frame = _frame(rows)
    title = "이상 유형 분포"
    if frame.empty or not {"anomaly_code", "run_count"}.issubset(frame.columns):
        return _empty_figure(title)
    frame = frame.sort_values("run_count", ascending=False)
    figure = px.bar(
        frame,
        x="anomaly_code",
        y="run_count",
        labels={"anomaly_code": "이상 유형", "run_count": "실행 수"},
        title=title,
    )
    figure.update_layout(height=380, showlegend=False)
    return figure


def build_quality_failures_figure(
    rows: Iterable[dict[str, Any]] | None,
) -> go.Figure:
    return _horizontal_bar(
        rows,
        category="feature",
        value="failure_count",
        title="품질 불합격 상위 항목",
        category_label="품질 항목",
        value_label="불합격 수",
    )


def build_status_counts_figure(rows: Iterable[dict[str, Any]] | None) -> go.Figure:
    frame = _frame(rows)
    title = "질의 상태 구성"
    if frame.empty or not {"status", "count"}.issubset(frame.columns):
        return _empty_figure(title)
    figure = px.pie(
        frame,
        names="status",
        values="count",
        hole=0.58,
        title=title,
    )
    figure.update_traces(textposition="inside", textinfo="percent+label")
    figure.update_layout(height=380, showlegend=False)
    return figure


def build_provider_counts_figure(rows: Iterable[dict[str, Any]] | None) -> go.Figure:
    frame = _frame(rows)
    title = "Provider별 질의량"
    if frame.empty or not {"provider", "count"}.issubset(frame.columns):
        return _empty_figure(title)
    frame = frame.sort_values("count", ascending=True)
    figure = px.bar(
        frame,
        x="count",
        y="provider",
        orientation="h",
        labels={"provider": "Provider", "count": "질의 수"},
        title=title,
    )
    figure.update_layout(height=340, showlegend=False)
    return figure


def build_recent_latency_figure(rows: Iterable[dict[str, Any]] | None) -> go.Figure:
    frame = _frame(rows)
    title = "최근 질의 응답시간"
    if frame.empty or "elapsed_ms" not in frame:
        return _empty_figure(title)
    frame = frame.reset_index(drop=True).copy()
    frame["sequence"] = frame.index + 1
    hover = [column for column in ("question", "status", "provider") if column in frame]
    figure = px.line(
        frame,
        x="sequence",
        y="elapsed_ms",
        markers=True,
        hover_data=hover,
        labels={"sequence": "최근 실행 순서", "elapsed_ms": "응답시간 (ms)"},
        title=title,
    )
    figure.update_layout(height=340)
    return figure


def build_blind_comparison_figure(comparison: pd.DataFrame) -> go.Figure:
    title = "Blind 평가 variant별 품질 비교"
    rate_columns = [
        column
        for column in (
            "execution_success_rate",
            "result_accuracy",
            "strict_result_accuracy",
            "schema_compliance_rate",
            "read_only_compliance_rate",
        )
        if column in comparison.columns
    ]
    if comparison.empty or "variant" not in comparison or not rate_columns:
        return _empty_figure(title)
    melted = comparison.melt(
        id_vars=["variant"],
        value_vars=rate_columns,
        var_name="metric",
        value_name="rate",
    )
    figure = px.bar(
        melted,
        x="variant",
        y="rate",
        color="metric",
        barmode="group",
        labels={"variant": "Variant", "rate": "비율", "metric": "지표"},
        title=title,
    )
    figure.update_yaxes(tickformat=".0%", range=[0, 1])
    figure.update_layout(height=430, legend_title_text="지표")
    return figure

