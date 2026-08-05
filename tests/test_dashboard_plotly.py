from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from frontend.dashboard_plotly import (
    PLOTLY_CHART_CONFIG,
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
from frontend.plotly_comparison import _figures_for_case


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
    assert "표시할 데이터가 없습니다." in figure.layout.annotations[0].text
    assert figure.layout.paper_bgcolor == "rgba(0,0,0,0)"


def test_polished_figures_use_product_visual_defaults() -> None:
    figure = build_node_counts_figure(
        [
            {"label": "Equipment", "count": 100},
            {"label": "Observation", "count": 345_600},
        ]
    )

    assert figure.layout.title.text is None
    assert figure.layout.paper_bgcolor == "rgba(0,0,0,0)"
    assert figure.layout.plot_bgcolor == "rgba(0,0,0,0)"
    assert figure.layout.barcornerradius == 4
    assert figure.layout.xaxis.gridcolor == "#ECEDEF"
    assert figure.layout.xaxis.title.text is None
    assert figure.layout.yaxis.title.text is None
    assert isinstance(figure.data[0], go.Bar)
    assert figure.data[0].hovertemplate.endswith("<extra></extra>")
    assert PLOTLY_CHART_CONFIG["displayModeBar"] is False
    assert PLOTLY_CHART_CONFIG["displaylogo"] is False


def test_status_donut_contains_total_and_semantic_colors() -> None:
    figure = build_status_counts_figure(
        [
            {"status": "success", "count": 4},
            {"status": "blocked", "count": 2},
        ]
    )

    assert figure.layout.annotations
    assert "6" in figure.layout.annotations[0].text
    assert list(figure.data[0].marker.colors) == ["#29A634", "#DB0714"]
    assert figure.data[0].hole == 0.68
    assert list(figure.data[0].labels) == ["성공", "차단"]
    assert figure.data[0].textinfo == "none"


def test_three_renderer_comparison_uses_one_normalized_payload() -> None:
    snapshot = {
        "totals": {"nodes": 3, "relationships": 2},
        "node_counts": [
            {"label": "Part", "count": 2},
            {"label": "Equipment", "count": 1},
        ],
        "relationship_counts": [],
        "equipment_runs": [],
        "anomaly_runs": [],
        "quality_failures": [],
        "integrity": {},
        "evaluation": {},
        "runtime": {"status_counts": [], "recent_queries": []},
    }
    express, graph_objects, metrics, payload, error = _figures_for_case(snapshot, "범주 비교")

    assert error is None
    assert isinstance(express, go.Figure)
    assert isinstance(graph_objects, go.Figure)
    assert payload == {
        "kind": "bar",
        "title": "노드 유형별 규모",
        "rows": [
            {"category": "Part", "value": 2.0},
            {"category": "Equipment", "value": 1.0},
        ],
    }
    assert metrics["express_json_bytes"] > 0
    assert metrics["graph_objects_json_bytes"] > 0
    assert metrics["shared_payload_bytes"] > 0


def test_graph_objects_are_used_for_the_custom_plotly_experiment() -> None:
    bar = build_node_counts_figure([{"label": "Part", "count": 12}])
    donut = build_status_counts_figure([{"status": "success", "count": 2}])
    line = build_recent_latency_figure([{"elapsed_ms": 120}])

    assert isinstance(bar.data[0], go.Bar)
    assert isinstance(donut.data[0], go.Pie)
    assert isinstance(line.data[0], go.Scatter)

