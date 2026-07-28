"""Streamlit navigation state and shared workspace chrome."""

from __future__ import annotations

from typing import Any, MutableMapping

import streamlit as st

from frontend.design_system import (
    NAVIGATION_ITEMS,
    PAGE_BY_KEY,
    PAGE_BY_LABEL,
    Role,
    navigation_for_role,
    page_description,
    ui_text,
)


NAVIGATION_PAGES = tuple(item.label for item in NAVIGATION_ITEMS)


def navigate_to_page(page: str) -> None:
    if page in NAVIGATION_PAGES:
        st.session_state["pending_page"] = page


def workspace_url(page: str) -> str:
    return f"/?workspace={PAGE_BY_LABEL[page].key}"


def apply_navigation_request(
    state: MutableMapping[str, Any],
    role: Role,
    requested_workspace: str | None,
) -> tuple[str, tuple[str, ...]]:
    """Resolve URL and queued navigation before the radio widget is mounted."""

    allowed_pages = tuple(item.label for item in navigation_for_role(role))
    if (
        requested_workspace in PAGE_BY_KEY
        and requested_workspace != state.get("consumed_workspace_query")
    ):
        requested_page = PAGE_BY_KEY[requested_workspace].label
        if requested_page in allowed_pages:
            state["pending_page"] = requested_page
        state["consumed_workspace_query"] = requested_workspace
    pending_page = state.pop("pending_page", None)
    if pending_page in allowed_pages:
        state["active_page"] = pending_page
        state["navigation_widget_revision"] = (
            int(state.get("navigation_widget_revision", 0)) + 1
        )
    if state.get("active_page") not in allowed_pages:
        state["active_page"] = "Home"
    return state["active_page"], allowed_pages


def render_workspace_link(
    label: str,
    page: str,
    *,
    stretch: bool = False,
) -> None:
    width_class = " p3-workspace-link--stretch" if stretch else ""
    st.markdown(
        (
            f'<a class="p3-workspace-link{width_class}" '
            f'href="{workspace_url(page)}" target="_self">{label}</a>'
        ),
        unsafe_allow_html=True,
    )


def render_page_header(page: str) -> None:
    item = PAGE_BY_LABEL[page]
    locale = st.session_state.get("locale", "ko")
    badge = (
        ui_text("operational", locale)
        if item.delivery == "available"
        else (
            f"Stage {item.implementation_stage} "
            f"{ui_text('preparing', locale)}"
        )
    )
    heading_column, home_column = st.columns([5, 1])
    with heading_column:
        st.markdown(
            f"""
            <section class="p3-page-head" id="p3-main-content">
              <div>
                <h1>{item.icon} {item.label}</h1>
                <p>{page_description(page, locale)}</p>
                <span class="p3-stage-badge">{badge}</span>
              </div>
            </section>
            """,
            unsafe_allow_html=True,
        )
    with home_column:
        st.caption("현재 작업공간")
        render_workspace_link("← 운영 홈으로", "Home", stretch=True)


def render_sidebar_navigation(role: Role) -> str:
    st.sidebar.markdown("### 작업공간 이동")
    current_page, allowed_pages = apply_navigation_request(
        st.session_state,
        role,
        st.query_params.get("workspace"),
    )
    page = st.sidebar.radio(
        "Navigation",
        options=allowed_pages,
        index=allowed_pages.index(current_page),
        key=(
            "navigation-"
            f"{st.session_state['navigation_widget_revision']}"
        ),
        format_func=lambda label: (
            f"{PAGE_BY_LABEL[label].icon}  {label}"
            + (
                f"  · {PAGE_BY_LABEL[label].implementation_stage}"
                if PAGE_BY_LABEL[label].delivery == "foundation"
                else ""
            )
        ),
        label_visibility="collapsed",
    )
    if page != current_page:
        st.session_state["active_page"] = page
        workspace_key = PAGE_BY_LABEL[page].key
        st.session_state["consumed_workspace_query"] = workspace_key
        st.query_params["workspace"] = workspace_key
    st.sidebar.caption(
        f"{role.value} 권한 · {len(allowed_pages)}개 작업공간"
    )
    return page

