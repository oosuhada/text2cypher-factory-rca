"""Three-way visualization experiment and renderer decision page."""

from __future__ import annotations

import json
import os
from pathlib import Path
from time import perf_counter
from typing import Any
from urllib.parse import quote

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from frontend.dashboard_plotly import (
    build_node_counts_figure,
    build_recent_latency_figure,
    build_status_counts_figure,
)
from frontend.pages.dashboard import (
    normalize_dashboard_snapshot,
    render_dashboard_figure,
)
from frontend.runtime import SERVICE_BUNDLE_VERSION, clear_service_cache, get_services
from frontend.session_state import initialize_session
from frontend.ui_mode import runtime_provider_and_model


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REACT_ECHARTS_URL = (
    "https://dashboard.oosu.dev/app/projects/manufacturing-demo-project"
)
REACT_ECHARTS_EMBED_URL = os.getenv(
    "P3_REACT_ECHARTS_EMBED_URL",
    "https://dashboard.oosu.dev/visualization-compare/echarts",
).rstrip("/")
BENCHMARK_PATH = Path(__file__).with_name("visualization_renderer_benchmark.json")
DEFAULT_CONFIG = {
    "displaylogo": True,
    "displayModeBar": "hover",
    "responsive": True,
}


def _default_node_counts(rows: list[dict[str, Any]]) -> go.Figure:
    frame = pd.DataFrame(rows).sort_values("count", ascending=True)
    return px.bar(
        frame,
        x="count",
        y="label",
        orientation="h",
        title="노드 유형별 규모",
        labels={"count": "노드 수", "label": "노드 유형"},
    )


def _default_status_counts(rows: list[dict[str, Any]]) -> go.Figure:
    frame = pd.DataFrame(rows)
    return px.pie(
        frame,
        names="status",
        values="count",
        hole=0.58,
        title="질의 상태 구성",
    )


def _default_latency(rows: list[dict[str, Any]]) -> go.Figure:
    frame = pd.DataFrame(rows).reset_index(drop=True)
    frame["sequence"] = frame.index + 1
    return px.line(
        frame,
        x="sequence",
        y="elapsed_ms",
        markers=True,
        title="최근 질의 응답시간",
        labels={"sequence": "최근 실행 순서", "elapsed_ms": "응답시간 (ms)"},
    )


def _render_method_card(
    *,
    step: str,
    title: str,
    badge: str,
    summary: str,
    points: tuple[str, ...],
    selected: bool = False,
) -> str:
    point_html = "".join(f"<li>{point}</li>" for point in points)
    selected_class = " is-selected" if selected else ""
    return (
        f'<article class="p3-method-card{selected_class}">'
        f'<header><span>{step}</span><b>{badge}</b></header>'
        f"<h3>{title}</h3><p>{summary}</p><ul>{point_html}</ul></article>"
    )


def _render_decision_overview() -> None:
    cards = "".join(
        (
            _render_method_card(
                step="EXPERIMENT 01",
                title="Plotly Express + Streamlit",
                badge="빠른 기준선",
                summary="데이터프레임을 최소 코드로 차트화해 연결 가능성과 개발 속도를 검증했습니다.",
                points=(
                    "초기 구현 속도는 가장 빠름",
                    "기본 theme·margin 의존도가 높음",
                    "제품형 Board와 cross-filter에는 부족",
                ),
            ),
            _render_method_card(
                step="EXPERIMENT 02",
                title="Plotly Graph Objects + Streamlit",
                badge="차트 정교화",
                summary="Graph Objects로 trace, hover, semantic color와 여백을 직접 제어했습니다.",
                points=(
                    "차트 내부 표현은 상당 부분 개선",
                    "Streamlit column·widget layout 제약은 지속",
                    "복합 제품 interaction 구현 비용이 커짐",
                ),
            ),
            _render_method_card(
                step="FINAL PRODUCT",
                title="React + Apache ECharts",
                badge="최종 선택",
                summary="차트가 아니라 Dashboard runtime 전체를 제품 요구에 맞게 직접 구성했습니다.",
                points=(
                    "10종 visualization registry와 자동·수동 전환",
                    "Board grid, Inspector, selection·brush cross-filter",
                    "역할·Object context·저장된 view와 통합",
                ),
                selected=True,
            ),
        )
    )
    st.markdown(
        f'<section class="p3-method-grid">{cards}</section>',
        unsafe_allow_html=True,
    )


def _render_decision_matrix() -> None:
    st.markdown(
        """
        <section class="p3-decision-panel">
          <header>
            <div><small>PROJECT DECISION</small><h2>React + ECharts를 최종 Dashboard로 선택</h2></div>
            <strong>SELECTED</strong>
          </header>
          <div class="p3-decision-table-wrap">
            <table class="p3-decision-table">
              <thead><tr><th>평가 기준</th><th>Plotly Express</th><th>Plotly Graph Objects</th><th>React + ECharts</th></tr></thead>
              <tbody>
                <tr><td>빠른 분석 실험</td><td class="is-good">매우 적합</td><td class="is-good">적합</td><td>구현 비용 큼</td></tr>
                <tr><td>시각 디자인 제어</td><td>기본값 의존</td><td class="is-mid">차트 내부 제어</td><td class="is-good">UI 전체 제어</td></tr>
                <tr><td>반응형 Board layout</td><td>Streamlit 제약</td><td>Streamlit 제약 지속</td><td class="is-good">12열 grid 직접 제어</td></tr>
                <tr><td>선택·brush·cross-filter</td><td>제한적</td><td class="is-mid">별도 wiring 필요</td><td class="is-good">제품 runtime 구현</td></tr>
                <tr><td>AI 차트 추천·수동 전환</td><td>별도 개발</td><td>별도 개발</td><td class="is-good">Registry + Inspector 구현</td></tr>
                <tr><td>역할·Object·권한 UX 통합</td><td>부적합</td><td>부분 가능</td><td class="is-good">제품 구조와 직접 통합</td></tr>
                <tr><td>최종 용도</td><td>연결성 PoC</td><td>분석·내부 보고</td><td class="is-selected">최종 제품 Dashboard</td></tr>
              </tbody>
            </table>
          </div>
          <p>Plotly 계열은 실패한 실험이 아니라 Python 기반 분석·검증 도구로 유지합니다. 최종 사용자 화면은 차트 품질보다 Board 편집, 역할별 정보 구조, cross-filter와 Object context가 더 중요하므로 React + ECharts를 선택합니다.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_react_echarts_runtime() -> None:
    st.markdown(
        f"""
        <section class="p3-react-runtime">
          <header>
            <div><small>IMPLEMENTED PRODUCT RUNTIME</small><h2>현재 React + ECharts Dashboard</h2></div>
            <a class="p3-workspace-link" href="{REACT_ECHARTS_URL}" target="_blank" rel="noreferrer">실제 Dashboard 열기 ↗</a>
          </header>
          <div class="p3-react-runtime-grid">
            <article><b>Visualization registry</b><span>Metric · Table · Bar · Stacked · Line · Area · Donut · Histogram · Scatter · Heatmap</span></article>
            <article><b>Board runtime</b><span>react-grid-layout 기반 크기·배치·fullscreen·saved view</span></article>
            <article><b>Interaction</b><span>click selection · brush · data zoom · server cross-filter</span></article>
            <article><b>Semantic planner</b><span>자동 추천, 대안·불가 사유, 수동 chart·field mapping</span></article>
            <article><b>Product context</b><span>Project · Workspace · Role · Object context와 동기화</span></article>
            <article><b>State contract</b><span>loading · empty · incompatible · ready를 Board 단위로 처리</span></article>
          </div>
          <div class="p3-react-board-preview" aria-label="React ECharts runtime structure preview">
            <div class="p3-react-board-head"><span>관리형 BOARD · 위험 추세 분석</span><div><i>AUTO</i><b>Line</b><em>•••</em></div></div>
            <div class="p3-react-board-body">
              <aside><strong>Object context</strong><span>CMP-S03-L03-01</span><small>긴급 검토 · 82.5%</small></aside>
              <div class="p3-react-chart-schematic">
                <div class="p3-react-chart-gridline is-1"></div><div class="p3-react-chart-gridline is-2"></div><div class="p3-react-chart-gridline is-3"></div>
                <svg viewBox="0 0 640 190" role="img" aria-label="ECharts line interaction schematic"><path d="M12 160 C88 148 116 120 174 132 S264 92 318 106 S410 54 468 76 S558 28 628 42" fill="none" stroke="#0C1C74" stroke-width="5" stroke-linecap="round"/><path d="M12 160 C88 148 116 120 174 132 S264 92 318 106 S410 54 468 76 S558 28 628 42 L628 184 L12 184 Z" fill="rgba(12,28,116,.10)"/><g fill="#fff" stroke="#0C1C74" stroke-width="4"><circle cx="174" cy="132" r="6"/><circle cx="318" cy="106" r="6"/><circle cx="468" cy="76" r="6"/><circle cx="628" cy="42" r="6"/></g></svg>
              </div>
            </div>
            <footer><span>선택 → Object Context 갱신</span><span>Brush → Cross-filter</span><span>Inspector → 차트·필드 변경</span></footer>
          </div>
          <p class="p3-react-preview-note">위 미리보기는 실제 제품 runtime의 구조를 설명하는 schematic이며, 실제 ECharts Canvas와 Board 동작은 링크된 React Dashboard에서 확인합니다.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _shared_case_data(
    snapshot: dict[str, Any],
    case: str,
) -> tuple[str, list[dict[str, Any]], str, str | None]:
    runtime = snapshot["runtime"]
    if case == "범주 비교":
        rows = snapshot["node_counts"]
        if not rows:
            return "bar", [], "노드 유형별 규모", "현재 프로젝트에는 노드 유형 집계가 없습니다."
        normalized = [
            {"category": str(row.get("label", "")), "value": float(row.get("count", 0))}
            for row in rows
        ]
        return "bar", normalized, "노드 유형별 규모", None
    if case == "상태 구성":
        rows = runtime["status_counts"]
        if not rows:
            return "donut", [], "질의 상태 구성", "Query Studio 실행 이력이 없어 상태 구성을 비교할 수 없습니다."
        normalized = [
            {"category": str(row.get("status", "")), "value": float(row.get("count", 0))}
            for row in rows
        ]
        return "donut", normalized, "질의 상태 구성", None
    rows = runtime["recent_queries"]
    if not rows or not any("elapsed_ms" in row for row in rows):
        return "line", [], "최근 질의 응답시간", "응답시간이 포함된 최근 질의가 없어 시간 추세를 비교할 수 없습니다."
    normalized = [
        {"category": str(index + 1), "value": float(row.get("elapsed_ms", 0))}
        for index, row in enumerate(rows)
    ]
    return "line", normalized, "최근 질의 응답시간", None


def _figures_for_case(
    snapshot: dict[str, Any],
    case: str,
) -> tuple[go.Figure | None, go.Figure | None, dict[str, float | int], dict[str, Any] | None, str | None]:
    kind, normalized, title, error = _shared_case_data(snapshot, case)
    if error:
        return None, None, {}, None, error

    if case == "범주 비교":
        source_rows = snapshot["node_counts"]
        express_builder = lambda: _default_node_counts(source_rows)
        graph_objects_builder = lambda: build_node_counts_figure(source_rows)
    elif case == "상태 구성":
        source_rows = snapshot["runtime"]["status_counts"]
        express_builder = lambda: _default_status_counts(source_rows)
        graph_objects_builder = lambda: build_status_counts_figure(source_rows)
    else:
        source_rows = snapshot["runtime"]["recent_queries"]
        express_builder = lambda: _default_latency(source_rows)
        graph_objects_builder = lambda: build_recent_latency_figure(source_rows)

    started = perf_counter()
    express_figure = express_builder()
    express_ms = (perf_counter() - started) * 1000
    started = perf_counter()
    graph_objects_figure = graph_objects_builder()
    graph_objects_ms = (perf_counter() - started) * 1000
    express_figure.update_layout(height=360)
    graph_objects_figure.update_layout(height=360)
    payload = {"kind": kind, "title": title, "rows": normalized}
    metrics = {
        "express_build_ms": round(express_ms, 2),
        "graph_objects_build_ms": round(graph_objects_ms, 2),
        "express_json_bytes": len(express_figure.to_json().encode("utf-8")),
        "graph_objects_json_bytes": len(graph_objects_figure.to_json().encode("utf-8")),
        "shared_payload_bytes": len(json.dumps(payload, ensure_ascii=False).encode("utf-8")),
    }
    return express_figure, graph_objects_figure, metrics, payload, None


def _metric_strip(label: str, build_ms: float | str, payload_bytes: int | str, client_ms: float | str) -> str:
    def value(value: float | int | str, suffix: str = "") -> str:
        if isinstance(value, str):
            return value
        return f"{value:,.1f}{suffix}" if isinstance(value, float) else f"{value:,}{suffix}"

    return (
        f'<div class="p3-renderer-metrics" aria-label="{label} metrics">'
        f'<span><small>Figure build</small><b>{value(build_ms, " ms")}</b></span>'
        f'<span><small>Serialized</small><b>{value(payload_bytes, " B")}</b></span>'
        f'<span><small>Browser ready</small><b>{value(client_ms, " ms")}</b></span>'
        "</div>"
    )


def _load_benchmark(case: str) -> dict[str, Any]:
    if not BENCHMARK_PATH.exists():
        return {}
    try:
        payload = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
        return dict(payload.get("cases", {}).get(case, {}))
    except (OSError, ValueError, TypeError):
        return {}


def _render_live_three_way(snapshot: dict[str, Any]) -> None:
    st.markdown("## 동일 데이터 · 동일 차트 의도 · 세 렌더러 실제 출력")
    st.caption(
        "Plotly Express와 Plotly Graph Objects는 Streamlit에서 실제 렌더링하고, "
        "React + ECharts는 공개 React 앱의 전용 임베드 route에 같은 JSON payload를 전달합니다."
    )
    case_options = ("범주 비교", "상태 구성", "시간 추세")
    case_keys = {"category": "범주 비교", "status": "상태 구성", "latency": "시간 추세"}
    requested_case = case_keys.get(str(st.query_params.get("renderer_case", "category")), "범주 비교")
    case = st.radio(
        "비교할 데이터",
        options=case_options,
        index=case_options.index(requested_case),
        horizontal=True,
        key="visualization-experiment-case",
    )
    express_figure, graph_objects_figure, metrics, payload, error = _figures_for_case(snapshot, case)
    if error or payload is None or express_figure is None or graph_objects_figure is None:
        st.info(error or "비교 데이터를 준비하지 못했습니다.")
        return

    benchmark = _load_benchmark(case)
    express_ready = benchmark.get("plotly_express_ready_ms", "측정 전")
    go_ready = benchmark.get("plotly_graph_objects_ready_ms", "측정 전")
    echarts_ready = benchmark.get("react_echarts_ready_ms", "Live")
    encoded_payload = quote(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    embed_url = f"{REACT_ECHARTS_EMBED_URL}?payload={encoded_payload}"

    with st.container(key="renderer-live-grid"):
        express_column, graph_objects_column, echarts_column = st.columns(3)
        with express_column:
            st.markdown(
                '<div class="p3-live-renderer-head"><span>EXPERIMENT 01</span><strong>Plotly Express + Streamlit</strong><small>최소 코드 기준선</small></div>',
                unsafe_allow_html=True,
            )
            st.plotly_chart(
                express_figure,
                width="stretch",
                key=f"plotly-express-live-{case}",
                config=DEFAULT_CONFIG,
            )
            st.markdown(
                _metric_strip(
                    "Plotly Express",
                    metrics["express_build_ms"],
                    metrics["express_json_bytes"],
                    express_ready,
                ),
                unsafe_allow_html=True,
            )
        with graph_objects_column:
            st.markdown(
                '<div class="p3-live-renderer-head is-polished"><span>EXPERIMENT 02</span><strong>Plotly Graph Objects + Streamlit</strong><small>trace와 layout 직접 제어</small></div>',
                unsafe_allow_html=True,
            )
            render_dashboard_figure(
                graph_objects_figure,
                key=f"plotly-graph-objects-live-{case}",
            )
            st.markdown(
                _metric_strip(
                    "Plotly Graph Objects",
                    metrics["graph_objects_build_ms"],
                    metrics["graph_objects_json_bytes"],
                    go_ready,
                ),
                unsafe_allow_html=True,
            )
        with echarts_column:
            st.markdown(
                '<div class="p3-live-renderer-head is-selected"><span>FINAL PRODUCT</span><strong>React + Apache ECharts</strong><small>독립 제품 runtime</small></div>',
                unsafe_allow_html=True,
            )
            components.iframe(embed_url, height=390, scrolling=False)
            st.markdown(
                _metric_strip(
                    "React ECharts",
                    "Client",
                    metrics["shared_payload_bytes"],
                    echarts_ready,
                ),
                unsafe_allow_html=True,
            )

    if benchmark:
        st.caption(
            "Browser ready는 공개 URL에서 새 브라우저 context로 반복 측정한 중앙값입니다. "
            f"측정: {benchmark.get('runs', '—')}회 · viewport {benchmark.get('viewport', '—')} · {benchmark.get('measured_at', '—')}"
        )
    else:
        st.caption("Browser ready 기준값은 배포 후 공개 URL에서 반복 측정해 갱신됩니다. React 카드 내부에는 현재 iframe의 live ready 시간이 표시됩니다.")


def render_visualization_decision(
    snapshot: dict[str, Any],
    *,
    project_id: str,
) -> None:
    snapshot = normalize_dashboard_snapshot(snapshot)
    st.markdown(
        f"""
        <section class="p3-plotly-comparison-hero" id="p3-main-content">
          <div>
            <small>Visualization renderer decision · three implementations</small>
            <h1>Plotly Express → Plotly Graph Objects → React + ECharts</h1>
            <p>빠른 연결 실험, 차트 정교화 실험, 실제 제품 Dashboard를 같은 기준으로 비교합니다. 최종 선택은 단순히 더 예쁜 차트가 아니라 Board layout, cross-filter, 역할별 UX와 AI 시각화 전환을 포함한 제품 runtime을 기준으로 결정했습니다.</p>
          </div>
          <a class="p3-workspace-link" href="/?workspace=dashboard" target="_self">Streamlit Dashboard로 돌아가기 →</a>
        </section>
        """,
        unsafe_allow_html=True,
    )
    st.caption(f"현재 프로젝트 · {project_id} · 동일 Dashboard snapshot 기준")
    _render_decision_overview()
    _render_live_three_way(snapshot)
    _render_react_echarts_runtime()
    _render_decision_matrix()


def render_plotly_comparison_route() -> None:
    """Resolve the active project and render the visualization decision route."""

    initialize_session()
    st.markdown(
        """
        <style>
          [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display: none !important; }
          .block-container { max-width: 1600px !important; padding-left: 2rem !important; padding-right: 2rem !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    project_id = str(
        st.query_params.get("project_id")
        or st.session_state.get("active_project_id", "cip-dmd")
    )
    provider, model_name = runtime_provider_and_model()
    st.sidebar.markdown("## Visualization Decision")
    st.sidebar.caption("Plotly Express · Plotly Graph Objects · React + ECharts")
    st.sidebar.markdown(
        '<a class="p3-workspace-link p3-workspace-link--stretch" '
        'href="/?workspace=dashboard" target="_self">← Streamlit Dashboard</a>',
        unsafe_allow_html=True,
    )
    st.sidebar.markdown(
        f'<a class="p3-workspace-link p3-workspace-link--stretch" '
        f'href="{REACT_ECHARTS_URL}" target="_blank" rel="noreferrer">React + ECharts ↗</a>',
        unsafe_allow_html=True,
    )
    st.sidebar.caption(f"Project · {project_id}")
    try:
        services = get_services(
            provider,
            model_name,
            SERVICE_BUNDLE_VERSION,
            project_id,
        )
        snapshot = services.dashboard.snapshot()
    except Exception as error:
        st.error(f"비교용 Dashboard snapshot을 불러오지 못했습니다: {error}")
        if st.button("서비스 캐시 초기화"):
            clear_service_cache()
            st.rerun()
        return
    render_visualization_decision(snapshot, project_id=project_id)


render_plotly_comparison = render_visualization_decision

__all__ = [
    "render_plotly_comparison",
    "render_plotly_comparison_route",
    "render_visualization_decision",
]
