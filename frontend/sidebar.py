"""Streamlit sidebar composition for project, navigation, history, and settings."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

import streamlit as st

from backend.app.projects import ProjectRegistry
from frontend.design_system import Role
from frontend.navigation import navigate_to_page, render_sidebar_navigation
from frontend.session_state import (
    get_conversation_store,
    open_conversation,
    start_new_conversation,
    switch_project_state,
)


def switch_project(
    project_id: str,
    *,
    project_root: Path,
    clear_services: Callable[[], None],
) -> None:
    changed = switch_project_state(
        st.session_state,
        project_id,
        get_conversation_store(project_root),
    )
    if not changed:
        return
    ProjectRegistry(
        project_root / "data" / "processed" / "projects.sqlite3"
    ).activate(project_id)
    clear_services()
    st.toast(f"{project_id} 워크스페이스로 전환했습니다.", icon="✅")


def _render_sidebar_conversations(
    project_id: str,
    *,
    project_root: Path,
) -> None:
    st.sidebar.markdown("### 대화")
    if st.sidebar.button(
        "＋ 새 대화",
        type="primary",
        width="stretch",
        key="sidebar-new-conversation",
    ):
        start_new_conversation()
        navigate_to_page("Query Studio")
        st.rerun()
    conversations = st.session_state["conversations"]
    if not conversations:
        st.sidebar.caption("질문을 실행하면 최근 대화가 여기에 표시됩니다.")
        return

    st.sidebar.caption("프로젝트에 저장된 최근 대화 · 최대 12개")
    history_search = st.sidebar.text_input(
        "대화 검색",
        placeholder="질문 제목 또는 내용",
        key=f"conversation-search-{project_id}",
    )
    visible_conversations = (
        get_conversation_store(project_root).list(
            project_id,
            search=history_search,
            limit=12,
        )
        if history_search.strip()
        else conversations
    )
    for conversation in visible_conversations[:6]:
        is_active = (
            conversation["id"]
            == st.session_state["active_conversation_id"]
        )
        label = (
            f"● {conversation['title']}"
            if is_active
            else conversation["title"]
        )
        if st.sidebar.button(
            label,
            key=f"conversation-{conversation['id']}",
            width="stretch",
            disabled=is_active,
        ):
            open_conversation(conversation["id"])
            navigate_to_page("Query Studio")
            st.rerun()
    if st.sidebar.button(
        "프로젝트 대화 모두 지우기",
        key="clear-all-conversations",
        width="stretch",
    ):
        get_conversation_store(project_root).delete_project(project_id)
        st.session_state["conversations"] = []
        st.session_state["active_conversation_id"] = str(uuid4())
        st.session_state["messages"] = []
        st.session_state["last_result"] = None
        st.rerun()


def _render_sidebar_project(
    project_rows: list[dict[str, Any]],
    active_project_id: str,
    role: Role,
    *,
    project_root: Path,
    clear_services: Callable[[], None],
) -> str:
    project_ids = [row["project_id"] for row in project_rows]
    st.sidebar.markdown("### 프로젝트")
    selected_project_id = st.sidebar.selectbox(
        "활성 워크스페이스",
        project_ids,
        index=project_ids.index(active_project_id),
        format_func=lambda value: next(
            row["name"] for row in project_rows if row["project_id"] == value
        ),
    )
    if selected_project_id != active_project_id:
        switch_project(
            selected_project_id,
            project_root=project_root,
            clear_services=clear_services,
        )
        st.rerun()
    if role in {Role.DATA_STEWARD, Role.ADMIN}:
        if st.sidebar.button(
            "＋ 프로젝트 만들기",
            key="sidebar-create-project",
            width="stretch",
        ):
            navigate_to_page("Projects")
            st.rerun()
    return selected_project_id


def _render_sidebar_execution(role: Role) -> tuple[str, str]:
    st.sidebar.markdown("### 실행 설정")
    if role in {Role.DATA_STEWARD, Role.ADMIN}:
        provider = st.sidebar.selectbox(
            "생성 모드",
            options=("auto", "gemini", "gold", "openai"),
            format_func=lambda value: (
                {
                    "auto": "자동 · OpenAI 없으면 Gemini",
                    "gemini": "Vertex Gemini · 자유 질문",
                    "gold": "Gold Question 데모 · 정답셋 전용",
                    "openai": "OpenAI · 자유 질문",
                }[value]
            ),
        )
        use_openai_model = provider == "openai" or (
            provider == "auto" and bool(os.getenv("OPENAI_API_KEY"))
        )
        default_model = (
            os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
            if use_openai_model
            else os.getenv("GOOGLE_VERTEX_MODEL", "gemini-2.5-flash")
        )
        model_name = st.sidebar.text_input(
            "생성 모델",
            value=default_model,
            disabled=provider == "gold",
            key=f"model-name-{provider}",
        )
        if provider == "gold":
            st.sidebar.info(
                "추천 질문과 Gold Question 정답셋 15개만 정확히 "
                "실행하는 회귀검증 모드입니다."
            )
        elif provider == "gemini":
            st.sidebar.info(
                "Vertex AI Gemini로 새로운 자연어 질문을 처리합니다."
            )
        elif provider == "auto":
            st.sidebar.info(
                "OpenAI 키가 없으면 Vertex AI Gemini를 자동 사용합니다."
            )
        else:
            st.sidebar.caption("OPENAI_API_KEY 환경변수가 필요합니다.")
    else:
        provider = "auto"
        model_name = (
            os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
            if os.getenv("OPENAI_API_KEY")
            else os.getenv("GOOGLE_VERTEX_MODEL", "gemini-2.5-flash")
        )
        st.sidebar.caption(
            "모델과 provider는 Data Steward 또는 Admin이 관리합니다."
        )
    return provider, model_name


def render_sidebar(
    *,
    project_root: Path,
    clear_services: Callable[[], None],
) -> tuple[str, str, str, str]:
    registry = ProjectRegistry(
        project_root / "data" / "processed" / "projects.sqlite3"
    )
    registry.ensure_default()
    project_rows = registry.list()
    project_ids = [row["project_id"] for row in project_rows]
    active_project_id = st.session_state.get(
        "active_project_id", registry.active_project_id() or "cip-dmd"
    )
    if active_project_id not in project_ids:
        active_project_id = project_ids[0]

    requested_project_id = st.query_params.get("project_id")
    if (
        requested_project_id in project_ids
        and requested_project_id != active_project_id
    ):
        switch_project(
            requested_project_id,
            project_root=project_root,
            clear_services=clear_services,
        )
        active_project_id = requested_project_id
    elif requested_project_id and requested_project_id not in project_ids:
        st.sidebar.warning(
            "요청한 프로젝트를 찾을 수 없어 현재 프로젝트를 유지합니다."
        )
    role = Role(st.session_state.get("preview_role", Role.ADMIN.value))

    st.sidebar.markdown("## Factory Graph RCA")
    st.sidebar.caption(
        "Internal Console · 데이터·평가·운영 진단 전용"
    )
    selected_project_id = _render_sidebar_project(
        project_rows,
        active_project_id,
        role,
        project_root=project_root,
        clear_services=clear_services,
    )
    st.sidebar.divider()

    page = render_sidebar_navigation(role)
    st.sidebar.divider()

    _render_sidebar_conversations(
        selected_project_id,
        project_root=project_root,
    )
    st.sidebar.divider()

    provider, model_name = _render_sidebar_execution(role)
    st.sidebar.divider()

    role_value = st.sidebar.selectbox(
        "역할 미리보기",
        options=tuple(candidate.value for candidate in Role),
        key="preview_role",
        help=(
            "2-1 UI 권한 설계를 검증하는 프로토타입입니다. "
            "실제 사용자 인증·SSO는 Admin 단계에서 연결합니다."
        ),
    )
    st.session_state["active_role"] = Role(role_value).value
    st.sidebar.divider()

    locale_label = st.sidebar.segmented_control(
        "언어 / Language",
        options=("한국어", "English"),
        default=(
            "English"
            if st.session_state.get("locale") == "en"
            else "한국어"
        ),
        key="locale-control",
    )
    st.session_state["locale"] = (
        "en" if locale_label == "English" else "ko"
    )
    st.sidebar.divider()

    st.sidebar.markdown("### 안전 설정")
    st.sidebar.success("Neo4j reader mode")
    st.sidebar.caption(
        "쓰기 의도 차단 · Cypher 검사 · EXPLAIN · DB read-only"
    )
    return page, provider, model_name, selected_project_id

