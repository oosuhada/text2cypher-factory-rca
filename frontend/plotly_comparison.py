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
            <div><small>WHY A PRODUCT RUNTIME</small><h2>차트 선택이 다른 업무 화면까지 이어지는 구조</h2></div>
            <a class="p3-workspace-link" href="{REACT_ECHARTS_URL}" target="_blank" rel="noreferrer">실제 Dashboard 열기 ↗</a>
          </header>
          <p class="p3-runtime-intro">ECharts는 차트를 그립니다. React Dashboard runtime은 사용자의 선택을 공통 Object Context로 바꾸고, 다른 Board·필터·Inspector에 전파합니다.</p>
          <div class="p3-runtime-flow" aria-label="Chart interaction to shared object context and synchronized dashboard effects">
            <article class="p3-runtime-stage is-chart-event">
              <header><span>01 · CHART EVENT</span><strong>위험 막대 선택</strong></header>
              <div class="p3-runtime-bars" aria-label="Selected risk bar example">
                <div><small>CMP-S01</small><i style="--bar-size:43%"></i><em>43%</em></div>
                <div><small>CMP-S02</small><i style="--bar-size:61%"></i><em>61%</em></div>
                <div class="is-selected"><small>CMP-S03</small><i style="--bar-size:82.5%"></i><em>82.5%</em></div>
              </div>
              <footer><b>Click / Brush</b><span>selection payload 생성</span></footer>
            </article>
            <div class="p3-runtime-arrow" aria-hidden="true"><span>선택 상태 전달</span><b>→</b></div>
            <article class="p3-runtime-stage is-context">
              <header><span>02 · SHARED CONTEXT</span><strong>Object Context 갱신</strong></header>
              <dl>
                <div><dt>Object</dt><dd>CMP-S03-L03-01</dd></div>
                <div><dt>Risk</dt><dd class="is-danger">82.5% · 긴급 검토</dd></div>
                <div><dt>Scope</dt><dd>Manufacturing / Engineer</dd></div>
              </dl>
              <footer><b>단일 상태</b><span>Project · Workspace · Role 동기화</span></footer>
            </article>
            <div class="p3-runtime-arrow" aria-hidden="true"><span>Cross-filter 전파</span><b>→</b></div>
            <article class="p3-runtime-stage is-effects">
              <header><span>03 · SYNCHRONIZED UI</span><strong>관련 화면이 함께 변경</strong></header>
              <div class="p3-runtime-effects">
                <div><small>Maintenance queue</small><b>3개 설비로 필터</b><span>우선 점검 대상만 표시</span></div>
                <div><small>Board Inspector</small><b>Line · failure_probability</b><span>차트·필드 매핑 변경</span></div>
                <div><small>Saved role view</small><b>Engineer focus</b><span>역할별 레이아웃 유지</span></div>
              </div>
            </article>
          </div>
          <div class="p3-runtime-foundation" aria-label="React dashboard runtime responsibilities">
            <span><b>Board grid</b> 크기·배치·전체화면</span>
            <span><b>Visualization registry</b> 10종 차트 전환</span>
            <span><b>State contract</b> Loading·Empty·Ready</span>
            <span><b>Saved view</b> 역할·필터·레이아웃 저장</span>
          </div>
          <p class="p3-react-preview-note">핵심은 ECharts 자체가 아니라, 차트 이벤트를 제품 상태로 변환해 여러 업무 화면을 동기화하는 React runtime입니다.</p>
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
        normalized.sort(key=lambda row: (row["value"], row["category"]))
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
    express_figure.update_layout(height=390)
    graph_objects_figure.update_layout(height=390)
    payload = {"kind": kind, "title": title, "rows": normalized}
    metrics = {
        "express_build_ms": round(express_ms, 2),
        "graph_objects_build_ms": round(graph_objects_ms, 2),
        "express_json_bytes": len(express_figure.to_json().encode("utf-8")),
        "graph_objects_json_bytes": len(graph_objects_figure.to_json().encode("utf-8")),
        "shared_payload_bytes": len(json.dumps(payload, ensure_ascii=False).encode("utf-8")),
    }
    return express_figure, graph_objects_figure, metrics, payload, None


def _metric_strip(
    label: str,
    *,
    runtime: str,
    build_ms: float | str,
    payload_bytes: int | str,
    client_ms: float | str,
) -> str:
    def value(value: float | int | str, suffix: str = "") -> str:
        if isinstance(value, str):
            return value
        return f"{value:,.1f}{suffix}" if isinstance(value, float) else f"{value:,}{suffix}"

    return (
        f'<div class="p3-renderer-metrics" aria-label="{label} metrics">'
        f'<span><small>Runtime</small><b>{runtime}</b></span>'
        f'<span><small>Figure / option build</small><b>{value(build_ms, " ms")}</b></span>'
        f'<span><small>Serialized</small><b>{value(payload_bytes, " B")}</b></span>'
        f'<span><small>Browser ready</small><b>{value(client_ms, " ms")}</b></span>'
        "</div>"
    )


def _renderer_header(
    *,
    step: str,
    title: str,
    summary: str,
    renderer: str,
    layout_owner: str,
    variant: str = "",
) -> str:
    variant_class = f" {variant}" if variant else ""
    return (
        f'<div class="p3-live-renderer-head{variant_class}">'
        f'<span>{step}</span><strong>{title}</strong><small>{summary}</small>'
        '<dl class="p3-renderer-context">'
        f'<div><dt>Renderer</dt><dd>{renderer}</dd></div>'
        f'<div><dt>Layout owner</dt><dd>{layout_owner}</dd></div>'
        "</dl></div>"
    )


def _capability_panel(
    label: str,
    rows: tuple[tuple[str, str, str], ...],
) -> str:
    row_html = "".join(
        (
            '<li>'
            f'<span>{feature}</span>'
            f'<b class="is-{tone}">{status}</b>'
            "</li>"
        )
        for feature, status, tone in rows
    )
    return (
        f'<section class="p3-capability-panel" aria-label="{label} capability matrix">'
        '<header><strong>현재 구현 기준</strong><small>가능 · 제한 · 미구현</small></header>'
        f"<ul>{row_html}</ul></section>"
    )


PLOTLY_EXPRESS_CAPABILITIES = (
    ("DataFrame → 차트", "가능", "yes"),
    ("차트 내부 스타일", "제한", "limited"),
    ("반응형 Board layout", "제한", "limited"),
    ("Click selection", "제한", "limited"),
    ("Brush · cross-filter", "미구현", "no"),
    ("차트·필드 전환", "미구현", "no"),
    ("저장 layout · 역할 context", "미구현", "no"),
)

PLOTLY_GRAPH_OBJECTS_CAPABILITIES = (
    ("DataFrame → 차트", "가능", "yes"),
    ("차트 내부 스타일", "가능", "yes"),
    ("반응형 Board layout", "제한", "limited"),
    ("Click selection", "별도 연결", "limited"),
    ("Brush · cross-filter", "별도 연결", "limited"),
    ("차트·필드 전환", "미구현", "no"),
    ("저장 layout · 역할 context", "미구현", "no"),
)

REACT_ECHARTS_CAPABILITIES = (
    ("Data contract → 차트", "구현됨", "yes"),
    ("차트 내부 스타일", "구현됨", "yes"),
    ("반응형 Board layout", "구현됨", "yes"),
    ("Click selection", "구현됨", "yes"),
    ("Brush · cross-filter", "구현됨", "yes"),
    ("차트·필드 전환", "구현됨", "yes"),
    ("저장 layout · 역할 context", "구현됨", "yes"),
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
                _renderer_header(
                    step="EXPERIMENT 01",
                    title="Plotly Express + Streamlit",
                    summary="최소 코드 기준선",
                    renderer="Plotly SVG",
                    layout_owner="Streamlit columns",
                ),
                unsafe_allow_html=True,
            )
            st.markdown(
                _metric_strip(
                    "Plotly Express",
                    runtime="Python · Streamlit",
                    build_ms=metrics["express_build_ms"],
                    payload_bytes=metrics["express_json_bytes"],
                    client_ms=express_ready,
                ),
                unsafe_allow_html=True,
            )
            st.plotly_chart(
                express_figure,
                width="stretch",
                key=f"plotly-express-live-{case}",
                config=DEFAULT_CONFIG,
            )
            st.markdown(
                _capability_panel("Plotly Express", PLOTLY_EXPRESS_CAPABILITIES),
                unsafe_allow_html=True,
            )
        with graph_objects_column:
            st.markdown(
                _renderer_header(
                    step="EXPERIMENT 02",
                    title="Plotly Graph Objects + Streamlit",
                    summary="trace와 layout 직접 제어",
                    renderer="Plotly SVG",
                    layout_owner="Streamlit columns",
                    variant="is-polished",
                ),
                unsafe_allow_html=True,
            )
            st.markdown(
                _metric_strip(
                    "Plotly Graph Objects",
                    runtime="Python · Streamlit",
                    build_ms=metrics["graph_objects_build_ms"],
                    payload_bytes=metrics["graph_objects_json_bytes"],
                    client_ms=go_ready,
                ),
                unsafe_allow_html=True,
            )
            render_dashboard_figure(
                graph_objects_figure,
                key=f"plotly-graph-objects-live-{case}",
            )
            st.markdown(
                _capability_panel(
                    "Plotly Graph Objects",
                    PLOTLY_GRAPH_OBJECTS_CAPABILITIES,
                ),
                unsafe_allow_html=True,
            )
        with echarts_column:
            st.markdown(
                _renderer_header(
                    step="FINAL PRODUCT",
                    title="React + Apache ECharts",
                    summary="제품 Dashboard runtime",
                    renderer="ECharts Canvas",
                    layout_owner="React grid runtime",
                    variant="is-selected",
                ),
                unsafe_allow_html=True,
            )
            st.markdown(
                _metric_strip(
                    "React ECharts",
                    runtime="React · Browser",
                    build_ms="Client-side",
                    payload_bytes=metrics["shared_payload_bytes"],
                    client_ms=echarts_ready,
                ),
                unsafe_allow_html=True,
            )
            st.iframe(embed_url, height=390)
            st.markdown(
                _capability_panel("React ECharts", REACT_ECHARTS_CAPABILITIES),
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
          .block-container {
            max-width: 1600px !important;
            padding-left: clamp(.75rem, 3vw, 2rem) !important;
            padding-right: clamp(.75rem, 3vw, 2rem) !important;
          }
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
