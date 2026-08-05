"""Side-by-side default and product-styled Plotly comparison page."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from frontend.dashboard_plotly import (
    PLOTLY_CHART_CONFIG,
    build_node_counts_figure,
    build_recent_latency_figure,
    build_status_counts_figure,
)
from frontend.pages.dashboard import normalize_dashboard_snapshot
from frontend.runtime import SERVICE_BUNDLE_VERSION, clear_service_cache, get_services
from frontend.session_state import initialize_session
from frontend.ui_mode import runtime_provider_and_model


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = {
    "displaylogo": True,
    "displayModeBar": "hover",
    "responsive": True,
}


def _default_node_counts(rows: list[dict[str, Any]]):
    frame = pd.DataFrame(rows).sort_values("count", ascending=True)
    return px.bar(
        frame,
        x="count",
        y="label",
        orientation="h",
        title="노드 유형별 규모",
        labels={"count": "노드 수", "label": "노드 유형"},
    )


def _default_status_counts(rows: list[dict[str, Any]]):
    frame = pd.DataFrame(rows)
    return px.pie(
        frame,
        names="status",
        values="count",
        hole=0.58,
        title="질의 상태 구성",
    )


def _default_latency(rows: list[dict[str, Any]]):
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


def _render_pair(
    *,
    default_figure,
    polished_figure,
    key_prefix: str,
) -> None:
    default_column, polished_column = st.columns(2)
    with default_column:
        st.markdown(
            '<div class="p3-compare-label">기본 Plotly Express<span>BEFORE</span></div>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(
            default_figure,
            width="stretch",
            key=f"{key_prefix}-default",
            config=DEFAULT_CONFIG,
        )
    with polished_column:
        st.markdown(
            '<div class="p3-compare-label is-polished">제품 스타일 Plotly<span>AFTER</span></div>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(
            polished_figure,
            width="stretch",
            key=f"{key_prefix}-polished",
            theme=None,
            config=PLOTLY_CHART_CONFIG,
        )


def render_plotly_comparison(
    snapshot: dict[str, Any],
    *,
    project_id: str,
) -> None:
    snapshot = normalize_dashboard_snapshot(snapshot)
    runtime = snapshot["runtime"]

    st.markdown(
        f"""
        <section class="p3-plotly-comparison-hero" id="p3-main-content">
          <div>
            <small>Plotly · same data · same chart type</small>
            <h1>기본 설정과 제품 스타일 비교</h1>
            <p>동일한 Dashboard snapshot을 사용해 Plotly 기본값과 공통 제품 템플릿의 차이를 확인합니다. 데이터와 차트 종류는 유지하고 색상, 여백, 축, 툴팁, 범례, 카드와 반응형 높이만 개선했습니다.</p>
          </div>
          <a class="p3-workspace-link" href="/?workspace=dashboard" target="_self">Dashboard로 돌아가기 →</a>
        </section>
        """,
        unsafe_allow_html=True,
    )
    st.caption(f"현재 프로젝트 · {project_id} · 실시간 Dashboard snapshot")
    st.markdown(
        """
        <section class="p3-comparison-notes">
          <article><strong>시각적 계층</strong><span>Figure 내부 제목을 제거하고 페이지의 Board heading과 역할을 분리했습니다.</span></article>
          <article><strong>제품 팔레트</strong><span>ECharts Dashboard와 동일한 series·semantic 색상 체계를 적용했습니다.</span></article>
          <article><strong>정보 밀도</strong><span>차트 높이, 여백, 축 눈금과 긴 범주 배치를 현재 폭에 맞게 조정했습니다.</span></article>
          <article><strong>상호작용</strong><span>Hover label은 유지하고 발표에 불필요한 Modebar와 로고는 숨겼습니다.</span></article>
        </section>
        """,
        unsafe_allow_html=True,
    )

    node_tab, status_tab, latency_tab = st.tabs(
        ["범주 비교", "상태 구성", "시간 추세"]
    )
    with node_tab:
        rows = snapshot["node_counts"]
        if not rows:
            st.info("현재 프로젝트에는 노드 유형 집계가 없습니다.")
        else:
            _render_pair(
                default_figure=_default_node_counts(rows),
                polished_figure=build_node_counts_figure(rows),
                key_prefix="plotly-compare-node",
            )
    with status_tab:
        rows = runtime["status_counts"]
        if not rows:
            st.info("Query Studio 실행 이력이 없어 상태 구성을 비교할 수 없습니다.")
        else:
            _render_pair(
                default_figure=_default_status_counts(rows),
                polished_figure=build_status_counts_figure(rows),
                key_prefix="plotly-compare-status",
            )
    with latency_tab:
        rows = runtime["recent_queries"]
        if not rows or not any("elapsed_ms" in row for row in rows):
            st.info("응답시간이 포함된 최근 질의가 없어 시간 추세를 비교할 수 없습니다.")
        else:
            _render_pair(
                default_figure=_default_latency(rows),
                polished_figure=build_recent_latency_figure(rows),
                key_prefix="plotly-compare-latency",
            )


def render_plotly_comparison_route() -> None:
    """Resolve the active project and render the hidden comparison route."""

    initialize_session()
    project_id = str(
        st.query_params.get("project_id")
        or st.session_state.get("active_project_id", "cip-dmd")
    )
    provider, model_name = runtime_provider_and_model()
    st.sidebar.markdown("## Plotly UI Comparison")
    st.sidebar.caption("같은 데이터와 차트 종류의 Before / After")
    st.sidebar.markdown(
        '<a class="p3-workspace-link p3-workspace-link--stretch" '
        'href="/?workspace=dashboard" target="_self">← Dashboard로 돌아가기</a>',
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
    render_plotly_comparison(snapshot, project_id=project_id)


__all__ = ["render_plotly_comparison", "render_plotly_comparison_route"]
