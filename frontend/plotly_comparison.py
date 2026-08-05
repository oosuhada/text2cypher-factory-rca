"""Three-way visualization experiment and renderer decision page."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

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


def _case_builders(
    snapshot: dict[str, Any],
    case: str,
) -> tuple[str, go.Figure | None, go.Figure | None, str | None]:
    runtime = snapshot["runtime"]
    if case == "범주 비교":
        rows = snapshot["node_counts"]
        if not rows:
            return case, None, None, "현재 프로젝트에는 노드 유형 집계가 없습니다."
        return case, _default_node_counts(rows), build_node_counts_figure(rows), None
    if case == "상태 구성":
        rows = runtime["status_counts"]
        if not rows:
            return case, None, None, "Query Studio 실행 이력이 없어 상태 구성을 비교할 수 없습니다."
        return case, _default_status_counts(rows), build_status_counts_figure(rows), None
    rows = runtime["recent_queries"]
    if not rows or not any("elapsed_ms" in row for row in rows):
        return case, None, None, "응답시간이 포함된 최근 질의가 없어 시간 추세를 비교할 수 없습니다."
    return case, _default_latency(rows), build_recent_latency_figure(rows), None


def _render_plotly_experiments(snapshot: dict[str, Any]) -> None:
    st.markdown("## 동일 데이터로 확인한 두 번의 Plotly 실험")
    st.caption(
        "두 차트 모두 같은 Dashboard snapshot과 같은 시각화 의도를 사용합니다. "
        "차이는 Plotly Express 기본 생성과 Graph Objects 직접 구성 방식입니다."
    )
    case = st.radio(
        "비교할 데이터",
        options=("범주 비교", "상태 구성", "시간 추세"),
        horizontal=True,
        key="visualization-experiment-case",
    )
    case, express_figure, graph_objects_figure, error = _case_builders(snapshot, case)
    if error:
        st.info(error)
        return
    assert express_figure is not None and graph_objects_figure is not None

    with st.container(key="plotly-express-experiment"):
        st.markdown(
            '<div class="p3-experiment-heading"><span>EXPERIMENT 01</span><div><strong>Plotly Express</strong><small>빠른 기준선 · 기본 layout</small></div></div>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(
            express_figure,
            width="stretch",
            key=f"plotly-express-{case}",
            config=DEFAULT_CONFIG,
        )
        st.caption("장점: 데이터프레임에서 즉시 생성 · 한계: 기본 margin, title, legend와 Streamlit layout 의존")

    with st.container(key="plotly-graph-objects-experiment"):
        st.markdown(
            '<div class="p3-experiment-heading is-polished"><span>EXPERIMENT 02</span><div><strong>Plotly Graph Objects</strong><small>trace·hover·semantic style 직접 제어</small></div></div>',
            unsafe_allow_html=True,
        )
        render_dashboard_figure(
            graph_objects_figure,
            key=f"plotly-graph-objects-{case}",
        )
        st.caption("개선: 차트 내부 표현과 의미 색상 · 잔존 한계: Streamlit widget·column·Dashboard interaction 구조")


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
    _render_plotly_experiments(snapshot)
    _render_react_echarts_runtime()
    _render_decision_matrix()


def render_plotly_comparison_route() -> None:
    """Resolve the active project and render the visualization decision route."""

    initialize_session()
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
