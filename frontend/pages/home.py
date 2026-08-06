"""Landing page and active-project overview."""

from __future__ import annotations

from typing import Any

import streamlit as st

from backend.app.projects import ProjectRegistry
from frontend.api_client import FactoryGraphApiClient
from frontend.navigation import navigate_to_page, render_workspace_link
from frontend.project_workspace import (
    project_destination_page,
    relative_updated_at,
    status_presentation,
)
from frontend.runtime import PROJECT_ROOT, clear_service_cache
from frontend.sidebar import switch_project


def _switch_project(project_id: str) -> None:
    switch_project(
        project_id,
        project_root=PROJECT_ROOT,
        clear_services=clear_service_cache,
    )

def render_landing_overview() -> None:
    st.markdown(
        """
        <div class="p3-feature-grid">
          <div class="p3-feature">
            <b>01 · Ask</b>
            <p>제조 관계를 자연어로 질문합니다.</p>
          </div>
          <div class="p3-feature">
            <b>02 · Generate</b>
            <p>LLM이 읽기 전용 Cypher를 생성합니다.</p>
          </div>
          <div class="p3-feature">
            <b>03 · Verify</b>
            <p>의미·문법·쓰기 위험을 실행 전에 검사합니다.</p>
          </div>
          <div class="p3-feature">
            <b>04 · Trace</b>
            <p>조회 결과와 실제 관계 경로를 함께 확인합니다.</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_streamlit_landing() -> None:
    st.markdown(
        """
        <section class="p3-landing-hero">
          <div class="p3-landing-copy">
            <div class="p3-kicker">Manufacturing Knowledge Graph</div>
            <h1>Find the path.<span>Keep the proof.</span></h1>
            <p>
              제조 관계를 자연어로 묻고, 검증된 Cypher와 실제 그래프
              경로로 RCA 후보를 확인합니다. 추정한 답변이 아니라 조회한
              근거와 전문가 판정을 남깁니다.
            </p>
            <div class="p3-landing-proof">
              <span>Gold Question 15/15</span>
              <span>READ-only 100%</span>
              <span>Blind 26</span>
              <span>Expert HITL</span>
            </div>
          </div>
          <div class="p3-investigation">
            <div class="p3-investigation-head">
              <span>Live investigation</span><span>Verified</span>
            </div>
            <div class="p3-investigation-question">
              완제품 300002의 구성품과 각 공정·품질검사 결과를 보여줘.
            </div>
            <div class="p3-investigation-path">
              <b>Cylinder<br>300002</b><span>→</span>
              <b>Part<br>103504</b><span>→</span>
              <b>Process<br>CNC milling</b>
            </div>
            <div class="p3-cypher-preview">
              MATCH (c:Cylinder)-[:ASSEMBLED_FROM]-&gt;(p:Part)<br>
              OPTIONAL MATCH (p)-[:UNDERWENT]-&gt;(run:ProcessRun)<br>
              RETURN c, p, run
            </div>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    query_column, graph_column, spacer = st.columns([1, 1, 3])
    query_column.button(
        "RCA 질문 시작 →",
        type="primary",
        width="stretch",
        on_click=navigate_to_page,
        args=("Query Studio",),
    )
    graph_column.button(
        "그래프 탐색",
        width="stretch",
        on_click=navigate_to_page,
        args=("Graph Explorer",),
    )

    metric_columns = st.columns(4)
    metric_columns[0].metric("조립 완제품", "802")
    metric_columns[1].metric("Genealogy 완전성", "95.6%")
    metric_columns[2].metric("Blind 의미값 정확도", "61.5%")
    metric_columns[3].metric("관계 유형", "7")

    st.markdown(
        """
        <section class="p3-landing-section">
          <div class="p3-kicker" style="color:#0F766E">What the system proves</div>
          <h2>AI 답변보다 검증 경로를 설계합니다.</h2>
        </section>
        """,
        unsafe_allow_html=True,
    )
    render_landing_overview()
    st.markdown(
        """
        <section class="p3-landing-section">
          <div class="p3-kicker" style="color:#0F766E">Agent workflow</div>
          <h2>실행 전에 의심하고, 실행 후에 증명합니다.</h2>
          <div class="p3-workflow">
            <div><b>01 · Ask</b><span>현업 언어로 관계 질문</span></div>
            <div><b>02 · Generate</b><span>스키마 기반 Cypher 생성</span></div>
            <div><b>03 · Verify</b><span>READ-only·EXPLAIN·의미 검사</span></div>
            <div><b>04 · Trace</b><span>조회값·관계·전문가 판정</span></div>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    st.info(
        "사내 프로토타입에서는 질문, 실행 Cypher, 조회 결과, 관계 경로와 "
        "도메인 전문가 판정을 같은 앱에서 확인합니다.",
        icon="🔷",
    )
    render_home_project_overview()

def _fallback_next_action(project: dict[str, Any]) -> str:
    status = str(project.get("status", "draft"))
    if status in {"draft", "profiling", "failed"}:
        return "connect" if project.get("source_type") == "neo4j" else "upload"
    if status == "mapping_review":
        return "map"
    if status in {"loading", "validating"}:
        return "validate"
    if status == "evaluation_required":
        return "evaluate"
    return "query" if status == "ready" else "upload"

def _project_readiness_summary(
    project: dict[str, Any],
    api: FactoryGraphApiClient | None,
) -> dict[str, Any]:
    if api is not None:
        try:
            report = api.project_readiness(project["project_id"])
            return {
                "next_action": report["next_action"],
                "can_query": report["can_query"],
                "checks_passed": sum(
                    check.get("status") == "PASS"
                    for check in report.get("checks", {}).values()
                ),
                "checks_total": len(report.get("checks", {})),
                "versions": report.get("versions", {}),
            }
        except Exception:
            pass
    return {
        "next_action": _fallback_next_action(project),
        "can_query": project.get("status") == "ready",
        "checks_passed": None,
        "checks_total": None,
        "versions": {
            "source": project.get("source_version"),
            "schema": project.get("schema_version"),
            "evaluation": project.get("evaluation_version"),
        },
    }

def render_home_project_overview() -> None:
    registry = ProjectRegistry(
        PROJECT_ROOT / "data" / "processed" / "projects.sqlite3"
    )
    registry.ensure_default()
    projects = registry.list()
    active = next(
        (project for project in projects if project.get("is_active")),
        projects[0],
    )
    ready_count = sum(project["status"] == "ready" for project in projects)
    favorite_count = sum(bool(project.get("favorite")) for project in projects)

    st.markdown("### Workspace overview")
    overview = st.columns([1.5, 1, 1, 1])
    overview[0].metric("활성 프로젝트", active["name"])
    overview[1].metric("전체 프로젝트", len(projects))
    overview[2].metric("질의 가능", ready_count)
    overview[3].metric("즐겨찾기", favorite_count)

    st.markdown("#### 최근 프로젝트")
    api = FactoryGraphApiClient()
    api_available = api.live()
    try:
        for project in projects[:3]:
            presentation = status_presentation(project["status"])
            readiness = _project_readiness_summary(
                project, api if api_available else None
            )
            destination = project_destination_page(readiness)
            with st.container(border=True):
                title, status_column, action_column = st.columns([4, 1, 1])
                title.markdown(
                    f"**{'★ ' if project.get('favorite') else ''}"
                    f"{project['name']}**"
                )
                title.caption(
                    f"{project['domain_type']} · {project['dataset_name']} · "
                    f"{relative_updated_at(project['updated_at'])}"
                )
                status_column.markdown(f"`{presentation['label']}`")
                if action_column.button(
                    "작업 열기",
                    key=f"home-open-{project['project_id']}",
                    width="stretch",
                    help=f"{destination} 화면으로 이동",
                ):
                    _switch_project(project["project_id"])
                    navigate_to_page(destination)
                    st.rerun()
    finally:
        api.close()

    render_workspace_link(
        "모든 프로젝트 보기 →",
        "Projects",
    )
