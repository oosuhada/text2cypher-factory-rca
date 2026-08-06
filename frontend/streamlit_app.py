"""P3 manufacturing knowledge-graph RCA Streamlit application."""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from frontend.app_shell import render_app_shell
from frontend.common_ui import (
    render_foundation_workspace,
    render_startup_failure,
)
from frontend.design_system import ui_text
from frontend.navigation import render_page_header
from frontend.pages.audit import render_audit_workspace
from frontend.pages.dashboard import render_dashboard_tab
from frontend.pages.data_sources import render_data_health_tab
from frontend.pages.evaluations import render_evaluations_workspace
from frontend.pages.graph_explorer_page import render_graph_explorer
from frontend.pages.home import render_streamlit_landing
from frontend.pages.projects import render_projects_workspace
from frontend.pages.query_studio import render_chat_tab
from frontend.pages.schema_studio import render_schema_studio
from frontend.runtime import (
    SERVICE_BUNDLE_VERSION,
    clear_service_cache,
    get_services,
)
from frontend.session_state import initialize_session
from frontend.sidebar import render_sidebar as render_sidebar_shell


APP_TITLE = "Factory Graph RCA"


render_app_shell(APP_TITLE)


def main() -> None:
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
    if page in {
        "Approval Queue",
        "Admin",
    }:
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


if __name__ == "__main__":
    main()
