"""Internal Console workspace renderer used by the hidden Streamlit router."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from frontend.common_ui import (
    render_foundation_workspace,
    render_startup_failure,
)
from frontend.design_system import ui_text
from frontend.navigation import render_page_header
from frontend.runtime import (
    SERVICE_BUNDLE_VERSION,
    clear_service_cache,
    get_services,
)
from frontend.session_state import initialize_session
from frontend.sidebar import render_sidebar as render_sidebar_shell
from frontend.workspaces.audit import render_audit_workspace
from frontend.workspaces.dashboard import render_dashboard_tab
from frontend.workspaces.data_sources import render_data_health_tab
from frontend.workspaces.evaluations import render_evaluations_workspace
from frontend.workspaces.graph_explorer import render_graph_explorer
from frontend.workspaces.home import render_streamlit_landing
from frontend.workspaces.projects import render_projects_workspace
from frontend.workspaces.query_studio import render_chat_tab
from frontend.workspaces.schema_studio import render_schema_studio


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def render_internal_console() -> None:
    initialize_session()
    page, provider, model_name, project_id = render_sidebar_shell(
        project_root=PROJECT_ROOT,
        clear_services=clear_service_cache,
    )
    st.markdown(
        '<a class="p3-skip-link" href="#p3-main-content">'
        f'{ui_text("skip", st.session_state.get("locale", "ko"))}</a>',
        unsafe_allow_html=True,
    )
    if page == "Home":
        render_streamlit_landing()
        return
    if page == "Projects":
        render_projects_workspace()
        return
    if page in {"Approval Queue", "Admin"}:
        render_foundation_workspace(page)
        return
    if page == "Pipeline":
        render_schema_studio()
        return
    if page not in {"Evaluations", "Audit Logs"}:
        render_page_header(page)
    try:
        services = get_services(
            provider,
            model_name,
            SERVICE_BUNDLE_VERSION,
            project_id,
        )
    except Exception as error:
        if page == "Data Sources":
            st.warning(f"질의 서비스 연결 전 데이터 온보딩 모드입니다: {error}")
            render_data_health_tab(None, None)
            return
        render_startup_failure(
            error,
            project_root=PROJECT_ROOT,
            clear_services=clear_service_cache,
        )
        return
    st.session_state["_active_service_bundle"] = services
    st.sidebar.caption(
        f"실제 연결: {services.provider} / {services.model_name} · "
        f"{getattr(services, 'transport', 'direct')}"
    )
    try:
        dashboard_snapshot = services.dashboard.snapshot()
    except Exception as error:
        dashboard_snapshot = None
        st.warning(f"대시보드 진단 일부를 불러오지 못했습니다: {error}")

    if page == "Query Studio":
        render_chat_tab(services)
    elif page == "Graph Explorer":
        render_graph_explorer(services)
    elif page == "Dashboard":
        render_dashboard_tab(services, dashboard_snapshot)
    elif page == "Evaluations":
        render_evaluations_workspace(services, dashboard_snapshot)
    elif page == "Audit Logs":
        render_audit_workspace()
    elif page == "Data Sources":
        render_data_health_tab(services, dashboard_snapshot)
