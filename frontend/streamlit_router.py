"""Single hidden Streamlit router for canonical and legacy URLs."""

from __future__ import annotations

from functools import partial

import streamlit as st

from frontend.internal_console import render_internal_console
from frontend.legacy_page_redirect import redirect_legacy_page


LEGACY_ROUTE_WORKSPACES = {
    "audit": "audit_logs",
    "dashboard": "dashboard",
    "data_sources": "data_sources",
    "evaluations": "evaluations",
    "evidence": "query_studio",
    "graph_explorer_page": "graph_explorer",
    "home": "home",
    "projects": "projects",
    "query_studio": "query_studio",
    "schema_studio": "pipeline",
}


def build_hidden_navigation() -> st.navigation:
    pages = [
        st.Page(
            render_internal_console,
            title="Internal Console",
            icon="🛠️",
            default=True,
        )
    ]
    pages.extend(
        st.Page(
            partial(redirect_legacy_page, workspace_key),
            title=f"Legacy {route}",
            url_path=route,
        )
        for route, workspace_key in LEGACY_ROUTE_WORKSPACES.items()
    )
    return st.navigation(pages, position="hidden")
