"""Landing page and active-project overview."""

from __future__ import annotations

import os
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
            <b>01 · Data</b>
            <p>데이터 소스, 업로드 이력과 프로파일을 점검합니다.</p>
          </div>
          <div class="p3-feature">
            <b>02 · Pipeline</b>
            <p>매핑, dry-run, 적재와 무결성 상태를 관리합니다.</p>
          </div>
          <div class="p3-feature">
            <b>03 · Evaluate</b>
            <p>Gold·Blind 회귀평가와 실패 유형을 확인합니다.</p>
          </div>
          <div class="p3-feature">
            <b>04 · Audit</b>
            <p>질의·ETL·평가 실행과 운영 증적을 추적합니다.</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_streamlit_landing() -> None:
    product_url = os.getenv("P3_PRODUCT_UI_URL", "http://localhost:3000")
    st.markdown(
        """
        <section class="p3-landing-hero">
          <div class="p3-landing-copy">
            <div class="p3-kicker">Internal Operations Console</div>
            <h1>Factory Graph RCA<span>Internal Console</span></h1>
            <p>
              이 화면은 데이터 온보딩, 그래프 적재, 평가와 운영 진단을
              위한 내부 콘솔입니다. 최종 사용자 RCA 질문과 근거 탐색은
              React 제품 UI에서 수행합니다.
            </p>
            <div class="p3-landing-proof">
              <span>Data operations</span>
              <span>Evaluation</span>
              <span>Audit</span>
              <span>Diagnostics</span>
            </div>
          </div>
          <div class="p3-investigation">
            <div class="p3-investigation-head">
              <span>Surface boundary</span><span>Internal only</span>
            </div>
            <div class="p3-investigation-question">
              제품 질의·Evidence·History는 React가 소유합니다.
            </div>
            <div class="p3-investigation-path">
              <b>Data<br>Source</b><span>→</span>
              <b>Graph<br>Pipeline</b><span>→</span>
              <b>Evaluate<br>Audit</b>
            </div>
            <div class="p3-cypher-preview">
              Product UI  · React :3000<br>
              Internal Console · Streamlit :8501<br>
              Source of truth · FastAPI :8000
            </div>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    product_column, project_column, spacer = st.columns([1.25, 1, 2.75])
    product_column.link_button(
        "React 제품 UI 열기 →",
        product_url,
        type="primary",
        width="stretch",
    )
    project_column.button(
        "프로젝트 운영 보기",
        width="stretch",
        on_click=navigate_to_page,
        args=("Projects",),
    )

    st.markdown(
        """
        <section class="p3-landing-section">
          <div class="p3-kicker" style="color:#0F766E">Internal responsibilities</div>
          <h2>제품 기능과 운영 기능을 분리합니다.</h2>
        </section>
        """,
        unsafe_allow_html=True,
    )
    render_landing_overview()

    st.markdown("### 운영 바로가기")
    shortcuts = st.columns(4)
    for column, label, page in zip(
        shortcuts,
        ("데이터 소스", "파이프라인", "평가", "감사 로그"),
        ("Data Sources", "Pipeline", "Evaluations", "Audit Logs"),
        strict=True,
    ):
        column.button(
            label,
            key=f"console-shortcut-{page}",
            width="stretch",
            on_click=navigate_to_page,
            args=(page,),
        )

    st.info(
        "최종 사용자 발표 여정은 React 제품 UI에서 완결합니다. "
        "Streamlit은 데이터·평가·감사·장애 진단에만 사용합니다.",
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


if __name__ == "__main__":
    from frontend.legacy_page_redirect import redirect_legacy_page

    redirect_legacy_page("home")
