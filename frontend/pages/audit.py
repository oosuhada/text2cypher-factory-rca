"""Read-only audit and conversation-history workspace."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from frontend.api_client import FactoryGraphApiClient
from frontend.common_ui import render_view_state
from frontend.design_system import Action, Role, ViewState, can_perform
from frontend.navigation import navigate_to_page, render_page_header
from frontend.session_state import get_conversation_store, open_conversation

def render_audit_workspace() -> None:
    render_page_header("Audit Logs")
    project_id = st.session_state.get("active_project_id", "cip-dmd")
    active_role = Role(
        st.session_state.get("active_role", Role.VIEWER.value)
    )
    api = FactoryGraphApiClient()
    search = st.text_input(
        "감사 이력 검색",
        placeholder="run ID, 질문, 상태 또는 작업명",
        key=f"audit-search-{project_id}",
    )
    event_type_label = st.segmented_control(
        "이벤트 유형",
        options=("전체", "질의", "ETL", "평가"),
        default="전체",
        key=f"audit-type-{project_id}",
    )
    event_type = {
        "전체": None,
        "질의": "query",
        "ETL": "etl",
        "평가": "evaluation",
    }[event_type_label or "전체"]
    try:
        payload = api.audit_events(
            project_id,
            event_type=event_type,
            search=search,
            limit=500,
        )
        health = api.health()
    except Exception as error:
        api.close()
        render_view_state(
            ViewState.ERROR,
            page="Audit Logs",
            detail=f"감사 서비스에 연결하지 못했습니다: {error}",
        )
        return

    events = payload.get("events", [])
    summary_columns = st.columns(5)
    summary_columns[0].metric("현재 프로젝트", project_id)
    summary_columns[1].metric("표시 이벤트", len(events))
    summary_columns[2].metric(
        "질의", sum(event["event_type"] == "query" for event in events)
    )
    summary_columns[3].metric(
        "ETL", sum(event["event_type"] == "etl" for event in events)
    )
    summary_columns[4].metric(
        "평가",
        sum(event["event_type"] == "evaluation" for event in events),
    )

    history_tab, timeline_tab, detail_tab, diagnostics_tab = st.tabs(
        ["대화 History", "운영 Timeline", "Run detail", "서비스 진단"]
    )
    with history_tab:
        conversation_search = st.text_input(
            "프로젝트 대화 검색",
            placeholder="질문 또는 대화 제목",
            key=f"audit-conversation-search-{project_id}",
        )
        conversations = get_conversation_store().list(
            project_id, search=conversation_search, limit=50
        )
        if not conversations:
            render_view_state(
                ViewState.EMPTY,
                page="Audit Logs",
                detail="이 프로젝트에 저장된 대화가 없습니다.",
            )
        for conversation in conversations:
            with st.container(border=True):
                columns = st.columns([5, 1, 1])
                columns[0].markdown(f"**{conversation['title']}**")
                columns[0].caption(
                    f"{conversation['updated_at']} · "
                    f"{len(conversation['messages'])} messages"
                )
                if columns[1].button(
                    "재열기",
                    key=f"audit-open-{conversation['id']}",
                    width="stretch",
                ):
                    open_conversation(conversation["id"])
                    navigate_to_page("Query Studio")
                    st.rerun()
                last_result = conversation.get("last_result") or {}
                rerun_question = last_result.get("question")
                if columns[2].button(
                    "재실행",
                    key=f"audit-rerun-conversation-{conversation['id']}",
                    width="stretch",
                    disabled=(
                        not bool(rerun_question)
                        or not can_perform(
                            active_role, Action.RERUN_QUERY
                        )
                    ),
                ):
                    open_conversation(conversation["id"])
                    st.session_state["pending_audit_question"] = rerun_question
                    navigate_to_page("Query Studio")
                    st.rerun()
    with timeline_tab:
        if not events:
            render_view_state(
                ViewState.EMPTY,
                page="Audit Logs",
                detail="선택한 범위에 감사 이벤트가 없습니다.",
            )
        else:
            timeline_rows = [
                {
                    "timestamp": event.get("timestamp"),
                    "type": event.get("event_type"),
                    "run_id": event.get("run_id"),
                    "title": event.get("title"),
                    "status": event.get("status"),
                    "schema": event.get("schema_version"),
                    "prompt": event.get("prompt_version"),
                }
                for event in events
            ]
            st.dataframe(
                pd.DataFrame(timeline_rows),
                width="stretch",
                hide_index=True,
            )
            st.download_button(
                "감사 Timeline CSV 다운로드",
                data=pd.DataFrame(timeline_rows).to_csv(
                    index=False
                ).encode("utf-8-sig"),
                file_name=f"{project_id}-audit-timeline.csv",
                mime="text/csv",
            )
    with detail_tab:
        if events:
            selected_run_id = st.selectbox(
                "Run ID",
                options=[event["run_id"] for event in events],
                format_func=lambda value: next(
                    (
                        f"{event['event_type']} · {event.get('title')} · {value}"
                        for event in events
                        if event["run_id"] == value
                    ),
                    value,
                ),
                key=f"audit-run-detail-{project_id}",
            )
            try:
                detail = api.audit_run(project_id, selected_run_id)
            except Exception as error:
                st.error(f"Run detail을 불러오지 못했습니다: {error}")
                detail = {}
            if detail:
                details = st.columns(5)
                details[0].metric("유형", detail.get("event_type", "—"))
                details[1].metric("상태", detail.get("status", "—"))
                details[2].metric(
                    "Schema", detail.get("schema_version") or "—"
                )
                details[3].metric(
                    "Prompt", detail.get("prompt_version") or "—"
                )
                details[4].metric(
                    "Provider", detail.get("provider") or "—"
                )
                if detail.get("question"):
                    st.markdown("##### 질문")
                    st.write(detail["question"])
                if detail.get("cypher"):
                    st.markdown("##### 실행 Cypher")
                    st.code(
                        detail["cypher"],
                        language="cypher",
                        line_numbers=True,
                    )
                st.markdown("##### 재현 증적")
                st.json(detail, expanded=False)
                action_columns = st.columns([1, 1, 4])
                action_columns[0].download_button(
                    "JSON 다운로드",
                    data=json.dumps(detail, ensure_ascii=False, indent=2),
                    file_name=f"{selected_run_id}.json",
                    mime="application/json",
                    width="stretch",
                )
                if action_columns[1].button(
                    "질문 재실행",
                    key=f"audit-rerun-{selected_run_id}",
                    disabled=(
                        not bool(detail.get("question"))
                        or not can_perform(
                            active_role, Action.RERUN_QUERY
                        )
                    ),
                    width="stretch",
                ):
                    st.session_state["pending_audit_question"] = detail[
                        "question"
                    ]
                    navigate_to_page("Query Studio")
                    st.rerun()
    with diagnostics_tab:
        required_checks = [
            check
            for check in health.get("checks", [])
            if check.get("required")
        ]
        ready_count = sum(
            check.get("status") == "PASS" for check in required_checks
        )
        diagnostic_columns = st.columns(3)
        diagnostic_columns[0].metric(
            "서비스 상태", health.get("status", "unknown")
        )
        diagnostic_columns[1].metric(
            "필수 점검",
            f"{ready_count}/{len(required_checks)} PASS",
        )
        diagnostic_columns[2].metric(
            "민감정보 노출", "0 · allowlist"
        )
        st.dataframe(
            pd.DataFrame(health.get("checks", [])),
            width="stretch",
            hide_index=True,
        )
        st.caption(
            "감사 API는 명시적 allowlist만 반환합니다. 시스템 프롬프트, "
            "Authorization header, API key, DB password는 저장하거나 표시하지 않습니다."
        )
    api.close()


if __name__ == "__main__":
    from frontend.legacy_page_redirect import redirect_legacy_page

    redirect_legacy_page("audit_logs")
