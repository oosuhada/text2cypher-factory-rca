from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from frontend.dashboard_plotly import (
    build_anomaly_runs_figure,
    build_blind_comparison_figure,
    build_equipment_runs_figure,
    build_node_counts_figure,
    build_provider_counts_figure,
    build_quality_failures_figure,
    build_recent_latency_figure,
    build_relationship_counts_figure,
    build_status_counts_figure,
)


def test_dashboard_builds_more_than_three_plotly_figures() -> None:
    figures = [
        build_node_counts_figure([{"label": "Part", "count": 12}]),
        build_relationship_counts_figure(
            [{"relationship_type": "PRODUCED_BY", "count": 8}]
        ),
        build_equipment_runs_figure(
            [{"equipment": "AssemblyCell", "run_count": 21}]
        ),
        build_anomaly_runs_figure(
            [{"anomaly_code": "surface_defect", "run_count": 3}]
        ),
        build_quality_failures_figure(
            [{"feature": "diameter", "failure_count": 5}]
        ),
        build_status_counts_figure([{"status": "success", "count": 14}]),
        build_provider_counts_figure([{"provider": "gemini", "count": 9}]),
        build_recent_latency_figure(
            [{"question": "최근 이상은?", "status": "success", "elapsed_ms": 125}]
        ),
    ]

    assert len(figures) == 8
    assert all(isinstance(figure, go.Figure) for figure in figures)
    assert all(figure.data for figure in figures)


def test_blind_comparison_uses_grouped_rate_series() -> None:
    comparison = pd.DataFrame(
        [
            {
                "variant": "baseline",
                "execution_success_rate": 0.8,
                "result_accuracy": 0.7,
                "strict_result_accuracy": 0.6,
                "schema_compliance_rate": 0.9,
                "read_only_compliance_rate": 1.0,
            },
            {
                "variant": "self-correction",
                "execution_success_rate": 0.95,
                "result_accuracy": 0.9,
                "strict_result_accuracy": 0.85,
                "schema_compliance_rate": 1.0,
                "read_only_compliance_rate": 1.0,
            },
        ]
    )

    figure = build_blind_comparison_figure(comparison)

    assert isinstance(figure, go.Figure)
    assert len(figure.data) == 5
    assert figure.layout.barmode == "group"
    assert figure.layout.yaxis.tickformat == ".0%"


def test_empty_chart_inputs_return_presentable_empty_figures() -> None:
    figure = build_node_counts_figure([])

    assert isinstance(figure, go.Figure)
    assert not figure.data
    assert figure.layout.annotations[0].text == "표시할 데이터가 없습니다."

