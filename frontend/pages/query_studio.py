"""Natural-language query and inline evidence workspace."""

from __future__ import annotations

from hashlib import sha256
from typing import Any

import pandas as pd
import streamlit as st

from backend.app.projects import ProjectRegistry
from frontend.app_services import ServiceBundle
from frontend.design_system import Action, Role, can_perform
from frontend.presentation import evidence_to_dot, flatten_rows_for_table, rows_to_csv
from frontend.query_workspace import (
    example_questions,
    query_context_versions,
    query_placeholder,
    query_status_presentation,
    statement_history,
)
from frontend.runtime import PROJECT_ROOT
from frontend.session_state import sync_active_conversation
from frontend.common_ui import failure_response

def render_response_summary(response: dict[str, Any]) -> None:
    status = response.get("status", "failed")
    presentation = query_status_presentation(status)
    st.markdown(
        f'<span class="p3-status">{presentation["label"]}</span>',
        unsafe_allow_html=True,
    )
    if status == "success":
        st.markdown(response["answer"])
        if response.get("caveat"):
            st.caption(f"주의 · {response['caveat']}")
    elif status == "empty":
        st.info(response["answer"], icon="ℹ️")
    elif status == "blocked":
        st.warning(response["answer"], icon="🛡️")
    elif status == "needs_clarification":
        st.info(response["answer"], icon="❓")
    elif status == "unsupported":
        st.info(response["answer"], icon="🔁")
    else:
        st.error(response["answer"], icon="⚠️")

    validation = response.get("validation", {})
    st.caption(
        f"결과 {response.get('row_count', 0)}행 · "
        f"검증 {validation.get('attempts', 0)}회 · "
        f"{validation.get('elapsed_ms', 0)}ms · "
        f"{response.get('provider', 'unknown')}"
    )
    st.caption(presentation["description"])
    if response.get("fallback_reason"):
        st.warning(
            "실시간 모델 장애를 감지해 검증된 Gold 쿼리로 전환했습니다.",
            icon="🛟",
        )

def render_inline_evidence(
    response: dict[str, Any],
    key_prefix: str,
    *,
    expanded: bool,
) -> None:
    with st.expander(
        "처리 근거 전체 보기 · 결과 / Cypher / 관계 경로 / 검증",
        expanded=expanded and response.get("status") == "success",
    ):
        result_tab, cypher_tab, graph_tab, validation_tab = st.tabs(
            ("조회 결과", "생성 Cypher", "관계 경로", "검증 이력")
        )
        with result_tab:
            rows = response.get("rows", [])
            if rows:
                st.dataframe(
                    pd.DataFrame(flatten_rows_for_table(rows)),
                    width="stretch",
                    hide_index=True,
                )
                st.download_button(
                    "결과 CSV",
                    data=rows_to_csv(rows),
                    file_name="p3_inline_result.csv",
                    mime="text/csv",
                    key=f"{key_prefix}-download",
                )
            else:
                st.info(
                    "실행 결과가 없거나 정책상 쿼리를 실행하지 않았습니다."
                )
        with cypher_tab:
            statements = statement_history(response)
            if statements:
                kind_copy = {
                    "generated": "초기 생성",
                    "corrected": "자기수정",
                    "final": "최종 실행",
                }
                for index, item in enumerate(statements):
                    label = kind_copy.get(item.get("kind"), item.get("kind"))
                    with st.container(border=True):
                        st.caption(
                            f"{label} · 시도 {item.get('attempt', index + 1)}"
                        )
                        st.code(
                            item.get("statement", ""),
                            language="cypher",
                            line_numbers=True,
                        )
            else:
                st.info("실행된 Cypher가 없습니다.")

        with graph_tab:
            evidence = response.get("evidence", {})
            if evidence.get("nodes"):
                st.graphviz_chart(
                    evidence_to_dot(evidence, rankdir="LR"),
                    width="stretch",
                )
                st.caption(
                    f"근거 노드 {evidence.get('node_count', 0)}개 · "
                    f"관계 {evidence.get('relationship_count', 0)}개"
                )
            else:
                st.info(
                    "집계 질의, 빈 결과 또는 실행 전 차단 상태이므로 "
                    "관계 경로를 임의 생성하지 않습니다."
                )

        with validation_tab:
            validation = response.get("validation", {})
            trace = validation.get("trace", [])
            if trace:
                st.dataframe(
                    pd.DataFrame(flatten_rows_for_table(trace)),
                    width="stretch",
                    hide_index=True,
                )
            errors = validation.get("errors", [])
            if errors:
                st.error("\n".join(str(error) for error in errors))
            elif trace:
                st.success(
                    "쓰기 차단·의미 검사·EXPLAIN 검증을 통과했습니다."
                )
            else:
                st.caption("모델 실행 전에 질문 guard에서 종료됐습니다.")

def render_expert_review(
    response: dict[str, Any],
    services: ServiceBundle,
    key_prefix: str,
) -> None:
    feedback_service = getattr(services, "feedback", None)
    if feedback_service is None or response.get("status") == "failed":
        return
    fingerprint = sha256(
        (
            f"{response.get('question', '')}\n"
            f"{response.get('cypher', '')}"
        ).encode("utf-8")
    ).hexdigest()
    existing = st.session_state["expert_reviews"].get(fingerprint)
    active_role = Role(
        st.session_state.get("active_role", Role.VIEWER.value)
    )
    if not can_perform(active_role, Action.REVIEW_RESULT):
        return
    with st.expander(
        "도메인 전문가 검증 · 전문가 전용",
        expanded=False,
    ):
        st.caption(
            "판정은 원래 답변을 덮어쓰지 않고 append-only "
            "감사기록으로 남습니다."
        )
        if existing:
            decision_labels = {
                "verified": "검증 완료",
                "needs_followup": "추가 확인 필요",
                "disputed": "이견 있음",
            }
            st.success(
                f"{decision_labels.get(existing['decision'], existing['decision'])} "
                f"· 검토자 {existing['reviewer']} · "
                f"기록 ID {existing['review_id'][:8]}"
            )
            return
        st.session_state.setdefault(f"{key_prefix}-reviewer", "domain-expert")
        st.session_state.setdefault(f"{key_prefix}-decision", "verified")
        st.session_state.setdefault(f"{key_prefix}-note", "")
        with st.form(f"{key_prefix}-expert-review"):
            reviewer_column, decision_column = st.columns([1, 2])
            with reviewer_column:
                reviewer = st.text_input(
                    "검토자 표시",
                    max_chars=120,
                    key=f"{key_prefix}-reviewer",
                )
            with decision_column:
                decision = st.radio(
                    "판정",
                    options=("verified", "needs_followup", "disputed"),
                    format_func=lambda value: {
                        "verified": "검증 완료",
                        "needs_followup": "추가 확인 필요",
                        "disputed": "이견 있음",
                    }[value],
                    horizontal=True,
                    key=f"{key_prefix}-decision",
                )
            note = st.text_area(
                "판정 근거 또는 추가 확인 사항",
                max_chars=2000,
                placeholder="예: MES 원장과 결과 건수 대조 완료",
                key=f"{key_prefix}-note",
            )
            submitted = st.form_submit_button(
                "전문가 판정 기록",
                type="primary",
                key=f"{key_prefix}-submit-review",
            )
        if submitted:
            try:
                record = feedback_service.record_review(
                    question=response.get("question", ""),
                    cypher=response.get("cypher", ""),
                    query_status=response.get("status", "unknown"),
                    provider=response.get("provider", "unknown"),
                    row_count=int(response.get("row_count", 0)),
                    decision=decision,
                    reviewer=reviewer,
                    note=note,
                )
                st.session_state["expert_reviews"][fingerprint] = record
                st.rerun()
            except Exception as error:
                st.error(f"전문가 검증 기록에 실패했습니다: {error}")

def render_chat_history(services: ServiceBundle) -> str | None:
    messages = st.session_state["messages"]
    rerun_question = None
    for index, message in enumerate(messages):
        with st.chat_message(message["role"]):
            if message["role"] == "user":
                st.markdown(message["content"])
            else:
                render_response_summary(message["content"])
                render_inline_evidence(
                    message["content"],
                    key_prefix=f"chat-{index}",
                    expanded=index == len(messages) - 1,
                )
                render_expert_review(
                    message["content"],
                    services,
                    key_prefix=f"chat-{index}",
                )
                active_role = Role(
                    st.session_state.get("active_role", Role.VIEWER.value)
                )
                if st.button(
                    "이 질문 다시 실행",
                    key=f"rerun-question-{index}",
                    disabled=not can_perform(
                        active_role, Action.RERUN_QUERY
                    ),
                ):
                    rerun_question = str(
                        message["content"].get("question", "")
                    )
    return rerun_question

def submit_question(question: str, services: ServiceBundle) -> None:
    st.session_state["messages"].append(
        {"role": "user", "content": question}
    )
    try:
        with st.status(
            "질의 파이프라인 실행 중",
            expanded=True,
        ) as status:
            st.write("1 · 프로젝트·schema version 고정")
            st.write("2 · 자연어 질문에서 READ-only Cypher 생성")
            st.write("3 · 쓰기 차단·의미 검사·EXPLAIN 검증")
            response = services.query_with_fallback(question)
            st.write("4 · 실행 결과·관계 근거 구성")
            status.update(
                label="질의 파이프라인 완료",
                state="complete",
                expanded=False,
            )
    except Exception as error:
        response = failure_response(question, error)
    st.session_state["messages"].append(
        {"role": "assistant", "content": response}
    )
    st.session_state["last_result"] = response
    sync_active_conversation()

def render_chat_tab(services: ServiceBundle) -> None:
    project_id = st.session_state.get("active_project_id", "cip-dmd")
    project = ProjectRegistry(
        PROJECT_ROOT / "data" / "processed" / "projects.sqlite3"
    ).require(project_id)
    st.subheader("제조 관계를 자연어로 조회")
    st.caption(
        "답변과 함께 생성된 Cypher, 결과표, 근거 경로를 확인할 수 있습니다."
    )
    versions = query_context_versions(
        project, st.session_state.get("last_result")
    )
    version_columns = st.columns(len(versions))
    for column, version in zip(version_columns, versions):
        column.metric(version["label"], version["value"])
    if project["status"] != "ready":
        st.warning(
            f"현재 프로젝트 상태는 `{project['status']}`입니다. "
            "Readiness gate가 끝나기 전에는 자유 질의가 차단될 수 있습니다."
        )
    st.markdown(
        """
        <div class="p3-trust-strip">
          <span>읽기 전용 Neo4j</span>
          <span>쓰기 의도 사전 차단</span>
          <span>EXPLAIN 검증</span>
          <span>근거 없는 경로 생성 금지</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    project_examples = example_questions(project_id)
    columns = st.columns(len(project_examples))
    selected_question = None
    for column, (label, question) in zip(columns, project_examples):
        if column.button(
            label,
            key=f"example-{project_id}-{label}",
            help=question,
            width="stretch",
        ):
            selected_question = question

    st.divider()
    rerun_question = render_chat_history(services)
    last_result = st.session_state.get("last_result")
    if last_result and last_result.get("status") == "failed":
        if st.button(
            "마지막 질문 다시 시도",
            key="retry-last-question",
            type="primary",
        ):
            submit_question(last_result["question"], services)
            st.rerun()
    typed_question = st.chat_input(query_placeholder(project_id))
    pending_question = st.session_state.pop("pending_audit_question", None)
    question = (
        typed_question
        or selected_question
        or rerun_question
        or pending_question
    )
    if question:
        submit_question(question, services)
        st.rerun()


if __name__ == "__main__":
    from frontend.legacy_page_redirect import redirect_legacy_page

    redirect_legacy_page("query_studio")
