"""Project catalog and project-creation workspace."""

from __future__ import annotations

import streamlit as st

from backend.app.projects import ProjectRegistry
from frontend.api_client import FactoryGraphApiClient
from frontend.common_ui import render_view_state
from frontend.design_system import Role, ViewState
from frontend.navigation import navigate_to_page, render_page_header
from frontend.pages.home import _project_readiness_summary
from frontend.project_workspace import (
    filter_projects,
    next_action_presentation,
    relative_updated_at,
    status_presentation,
)
from frontend.runtime import PROJECT_ROOT, clear_service_cache
from frontend.sidebar import switch_project
from frontend.ui_mode import configured_role, current_ui_mode, is_development


def _switch_project(project_id: str) -> None:
    switch_project(
        project_id,
        project_root=PROJECT_ROOT,
        clear_services=clear_service_cache,
    )

def render_projects_workspace() -> None:
    render_page_header("Projects")
    registry = ProjectRegistry(
        PROJECT_ROOT / "data" / "processed" / "projects.sqlite3"
    )
    registry.ensure_default()
    mode = current_ui_mode()
    role = (
        Role(st.session_state.get("preview_role", Role.ADMIN.value))
        if is_development(mode)
        else configured_role(mode)
    )

    search_column, status_column, favorite_column = st.columns([3, 2, 1])
    search = search_column.text_input(
        "프로젝트 검색",
        placeholder="이름, ID, 도메인, 담당자",
        key="project-search",
    )
    all_statuses = list(status_presentation(status)["status"] for status in (
        "draft",
        "profiling",
        "mapping_review",
        "loading",
        "validating",
        "evaluation_required",
        "ready",
        "failed",
    ))
    selected_statuses = status_column.multiselect(
        "상태",
        all_statuses,
        format_func=lambda value: status_presentation(value)["label"],
        key="project-status-filter",
    )
    favorites_only = favorite_column.toggle(
        "즐겨찾기만",
        key="project-favorites-only",
    )

    projects = filter_projects(
        registry.list(),
        search=search,
        statuses=set(selected_statuses),
        favorites_only=favorites_only,
    )
    if not projects:
        render_view_state(
            ViewState.EMPTY,
            page="Projects",
            detail="현재 검색·상태 조건에 일치하는 프로젝트가 없습니다.",
        )
    else:
        api = FactoryGraphApiClient()
        api_available = api.live()
        try:
            for project in projects:
                presentation = status_presentation(project["status"])
                readiness = _project_readiness_summary(
                    project, api if api_available else None
                )
                next_action = next_action_presentation(
                    readiness["next_action"]
                )
                with st.container(border=True):
                    head, status_area = st.columns([4, 1])
                    head.markdown(
                        f"### {'★ ' if project.get('favorite') else ''}"
                        f"{project['name']}"
                    )
                    head.caption(
                        f"`{project['project_id']}` · "
                        f"{project['industry']} / {project['domain_type']} · "
                        f"담당 {project.get('owner') or '미지정'}"
                    )
                    status_area.markdown(f"**{presentation['label']}**")
                    status_area.progress(presentation["progress"])
                    if project.get("description"):
                        st.write(project["description"])

                    metadata = st.columns(4)
                    metadata[0].caption(
                        f"데이터 · {project['dataset_name']}"
                    )
                    metadata[1].caption(
                        f"소스 · {project['source_type']}"
                    )
                    metadata[2].caption(
                        f"스키마 · {project.get('schema_version') or '미정'}"
                    )
                    metadata[3].caption(
                        relative_updated_at(project["updated_at"])
                    )
                    if readiness["checks_total"]:
                        st.caption(
                            f"Readiness · {readiness['checks_passed']}/"
                            f"{readiness['checks_total']} gate 통과"
                        )

                    favorite_action, open_action, next_action_column = (
                        st.columns([1, 1, 2])
                    )
                    if favorite_action.button(
                        "★ 해제" if project.get("favorite") else "☆ 저장",
                        key=f"favorite-{project['project_id']}",
                        width="stretch",
                    ):
                        registry.update(
                            project["project_id"],
                            favorite=not bool(project.get("favorite")),
                        )
                        st.rerun()
                    if open_action.button(
                        "현재 프로젝트"
                        if project.get("is_active")
                        else "전환",
                        key=f"open-project-{project['project_id']}",
                        disabled=bool(project.get("is_active")),
                        width="stretch",
                    ):
                        _switch_project(project["project_id"])
                        st.rerun()
                    if next_action_column.button(
                        f"다음 · {next_action['label']} →",
                        key=f"next-project-{project['project_id']}",
                        type="primary",
                        width="stretch",
                    ):
                        _switch_project(project["project_id"])
                        navigate_to_page(next_action["page"])
                        st.rerun()
        finally:
            api.close()

    if role not in {Role.DATA_STEWARD, Role.ADMIN}:
        st.info(
            "새 프로젝트 생성은 Data Steward 또는 Admin 권한이 필요합니다."
        )
        return

    st.divider()
    st.markdown("### 새 프로젝트 만들기")
    st.caption(
        "기본정보와 데이터 소스 유형을 등록하면 해당 프로젝트의 "
        "Data Sources 화면으로 바로 이동합니다."
    )
    st.markdown(
        """
        <div class="p3-trust-strip">
          <span>1 · 기본정보</span><span>2 · 소스 선택</span>
          <span>3 · 보안·담당자</span><span>4 · Data Sources</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.form("enterprise-create-project"):
        identity, ownership = st.columns(2)
        with identity:
            project_id = st.text_input(
                "프로젝트 ID *",
                placeholder="semiconductor-yield",
                help="영문 소문자로 시작하는 3~63자 ID",
            )
            name = st.text_input(
                "프로젝트 이름 *", placeholder="반도체 수율 RCA"
            )
            description = st.text_area(
                "설명",
                placeholder="이 프로젝트가 해결할 업무 문제를 적습니다.",
            )
            industry = st.text_input("산업 *", value="manufacturing")
            domain_type = st.text_input(
                "도메인 *", placeholder="semiconductor-process"
            )
        with ownership:
            source_type = st.radio(
                "첫 데이터 소스 *",
                options=("file", "neo4j"),
                format_func=lambda value: {
                    "file": "파일 업로드 · CSV/JSON/XLSX/ZIP",
                    "neo4j": "기존 Neo4j 연결",
                }[value],
            )
            dataset_name = st.text_input(
                "데이터셋/연결 이름 *",
                placeholder="Fab process history",
            )
            owner = st.text_input("담당자", placeholder="data-steward")
            security = st.selectbox(
                "보안 등급",
                options=("internal", "confidential", "restricted"),
                format_func=lambda value: {
                    "internal": "Internal",
                    "confidential": "Confidential",
                    "restricted": "Restricted",
                }[value],
            )
        submitted = st.form_submit_button(
            "프로젝트 생성 후 데이터 등록",
            type="primary",
            width="stretch",
        )
    if submitted:
        try:
            created = registry.create(
                project_id=project_id,
                name=name,
                description=description,
                industry=industry,
                domain_type=domain_type,
                dataset_name=dataset_name,
                owner=owner,
                security_classification=security,
                source_type=source_type,
            )
            _switch_project(created["project_id"])
            navigate_to_page("Data Sources")
            st.session_state["project_created_notice"] = created["name"]
            st.rerun()
        except ValueError as error:
            st.error(str(error))


if __name__ == "__main__":
    from frontend.legacy_page_redirect import redirect_legacy_page

    redirect_legacy_page("projects")
