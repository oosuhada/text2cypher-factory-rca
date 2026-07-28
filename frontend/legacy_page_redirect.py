"""Compatibility notice for Streamlit's former automatic page URLs."""

from __future__ import annotations

from html import escape
from urllib.parse import urlencode

import streamlit as st


LEGACY_PAGE_REDIRECT_MARKER = "p3-streamlit-legacy-page-redirect-v2"


def legacy_workspace_url(
    workspace_key: str,
    project_id: str | None = None,
) -> str:
    query_params = {"workspace": workspace_key}
    if project_id:
        query_params["project_id"] = project_id
    return f"/?{urlencode(query_params)}"


def redirect_legacy_page(workspace_key: str) -> None:
    """Render a safe migration notice for an old ``/page_name`` bookmark.

    The framework-reserved automatic sidebar is disabled. Old page URLs remain
    as compatibility entrypoints so saved bookmarks never produce a white
    screen. The user is sent to the canonical custom-router URL with the
    selected project preserved.
    """

    project_id = st.query_params.get("project_id")
    target = legacy_workspace_url(
        workspace_key,
        str(project_id) if project_id else None,
    )
    st.set_page_config(
        page_title="Factory Graph RCA — Internal Console",
        layout="wide",
    )
    st.title("내부 콘솔 주소가 변경되었습니다.")
    st.write(
        "이 주소는 이전 Streamlit 자동 페이지 경로입니다. "
        "현재는 하나의 작업공간 내비게이션만 사용합니다."
    )
    st.markdown(
        (
            '<a href="'
            f"{escape(target, quote=True)}"
            '" target="_self" style="display:inline-block;padding:.75rem 1rem;'
            'border-radius:.6rem;background:#0F766E;color:white;'
            'text-decoration:none;font-weight:700">'
            "정식 작업공간 열기 →</a>"
        ),
        unsafe_allow_html=True,
    )
    st.caption(f"새 주소: {target}")
