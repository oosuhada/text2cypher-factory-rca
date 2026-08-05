"""Polished Plotly figure builders for the Streamlit operations dashboard."""

from __future__ import annotations

from typing import Any, Iterable, Literal

import pandas as pd
import plotly.graph_objects as go


PLOTLY_SERIES = (
    "#0C1C74",
    "#E64D2B",
    "#00A396",
    "#D1970C",
    "#7861DB",
    "#29A634",
    "#DA2D6F",
    "#5F6B7B",
)
PLOTLY_NEUTRAL = {
    "ink": "#3A4950",
    "muted": "#5F6B7B",
    "border": "#DCDCDD",
    "grid": "#ECEDEF",
    "surface": "#FFFFFF",
    "surface_subtle": "#F7F8F9",
}
PLOTLY_STATUS_COLORS = {
    "success": "#29A634",
    "blocked": "#DB0714",
    "empty": "#5F6B7B",
    "needs_clarification": "#D1970C",
    "unsupported": "#7861DB",
    "error": "#DB0714",
}
PLOTLY_CHART_CONFIG = {
    "displaylogo": False,
    "displayModeBar": False,
    "responsive": True,
    "scrollZoom": False,
}


def _frame(rows: Iterable[dict[str, Any]] | None) -> pd.DataFrame:
    return pd.DataFrame(list(rows or []))


def _rgba(hex_color: str, alpha: float) -> str:
    normalized = hex_color.removeprefix("#")
    red = int(normalized[0:2], 16)
    green = int(normalized[2:4], 16)
    blue = int(normalized[4:6], 16)
    return f"rgba({red}, {green}, {blue}, {alpha})"


def style_dashboard_figure(
    figure: go.Figure,
    *,
    height: int = 286,
    orientation: Literal["horizontal", "vertical", "none"] = "vertical",
    show_legend: bool = False,
    value_tickformat: str | None = None,
) -> go.Figure:
    """Apply the shared product visual language to any dashboard figure."""

    figure.update_layout(
        title=None,
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        colorway=list(PLOTLY_SERIES),
        font={
            "family": "Pretendard, Inter, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif",
            "size": 11,
            "color": PLOTLY_NEUTRAL["ink"],
        },
        margin={"l": 14, "r": 18, "t": 18, "b": 14, "pad": 0},
        hoverlabel={
            "bgcolor": PLOTLY_NEUTRAL["surface"],
            "bordercolor": PLOTLY_NEUTRAL["border"],
            "font": {
                "family": "Pretendard, Inter, sans-serif",
                "size": 12,
                "color": PLOTLY_NEUTRAL["ink"],
            },
            "align": "left",
        },
        hovermode="closest",
        showlegend=show_legend,
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0,
            "font": {"size": 10, "color": PLOTLY_NEUTRAL["muted"]},
            "title": None,
            "itemclick": "toggle",
        },
        bargap=0.32,
        barcornerradius=4,
        uniformtext={"minsize": 9, "mode": "hide"},
        separators=".,",
    )
    axis_common = {
        "zeroline": False,
        "showline": False,
        "ticks": "",
        "tickfont": {"size": 10, "color": PLOTLY_NEUTRAL["muted"]},
        "title_font": {"size": 10, "color": PLOTLY_NEUTRAL["muted"]},
        "automargin": True,
    }
    figure.update_xaxes(**axis_common)
    figure.update_yaxes(**axis_common)
    figure.update_xaxes(title_text=None)
    figure.update_yaxes(title_text=None)
    if orientation == "horizontal":
        figure.update_xaxes(
            showgrid=True,
            gridcolor=PLOTLY_NEUTRAL["grid"],
            gridwidth=1,
            tickformat=value_tickformat,
        )
        figure.update_yaxes(showgrid=False, categoryorder="total ascending")
    elif orientation == "vertical":
        figure.update_xaxes(showgrid=False)
        figure.update_yaxes(
            showgrid=True,
            gridcolor=PLOTLY_NEUTRAL["grid"],
            gridwidth=1,
            tickformat=value_tickformat,
        )
    else:
        figure.update_xaxes(showgrid=False)
        figure.update_yaxes(showgrid=False)
    return figure


def _empty_figure(message: str = "표시할 데이터가 없습니다.") -> go.Figure:
    figure = go.Figure()
    figure.add_annotation(
        text=(
            "<b>현재 범위에 데이터가 없습니다.</b>"
            f"<br><span style='color:{PLOTLY_NEUTRAL['muted']}'>{message}</span>"
        ),
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        align="center",
        font={"size": 12, "color": PLOTLY_NEUTRAL["ink"]},
    )
    style_dashboard_figure(figure, height=260, orientation="none")
    figure.update_xaxes(visible=False)
    figure.update_yaxes(visible=False)
    return figure


def _horizontal_bar(
    rows: Iterable[dict[str, Any]] | None,
    *,
    category: str,
    value: str,
    category_label: str,
    value_label: str,
    hover_data: list[str] | None = None,
) -> go.Figure:
    frame = _frame(rows)
    if frame.empty or category not in frame or value not in frame:
        return _empty_figure()
    frame = frame.sort_values(value, ascending=True).tail(14)
    custom_columns = [column for column in (hover_data or []) if column in frame]
    customdata = frame[custom_columns].to_numpy() if custom_columns else None
    hover_lines = [f"<b>%{{y}}</b>", f"{value_label} %{{x:,.0f}}"]
    hover_lines.extend(
        f"{column} %{{customdata[{index}]}}"
        for index, column in enumerate(custom_columns)
    )
    figure = go.Figure(
        go.Bar(
            x=frame[value],
            y=frame[category],
            orientation="h",
            marker={"color": PLOTLY_SERIES[0], "line": {"width": 0}},
            text=frame[value],
            texttemplate="%{x:,.0f}",
            textposition="outside",
            cliponaxis=False,
            customdata=customdata,
            hovertemplate="<br>".join(hover_lines) + "<extra></extra>",
        )
    )
    height = max(260, min(390, 25 * len(frame) + 96))
    style_dashboard_figure(
        figure,
        height=height,
        orientation="horizontal",
        value_tickformat=",~s",
    )
    figure.update_layout(margin={"l": 12, "r": 44, "t": 18, "b": 12})
    return figure


def build_node_counts_figure(rows: Iterable[dict[str, Any]] | None) -> go.Figure:
    return _horizontal_bar(
        rows,
        category="label",
        value="count",
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
        category_label="관계 유형",
        value_label="관계 수",
    )


def build_equipment_runs_figure(rows: Iterable[dict[str, Any]] | None) -> go.Figure:
    return _horizontal_bar(
        rows,
        category="equipment",
        value="run_count",
        category_label="장비",
        value_label="실행 수",
    )


def build_anomaly_runs_figure(rows: Iterable[dict[str, Any]] | None) -> go.Figure:
    frame = _frame(rows)
    if frame.empty or not {"anomaly_code", "run_count"}.issubset(frame.columns):
        return _empty_figure()
    frame = frame.sort_values("run_count", ascending=False).head(10)
    figure = go.Figure(
        go.Bar(
            x=frame["anomaly_code"],
            y=frame["run_count"],
            marker={"color": PLOTLY_SERIES[1], "line": {"width": 0}},
            text=frame["run_count"],
            texttemplate="%{y:,.0f}",
            textposition="outside",
            cliponaxis=False,
            hovertemplate="<b>%{x}</b><br>실행 수 %{y:,.0f}<extra></extra>",
        )
    )
    style_dashboard_figure(
        figure,
        height=286,
        orientation="vertical",
        value_tickformat=",~s",
    )
    return figure


def build_quality_failures_figure(
    rows: Iterable[dict[str, Any]] | None,
) -> go.Figure:
    return _horizontal_bar(
        rows,
        category="feature",
        value="failure_count",
        category_label="품질 항목",
        value_label="불합격 수",
    )


def build_status_counts_figure(rows: Iterable[dict[str, Any]] | None) -> go.Figure:
    frame = _frame(rows)
    if frame.empty or not {"status", "count"}.issubset(frame.columns):
        return _empty_figure()
    total = int(frame["count"].sum())
    colors = [
        PLOTLY_STATUS_COLORS.get(str(status), PLOTLY_SERIES[index % len(PLOTLY_SERIES)])
        for index, status in enumerate(frame["status"])
    ]
    status_labels = {
        "success": "성공",
        "blocked": "차단",
        "empty": "빈 결과",
        "needs_clarification": "추가 확인",
        "unsupported": "미지원",
        "error": "오류",
    }
    labels = [status_labels.get(str(status), str(status)) for status in frame["status"]]
    figure = go.Figure(
        go.Pie(
            labels=labels,
            values=frame["count"],
            hole=0.68,
            marker={
                "colors": colors,
                "line": {"color": PLOTLY_NEUTRAL["surface"], "width": 3},
            },
            textinfo="none",
            hovertemplate="<b>%{label}</b><br>%{value:,.0f}건 · %{percent}<extra></extra>",
            sort=False,
        )
    )
    figure.add_annotation(
        text=(
            f"<span style='font-size:10px;color:{PLOTLY_NEUTRAL['muted']}'>전체</span>"
            f"<br><b style='font-size:21px'>{total:,}</b>"
        ),
        x=0.5,
        y=0.5,
        showarrow=False,
        align="center",
    )
    style_dashboard_figure(
        figure,
        height=322,
        orientation="none",
        show_legend=True,
    )
    figure.update_layout(
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": -0.04,
            "xanchor": "center",
            "x": 0.5,
            "font": {"size": 9, "color": PLOTLY_NEUTRAL["muted"]},
            "title": None,
        },
        margin={"l": 8, "r": 8, "t": 8, "b": 70},
    )
    return figure


def build_provider_counts_figure(rows: Iterable[dict[str, Any]] | None) -> go.Figure:
    return _horizontal_bar(
        rows,
        category="provider",
        value="count",
        category_label="Provider",
        value_label="질의 수",
    )


def build_recent_latency_figure(rows: Iterable[dict[str, Any]] | None) -> go.Figure:
    frame = _frame(rows)
    if frame.empty or "elapsed_ms" not in frame:
        return _empty_figure()
    frame = frame.reset_index(drop=True).copy()
    frame["sequence"] = frame.index + 1
    figure = go.Figure(
        go.Scatter(
            x=frame["sequence"],
            y=frame["elapsed_ms"],
            mode="lines+markers",
            line={"color": PLOTLY_SERIES[0], "width": 3, "shape": "spline"},
            marker={
                "size": 7,
                "color": PLOTLY_NEUTRAL["surface"],
                "line": {"color": PLOTLY_SERIES[0], "width": 2},
            },
            fill="tozeroy",
            fillcolor=_rgba(PLOTLY_SERIES[0], 0.08),
            hovertemplate=(
                "<b>최근 실행 %{x}</b><br>응답시간 %{y:,.0f} ms<extra></extra>"
            ),
        )
    )
    style_dashboard_figure(
        figure,
        height=286,
        orientation="vertical",
        value_tickformat=",~s",
    )
    figure.update_xaxes(dtick=1)
    return figure


def build_blind_comparison_figure(comparison: pd.DataFrame) -> go.Figure:
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
        return _empty_figure()
    metric_labels = {
        "execution_success_rate": "실행 성공",
        "result_accuracy": "의미값 정확도",
        "strict_result_accuracy": "엄격 계약",
        "schema_compliance_rate": "Schema 준수",
        "read_only_compliance_rate": "읽기 전용",
    }
    figure = go.Figure()
    for index, column in enumerate(rate_columns):
        figure.add_trace(
            go.Bar(
                name=metric_labels[column],
                x=comparison["variant"],
                y=comparison[column],
                marker={"color": PLOTLY_SERIES[index % len(PLOTLY_SERIES)]},
                hovertemplate=(
                    "<b>%{x}</b><br>%{fullData.name} %{y:.0%}<extra></extra>"
                ),
            )
        )
    style_dashboard_figure(
        figure,
        height=330,
        orientation="vertical",
        show_legend=True,
        value_tickformat=".0%",
    )
    figure.update_yaxes(range=[0, 1.05], tickformat=".0%")
    figure.update_layout(
        barmode="group",
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0,
            "font": {"size": 9, "color": PLOTLY_NEUTRAL["muted"]},
            "title": None,
        },
        margin={"l": 14, "r": 16, "t": 48, "b": 14},
    )
    return figure
