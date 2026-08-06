"""P3 manufacturing knowledge-graph RCA Streamlit application."""

from __future__ import annotations

import os
import json
import base64
from pathlib import Path
import sys
from typing import Any
from copy import deepcopy
from hashlib import sha256
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import streamlit as st

from backend.app.services.diagnostics import collect_demo_diagnostics
from backend.app.services.data_intake_service import DataIntakeService
from backend.app.conversations import ConversationStore
from backend.app.jobs import PipelineJobStore
from backend.app.ingestion import DatasetWorkspace
from backend.app.mapping import MappingWorkspace
from backend.app.projects import ProjectRegistry
from backend.app.schema_registry import SchemaRegistry
from frontend.app_services import (
    ServiceBundle,
    build_streamlit_service_bundle,
)
from frontend.api_client import FactoryGraphApiClient
from frontend.conversation_history import upsert_conversation
from frontend.data_preflight import inspect_uploaded_source
from frontend.design_system import (
    NAVIGATION_ITEMS,
    PAGE_BY_LABEL,
    Role,
    ViewState,
    build_global_css,
    navigation_for_role,
    state_copy,
)
from frontend.graph_explorer import (
    bound_evidence,
    build_visual_spec,
    graph_performance_policy,
    merge_catalog_payload,
    node_caption,
    selected_entity_details,
    shortest_path_ids,
    validate_project_scope,
)
from frontend.presentation import (
    evidence_to_dot,
    filter_evidence,
    flatten_rows_for_table,
    normalize_catalog_evidence,
    rows_to_csv,
)
from frontend.project_context import (
    restore_project_context,
    snapshot_project_context,
)
from frontend.project_workspace import (
    filter_projects,
    next_action_presentation,
    relative_updated_at,
    status_presentation,
)
from frontend.query_workspace import (
    query_context_versions,
    query_status_presentation,
    statement_history,
)
from frontend.onboarding import (
    format_elapsed,
    job_elapsed_seconds,
    job_status_presentation,
    onboarding_progress,
    profile_quality_warnings,
)


APP_TITLE = "Factory Graph RCA"
SERVICE_BUNDLE_VERSION = "2026-07-28-shared-api-v2"
NAVIGATION_PAGES = tuple(item.label for item in NAVIGATION_ITEMS)
EXAMPLE_QUESTIONS = [
    (
        "제품 Genealogy",
        "완제품 300002의 구성품, 각 구성품의 공정과 품질검사 결과를 보여줘.",
    ),
    (
        "품질 실패 × 이상",
        "표면거칠기 검사에 실패한 cylinder bottom들의 밀링 anomaly 분포를 보여줘.",
    ),
    (
        "역방향 영향분석",
        "밀링 anomaly class 2가 발생한 cylinder bottom과 조립된 완제품의 최종 QC 결과를 보여줘.",
    ),
    (
        "없는 엔티티 검증",
        "완제품 399999의 구성품과 품질검사 결과를 보여줘.",
    ),
]


st.set_page_config(
    page_title=APP_TITLE,
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1500px;}
    .p3-hero {
      padding: 1.4rem 1.6rem;
      border-radius: 18px;
      background: linear-gradient(120deg, #0B3B3A 0%, #0F766E 55%, #164E63 100%);
      color: white;
      box-shadow: 0 12px 30px rgba(15, 118, 110, 0.18);
      margin-bottom: 1rem;
    }
    .p3-hero h1 {font-size: 2rem; margin: 0 0 .35rem 0; color: white;}
    .p3-hero p {margin: 0; color: #D9F5F1; font-size: .98rem;}
    .p3-kicker {
      text-transform: uppercase;
      letter-spacing: .12em;
      font-size: .72rem;
      color: #99F6E4;
      margin-bottom: .45rem;
    }
    div[data-testid="stMetric"] {
      background: white;
      border: 1px solid #DDE6E8;
      padding: .8rem 1rem;
      border-radius: 14px;
    }
    div[data-testid="stChatMessage"] {
      border: 1px solid #E2E8F0;
      border-radius: 14px;
      padding: .3rem .45rem;
    }
    .p3-status {
      display: inline-block;
      border-radius: 999px;
      padding: .18rem .55rem;
      font-size: .76rem;
      font-weight: 700;
      background: #CCFBF1;
      color: #115E59;
      margin-bottom: .45rem;
    }
    .p3-feature-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: .7rem;
      margin: .4rem 0 1rem 0;
    }
    .p3-feature {
      background: #F8FAFC;
      border: 1px solid #DDE6E8;
      border-radius: 14px;
      padding: .85rem 1rem;
    }
    .p3-feature b {color: #0F5E58; font-size: .88rem;}
    .p3-feature p {margin: .3rem 0 0 0; color: #475569; font-size: .78rem;}
    .p3-trust-strip {
      display: flex;
      flex-wrap: wrap;
      gap: .45rem;
      margin: .25rem 0 1rem 0;
    }
    .p3-trust-strip span {
      border: 1px solid #CDE5DF;
      background: #F0FDFA;
      color: #115E59;
      border-radius: 999px;
      padding: .28rem .65rem;
      font-size: .76rem;
      font-weight: 650;
    }
    .p3-section-note {
      border-left: 3px solid #14B8A6;
      background: #F8FAFC;
      padding: .65rem .8rem;
      color: #475569;
      font-size: .82rem;
      margin: .35rem 0 .9rem 0;
    }
    .p3-landing-hero {
      display: grid;
      grid-template-columns: 1.1fr .9fr;
      gap: 1rem;
      align-items: stretch;
      padding: 2.6rem;
      border-radius: 24px;
      color: white;
      background:
        radial-gradient(circle at 86% 16%, rgba(45, 212, 191, .28), transparent 34%),
        linear-gradient(135deg, #082F2C 0%, #0B4F4A 56%, #123C55 100%);
      box-shadow: 0 24px 60px rgba(8, 47, 44, .2);
      margin-bottom: 1.2rem;
    }
    .p3-landing-copy h1 {
      max-width: 720px;
      margin: .45rem 0 .9rem;
      color: white;
      font-size: clamp(2.3rem, 5vw, 4.6rem);
      line-height: .98;
      letter-spacing: -.055em;
    }
    .p3-landing-copy h1 span {display:block; color:#5EEAD4;}
    .p3-landing-copy p {
      max-width: 650px;
      margin: 0;
      color: #D6F4F0;
      font-size: 1rem;
      line-height: 1.75;
    }
    .p3-landing-proof {
      display:flex;
      flex-wrap:wrap;
      gap:.45rem;
      margin-top:1.2rem;
    }
    .p3-landing-proof span {
      border:1px solid rgba(153,246,228,.34);
      border-radius:999px;
      padding:.34rem .68rem;
      color:#CCFBF1;
      background:rgba(15,118,110,.24);
      font-size:.76rem;
      font-weight:700;
    }
    .p3-investigation {
      align-self: stretch;
      border: 1px solid rgba(255,255,255,.2);
      border-radius: 18px;
      padding: 1.1rem;
      background: rgba(3, 18, 24, .48);
      backdrop-filter: blur(14px);
    }
    .p3-investigation-head {
      display:flex;
      justify-content:space-between;
      color:#99F6E4;
      font-size:.72rem;
      letter-spacing:.06em;
      text-transform:uppercase;
    }
    .p3-investigation-question {
      margin:.9rem 0;
      border-radius:12px;
      padding:.8rem;
      color:#E6FFFB;
      background:rgba(255,255,255,.08);
      font-size:.82rem;
      line-height:1.55;
    }
    .p3-investigation-path {
      display:grid;
      grid-template-columns:1fr auto 1fr auto 1fr;
      align-items:center;
      gap:.35rem;
      color:#5EEAD4;
      font-size:.64rem;
    }
    .p3-investigation-path b {
      border:1px solid rgba(94,234,212,.3);
      border-radius:10px;
      padding:.6rem .45rem;
      color:white;
      text-align:center;
      background:rgba(15,118,110,.24);
    }
    .p3-cypher-preview {
      margin-top:.8rem;
      border-radius:10px;
      padding:.7rem;
      color:#A7F3D0;
      background:#061B20;
      font-family:ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size:.65rem;
      line-height:1.55;
    }
    .p3-landing-section {
      padding:1.5rem 0 .5rem;
    }
    .p3-landing-section h2 {
      margin:.25rem 0 1rem;
      font-size:1.8rem;
      letter-spacing:-.035em;
    }
    .p3-workflow {
      display:grid;
      grid-template-columns:repeat(4,minmax(0,1fr));
      gap:.7rem;
      margin:1rem 0;
    }
    .p3-workflow div {
      border-top:2px solid #14B8A6;
      padding:.8rem .2rem;
    }
    .p3-workflow b {display:block;color:#0F5E58;}
    .p3-workflow span {color:#64748B;font-size:.76rem;}
    @media (max-width: 900px) {
      .p3-feature-grid {grid-template-columns: repeat(2, minmax(0, 1fr));}
      .p3-landing-hero {grid-template-columns:1fr;padding:1.5rem;}
      .p3-workflow {grid-template-columns:repeat(2,minmax(0,1fr));}
    }
    </style>
    """,
    unsafe_allow_html=True,
)
st.markdown(build_global_css(), unsafe_allow_html=True)


@st.cache_resource(show_spinner=False)
def get_services(
    provider: str,
    model_name: str,
    bundle_version: str,
    project_id: str,
) -> Any:
    del bundle_version
    schemas = SchemaRegistry(PROJECT_ROOT / "schemas")
    return build_streamlit_service_bundle(
        project_root=PROJECT_ROOT,
        provider=provider,
        model_name=model_name,
        project_id=project_id,
        schema_context=schemas.context(project_id),
    )


@st.cache_resource(show_spinner=False)
def get_data_intake_service() -> DataIntakeService:
    return DataIntakeService(PROJECT_ROOT)


@st.cache_data(show_spinner=False)
def get_reference_intake_archive() -> bytes:
    return DataIntakeService(PROJECT_ROOT).build_reference_archive()


def get_conversation_store() -> ConversationStore:
    return ConversationStore(
        PROJECT_ROOT / "data" / "processed" / "conversations.sqlite3"
    )


def initialize_session() -> None:
    st.session_state.setdefault("active_page", "Home")
    st.session_state.setdefault("preview_role", Role.ADMIN.value)
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("last_result", None)
    st.session_state.setdefault("conversations", [])
    st.session_state.setdefault(
        "active_conversation_id", str(uuid4())
    )
    st.session_state.setdefault("explorer_result", None)
    st.session_state.setdefault("explorer_search_result", None)
    st.session_state.setdefault("explorer_selected_node_ids", [])
    st.session_state.setdefault(
        "explorer_selected_relationship_ids", []
    )
    st.session_state.setdefault("explorer_expansion_history", [])
    st.session_state.setdefault("explorer_filters", {})
    st.session_state.setdefault("explorer_widget_revision", 0)
    st.session_state.setdefault("expert_reviews", {})
    st.session_state.setdefault("intake_record", None)
    st.session_state.setdefault("intake_approval_token", None)
    st.session_state.setdefault("active_project_id", "cip-dmd")
    st.session_state.setdefault("project_conversations", {})
    st.session_state.setdefault("conversation_loaded_projects", set())
    st.session_state.setdefault("query_filters", {})
    st.session_state.setdefault("evaluation_filters", {})
    active_project_id = st.session_state["active_project_id"]
    if active_project_id not in st.session_state["conversation_loaded_projects"]:
        conversations = get_conversation_store().list(
            active_project_id, limit=12
        )
        st.session_state["conversations"] = conversations
        if conversations and not st.session_state["messages"]:
            current = conversations[0]
            st.session_state["active_conversation_id"] = current["id"]
            st.session_state["messages"] = deepcopy(current["messages"])
            st.session_state["last_result"] = deepcopy(
                current.get("last_result")
            )
        st.session_state["conversation_loaded_projects"].add(
            active_project_id
        )


def navigate_to_page(page: str) -> None:
    if page not in NAVIGATION_PAGES:
        return
    st.session_state["active_page"] = page


def render_page_header(page: str) -> None:
    item = PAGE_BY_LABEL[page]
    badge = (
        "운영 화면"
        if item.delivery == "available"
        else f"Stage {item.implementation_stage} 준비"
    )
    st.markdown(
        f"""
        <section class="p3-page-head">
          <div>
            <h1>{item.icon} {item.label}</h1>
            <p>{item.description}</p>
          </div>
          <span class="p3-stage-badge">{badge}</span>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_view_state(
    state: ViewState,
    *,
    page: str,
    detail: str | None = None,
) -> None:
    copy = state_copy(state, page_label=page)
    message = detail or copy.message
    st.markdown(
        f"""
        <div class="p3-state-card" data-view-state="{state.value}">
          <h3>{copy.title}</h3>
          <p>{message}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_foundation_workspace(page: str) -> None:
    item = PAGE_BY_LABEL[page]
    render_page_header(page)
    render_view_state(
        ViewState.READY,
        page=page,
        detail=(
            f"정보구조와 접근 권한은 2-1에서 확정했습니다. 세부 업무 "
            f"기능은 구현계획 {item.implementation_stage}에서 연결됩니다."
        ),
    )
    st.markdown(
        """
        <div class="p3-foundation-grid">
          <div class="p3-foundation-card">
            <b>상태 계약</b>
            <span>정상·로딩·빈 상태·오류를 같은 언어와 구조로 표시합니다.</span>
          </div>
          <div class="p3-foundation-card">
            <b>API 경계</b>
            <span>업무 상태는 FastAPI가 소유하며 UI가 파일·DB를 우회하지 않습니다.</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def sync_active_conversation() -> None:
    messages = st.session_state["messages"]
    if not messages:
        return
    st.session_state["conversations"] = upsert_conversation(
        st.session_state["conversations"],
        conversation_id=st.session_state["active_conversation_id"],
        messages=messages,
        last_result=st.session_state.get("last_result"),
    )
    active = next(
        conversation
        for conversation in st.session_state["conversations"]
        if conversation["id"]
        == st.session_state["active_conversation_id"]
    )
    get_conversation_store().save(
        st.session_state.get("active_project_id", "cip-dmd"),
        active,
    )


def start_new_conversation() -> None:
    sync_active_conversation()
    st.session_state["active_conversation_id"] = str(uuid4())
    st.session_state["messages"] = []
    st.session_state["last_result"] = None


def open_conversation(conversation_id: str) -> None:
    conversation = next(
        (
            item
            for item in st.session_state["conversations"]
            if item["id"] == conversation_id
        ),
        None,
    )
    if conversation is None:
        return
    st.session_state["active_conversation_id"] = conversation_id
    st.session_state["messages"] = deepcopy(conversation["messages"])
    st.session_state["last_result"] = deepcopy(
        conversation.get("last_result")
    )


def failure_response(question: str, error: Exception) -> dict[str, Any]:
    return {
        "question": question,
        "answer": "서비스 연결 또는 질의 처리 중 오류가 발생했습니다.",
        "status": "failed",
        "cypher": "",
        "rows": [],
        "row_count": 0,
        "evidence": {
            "nodes": [],
            "relationships": [],
            "node_count": 0,
            "relationship_count": 0,
            "source_row_count": 0,
            "visualized_row_count": 0,
            "truncated": {
                "nodes": False,
                "relationships": False,
                "rows": False,
            },
        },
        "validation": {
            "attempts": 0,
            "errors": [str(error)],
            "trace": [],
            "elapsed_ms": 0,
        },
        "caveat": None,
    }


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
        result_column, cypher_column = st.columns([1.15, 1])
        with result_column:
            st.markdown("##### 조회 결과")
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
        with cypher_column:
            st.markdown("##### 생성·수정 Cypher")
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

        evidence = response.get("evidence", {})
        st.markdown("##### 실제 조회 관계")
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

        st.markdown("##### Validation·Self-correction trace")
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
            st.success("쓰기 차단·의미 검사·EXPLAIN 검증을 통과했습니다.")
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
    st.markdown("##### 도메인 전문가 검증")
    st.caption(
        "판정은 원래 답변을 덮어쓰지 않고 append-only 감사기록으로 남습니다."
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
                if st.button(
                    "이 질문 다시 실행",
                    key=f"rerun-question-{index}",
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
    columns = st.columns(len(EXAMPLE_QUESTIONS))
    selected_question = None
    for column, (label, question) in zip(columns, EXAMPLE_QUESTIONS):
        if column.button(
            label,
            key=f"example-{label}",
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
    typed_question = st.chat_input(
        "예: 완제품 300002의 구성품과 공정 이력을 보여줘."
    )
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


def render_landing_overview() -> None:
    st.markdown(
        """
        <div class="p3-feature-grid">
          <div class="p3-feature">
            <b>01 · Ask</b>
            <p>제조 관계를 자연어로 질문합니다.</p>
          </div>
          <div class="p3-feature">
            <b>02 · Generate</b>
            <p>LLM이 읽기 전용 Cypher를 생성합니다.</p>
          </div>
          <div class="p3-feature">
            <b>03 · Verify</b>
            <p>의미·문법·쓰기 위험을 실행 전에 검사합니다.</p>
          </div>
          <div class="p3-feature">
            <b>04 · Trace</b>
            <p>조회 결과와 실제 관계 경로를 함께 확인합니다.</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_streamlit_landing() -> None:
    st.markdown(
        """
        <section class="p3-landing-hero">
          <div class="p3-landing-copy">
            <div class="p3-kicker">Manufacturing Knowledge Graph</div>
            <h1>Find the path.<span>Keep the proof.</span></h1>
            <p>
              제조 관계를 자연어로 묻고, 검증된 Cypher와 실제 그래프
              경로로 RCA 후보를 확인합니다. 추정한 답변이 아니라 조회한
              근거와 전문가 판정을 남깁니다.
            </p>
            <div class="p3-landing-proof">
              <span>Gold 15/15</span>
              <span>READ-only 100%</span>
              <span>Blind 26</span>
              <span>Expert HITL</span>
            </div>
          </div>
          <div class="p3-investigation">
            <div class="p3-investigation-head">
              <span>Live investigation</span><span>Verified</span>
            </div>
            <div class="p3-investigation-question">
              완제품 300002의 구성품과 각 공정·품질검사 결과를 보여줘.
            </div>
            <div class="p3-investigation-path">
              <b>Cylinder<br>300002</b><span>→</span>
              <b>Part<br>103504</b><span>→</span>
              <b>Process<br>CNC milling</b>
            </div>
            <div class="p3-cypher-preview">
              MATCH (c:Cylinder)-[:ASSEMBLED_FROM]-&gt;(p:Part)<br>
              OPTIONAL MATCH (p)-[:UNDERWENT]-&gt;(run:ProcessRun)<br>
              RETURN c, p, run
            </div>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    query_column, graph_column, spacer = st.columns([1, 1, 3])
    query_column.button(
        "RCA 질문 시작 →",
        type="primary",
        width="stretch",
        on_click=navigate_to_page,
        args=("Query Studio",),
    )
    graph_column.button(
        "그래프 탐색",
        width="stretch",
        on_click=navigate_to_page,
        args=("Graph Explorer",),
    )

    metric_columns = st.columns(4)
    metric_columns[0].metric("조립 완제품", "802")
    metric_columns[1].metric("Genealogy 완전성", "95.6%")
    metric_columns[2].metric("Blind 의미값 정확도", "61.5%")
    metric_columns[3].metric("관계 유형", "7")

    st.markdown(
        """
        <section class="p3-landing-section">
          <div class="p3-kicker" style="color:#0F766E">What the system proves</div>
          <h2>AI 답변보다 검증 경로를 설계합니다.</h2>
        </section>
        """,
        unsafe_allow_html=True,
    )
    render_landing_overview()
    st.markdown(
        """
        <section class="p3-landing-section">
          <div class="p3-kicker" style="color:#0F766E">Agent workflow</div>
          <h2>실행 전에 의심하고, 실행 후에 증명합니다.</h2>
          <div class="p3-workflow">
            <div><b>01 · Ask</b><span>현업 언어로 관계 질문</span></div>
            <div><b>02 · Generate</b><span>스키마 기반 Cypher 생성</span></div>
            <div><b>03 · Verify</b><span>READ-only·EXPLAIN·의미 검사</span></div>
            <div><b>04 · Trace</b><span>조회값·관계·전문가 판정</span></div>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    st.info(
        "사내 프로토타입에서는 질문, 실행 Cypher, 조회 결과, 관계 경로와 "
        "도메인 전문가 판정을 같은 앱에서 확인합니다.",
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
    for project in projects[:3]:
        presentation = status_presentation(project["status"])
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
                "열기",
                key=f"home-open-{project['project_id']}",
                disabled=bool(project.get("is_active")),
                width="stretch",
            ):
                _switch_project(project["project_id"])
                navigate_to_page("Projects")
                st.rerun()

    if st.button(
        "모든 프로젝트 보기 →",
        key="home-all-projects",
        on_click=navigate_to_page,
        args=("Projects",),
    ):
        st.rerun()


def render_projects_workspace() -> None:
    render_page_header("Projects")
    registry = ProjectRegistry(
        PROJECT_ROOT / "data" / "processed" / "projects.sqlite3"
    )
    registry.ensure_default()
    role = Role(st.session_state.get("preview_role", Role.ADMIN.value))

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


def render_graph_explorer(services: ServiceBundle) -> None:
    project_id = st.session_state.get("active_project_id", "cip-dmd")
    st.subheader("Interactive Graph Explorer")
    st.caption(
        "노드를 검색하고 선택해 최대 3-hop까지 확장합니다. 모든 조회는 "
        f"현재 프로젝트 `{project_id}` 범위와 읽기 전용 계약을 따릅니다."
    )
    if services.graph is None:
        st.error("그래프 탐색 서비스가 구성되지 않았습니다.")
        return

    try:
        contract = SchemaRegistry(PROJECT_ROOT / "schemas").contract(
            project_id
        )
    except (KeyError, ValueError) as error:
        st.error(f"프로젝트 그래프 스키마를 불러오지 못했습니다: {error}")
        return
    identity_by_label = {
        row["label"]: row["identity_property"]
        for row in contract["node_identities"]
    }
    labels = tuple(identity_by_label)
    if not labels:
        st.info("탐색 가능한 노드 라벨이 없습니다.")
        return

    label_names = {
        "Cylinder": "완제품 Cylinder",
        "CylinderBottom": "구성품 Cylinder Bottom",
        "PistonRod": "구성품 Piston Rod",
        "Part": "전체 Part",
        "Process": "공정",
        "ProcessRun": "공정 실행",
        "Equipment": "장비",
        "AnomalyClass": "이상 유형",
        "QualityMeasurement": "품질 측정",
        "QualityFailure": "품질 불합격",
    }
    start_column, depth_column, limit_column = st.columns([2, 1, 1])
    with start_column:
        label = st.selectbox(
            "시작 노드 유형",
            options=labels,
            index=(
                labels.index("Cylinder")
                if "Cylinder" in labels
                else 0
            ),
            format_func=lambda value: label_names.get(value, value),
            key=f"graph-explorer-label-{project_id}",
        )
    with depth_column:
        default_depth = st.select_slider(
            "N-hop",
            options=(1, 2, 3),
            value=2,
            key=f"graph-explorer-depth-{project_id}",
        )
    with limit_column:
        result_limit = st.selectbox(
            "경로 제한",
            options=(25, 50, 75, 100),
            index=2,
            key=f"graph-explorer-limit-{project_id}",
        )

    with st.form(f"graph-node-search-form-{project_id}"):
        search_column, button_column = st.columns([4, 1])
        with search_column:
            search_term = st.text_input(
                "노드 검색",
                placeholder="ID, 이름, 공정, 이상 유형 또는 측정 항목 검색",
                label_visibility="collapsed",
            )
        with button_column:
            search_submitted = st.form_submit_button(
                "검색",
                type="primary",
                width="stretch",
            )
    if search_submitted:
        if not search_term.strip():
            st.warning("검색어를 입력하세요.")
        else:
            try:
                with st.spinner("일치하는 그래프 노드를 찾고 있습니다."):
                    st.session_state["explorer_search_result"] = (
                        services.graph.search_nodes(
                            label=label,
                            query=search_term.strip(),
                            limit=20,
                        )
                    )
            except Exception as error:
                st.error(f"노드 검색에 실패했습니다: {error}")

    search_result = st.session_state.get("explorer_search_result")
    if search_result and search_result.get("label") == label:
        nodes = search_result.get("nodes", [])
        if nodes:
            identity_property = search_result["identity_property"]

            def search_option_label(index: int) -> str:
                node = nodes[index]
                properties = node.get("properties", {})
                identity_value = properties.get(identity_property, node["id"])
                secondary = (
                    properties.get("display_name")
                    or properties.get("name")
                    or properties.get("part_type")
                    or properties.get("feature")
                )
                return " · ".join(
                    value
                    for value in (str(identity_value), str(secondary or ""))
                    if value
                )

            selection_column, depth_column, action_column = st.columns(
                [2, 1, 1]
            )
            with selection_column:
                selected_index = st.selectbox(
                    f"검색 결과 {len(nodes)}개",
                    options=range(len(nodes)),
                    format_func=search_option_label,
                    key=f"graph-search-selection-{project_id}-{label}",
                )
            with depth_column:
                st.caption("검색 결과를 시작점으로 사용합니다.")
            with action_column:
                explore_selected = st.button(
                    "그래프 열기",
                    type="primary",
                    width="stretch",
                    key=f"graph-open-search-{project_id}",
                )
            if explore_selected:
                selected_node = nodes[selected_index]
                selected_identity = str(
                    selected_node.get("properties", {}).get(
                        identity_property, ""
                    )
                )
                try:
                    with st.spinner("선택한 노드의 관계를 조회하고 있습니다."):
                        payload = services.graph.subgraph(
                            label=label,
                            identity=selected_identity,
                            depth=default_depth,
                            limit=result_limit,
                        )
                    validate_project_scope(payload, project_id)
                    st.session_state["explorer_result"] = {
                        "label": label,
                        "identity": selected_identity,
                        "depth": default_depth,
                        "payload": payload,
                    }
                    st.session_state["explorer_selected_node_ids"] = [
                        str(selected_node["id"])
                    ]
                    st.session_state[
                        "explorer_selected_relationship_ids"
                    ] = []
                    st.session_state["explorer_expansion_history"] = [
                        {
                            "label": label,
                            "identity": selected_identity,
                            "depth": default_depth,
                        }
                    ]
                    st.session_state["explorer_widget_revision"] += 1
                    st.rerun()
                except Exception as error:
                    st.error(f"관계 탐색에 실패했습니다: {error}")
        else:
            st.info("일치하는 노드가 없습니다. 다른 검색어를 입력해보세요.")

    with st.expander("정확한 ID로 바로 탐색"):
        with st.form(f"graph-explorer-form-{project_id}"):
            identity_column, depth_column = st.columns([1.5, 1])
            with identity_column:
                identity = st.text_input(
                    f"식별값 · {identity_by_label[label]}",
                    value="300002" if label == "Cylinder" else "",
                    placeholder="예: 300002",
                )
            with depth_column:
                st.caption(
                    f"{default_depth}-hop · 최대 {result_limit}개 경로"
                )
            submitted = st.form_submit_button(
                "관계 탐색",
                type="primary",
                width="stretch",
            )

    if submitted:
        if not identity.strip():
            st.warning("탐색할 식별값을 입력하세요.")
        else:
            try:
                with st.spinner("Neo4j에서 연결 관계를 조회하고 있습니다."):
                    payload = services.graph.subgraph(
                        label=label,
                        identity=identity.strip(),
                        depth=default_depth,
                        limit=result_limit,
                    )
                validate_project_scope(payload, project_id)
                st.session_state["explorer_result"] = {
                    "label": label,
                    "identity": identity.strip(),
                    "depth": default_depth,
                    "payload": payload,
                }
                root = payload.get("root")
                st.session_state["explorer_selected_node_ids"] = (
                    [str(root["id"])] if isinstance(root, dict) else []
                )
                st.session_state[
                    "explorer_selected_relationship_ids"
                ] = []
                st.session_state["explorer_expansion_history"] = [
                    {
                        "label": label,
                        "identity": identity.strip(),
                        "depth": default_depth,
                    }
                ]
                st.session_state["explorer_widget_revision"] += 1
                st.rerun()
            except Exception as error:
                st.error(f"관계 탐색에 실패했습니다: {error}")

    explorer_result = st.session_state.get("explorer_result")
    if not explorer_result:
        st.markdown(
            """
            <div class="p3-section-note">
              시작 예시: 노드 유형을 <b>Cylinder</b>로 선택하고
              <b>300002</b>를 입력하면 구성품·공정·장비·품질 관계를
              실제 그래프에서 확인할 수 있습니다.
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    payload = explorer_result["payload"]
    try:
        validate_project_scope(payload, project_id)
    except ValueError as error:
        st.error(str(error), icon="🔒")
        return
    if payload.get("root") is None:
        st.info(
            f"{explorer_result['label']} "
            f"'{explorer_result['identity']}'에 해당하는 노드가 없습니다."
        )
        return

    evidence = normalize_catalog_evidence(payload)
    available_labels = sorted(
        {str(node["label"]) for node in evidence["nodes"]}
    )
    available_relationships = sorted(
        {
            str(relationship["type"])
            for relationship in evidence["relationships"]
        }
    )
    filters = st.session_state.get("explorer_filters", {})
    with st.expander("표시 필터와 레이아웃", expanded=False):
        filter_column, relation_column, layout_column = st.columns(3)
        with filter_column:
            selected_labels = st.multiselect(
                "노드 유형",
                options=available_labels,
                default=[
                    value
                    for value in filters.get(
                        "labels", available_labels
                    )
                    if value in available_labels
                ],
                key=f"graph-label-filter-{project_id}",
            )
        with relation_column:
            selected_relationship_types = st.multiselect(
                "관계 유형",
                options=available_relationships,
                default=[
                    value
                    for value in filters.get(
                        "relationship_types",
                        available_relationships,
                    )
                    if value in available_relationships
                ],
                key=f"graph-relation-filter-{project_id}",
            )
        with layout_column:
            layout = st.selectbox(
                "레이아웃",
                options=(
                    "forcedirected",
                    "hierarchical",
                    "circular",
                    "grid",
                ),
                format_func=lambda value: {
                    "forcedirected": "Force directed",
                    "hierarchical": "Hierarchical",
                    "circular": "Circular",
                    "grid": "Grid",
                }[value],
                key=f"graph-layout-{project_id}",
            )
            include_isolated = st.toggle(
                "고립 노드 표시",
                value=bool(filters.get("include_isolated", True)),
                key=f"graph-isolated-{project_id}",
            )
    st.session_state["explorer_filters"] = {
        "labels": selected_labels,
        "relationship_types": selected_relationship_types,
        "include_isolated": include_isolated,
    }
    filtered = filter_evidence(
        evidence,
        labels=set(selected_labels),
        relationship_types=set(selected_relationship_types),
        include_isolated=include_isolated,
    )
    if not filtered["nodes"]:
        st.info(
            "현재 필터에 표시할 노드가 없습니다. 노드 유형 필터를 "
            "하나 이상 선택하세요."
        )
        return
    performance = graph_performance_policy(filtered["node_count"])
    filtered = bound_evidence(
        filtered,
        performance.recommended_limit,
        priority_node_ids=st.session_state.get(
            "explorer_selected_node_ids", []
        ),
    )
    visible_node_ids = {
        str(node["id"]) for node in filtered["nodes"]
    }
    visible_relationship_ids = {
        str(relationship.get("id", ""))
        for relationship in filtered["relationships"]
    }
    selected_node_ids = [
        node_id
        for node_id in st.session_state.get(
            "explorer_selected_node_ids", []
        )
        if node_id in visible_node_ids
    ]
    selected_relationship_ids = [
        relationship_id
        for relationship_id in st.session_state.get(
            "explorer_selected_relationship_ids", []
        )
        if relationship_id in visible_relationship_ids
    ]

    node_lookup = {
        str(node["id"]): node for node in filtered["nodes"]
    }
    focus_column, focus_action_column, path_column = st.columns(
        [3, 1, 1]
    )
    with focus_column:
        focus_node_id = st.selectbox(
            "화면에서 선택할 노드",
            options=tuple(node_lookup),
            index=(
                tuple(node_lookup).index(selected_node_ids[0])
                if selected_node_ids
                and selected_node_ids[0] in node_lookup
                else 0
            ),
            format_func=lambda node_id: node_caption(
                node_lookup[node_id], identity_by_label
            ).replace("\n", " · "),
            key=f"graph-focus-node-{project_id}",
        )
    with focus_action_column:
        st.write("")
        if st.button(
            "선택 동기화",
            width="stretch",
            key=f"graph-focus-action-{project_id}",
        ):
            st.session_state["explorer_selected_node_ids"] = [
                focus_node_id
            ]
            st.session_state[
                "explorer_selected_relationship_ids"
            ] = []
            st.session_state["explorer_widget_revision"] += 1
            st.rerun()
    with path_column:
        highlight_path = st.toggle(
            "루트 경로 강조",
            value=True,
            key=f"graph-path-highlight-{project_id}",
        )

    path_node_ids: set[str] = set()
    path_relationship_ids: set[str] = set()
    if highlight_path and selected_node_ids:
        path_node_ids, path_relationship_ids = shortest_path_ids(
            filtered,
            filtered.get("root_id"),
            selected_node_ids[0],
        )
    visual_spec = build_visual_spec(
        filtered,
        identity_by_label=identity_by_label,
        root_id=filtered.get("root_id"),
        selected_node_ids=selected_node_ids,
        selected_relationship_ids=selected_relationship_ids,
        highlighted_node_ids=path_node_ids,
        highlighted_relationship_ids=path_relationship_ids,
        label_mode=performance.label_mode,
    )

    node_metric, relation_metric, depth_metric, renderer_metric = st.columns(
        4
    )
    node_metric.metric("표시 노드", filtered["node_count"])
    relation_metric.metric("표시 관계", filtered["relationship_count"])
    depth_metric.metric("누적 확장", len(
        st.session_state.get("explorer_expansion_history", [])
    ))
    renderer_metric.metric("렌더러", performance.renderer.upper())
    st.caption(performance.message)
    if filtered.get("sampled_out_node_count"):
        st.warning(
            f"브라우저 안정성을 위해 "
            f"{filtered['sampled_out_node_count']:,}개 노드를 제외하고 "
            "루트·선택 노드를 우선 표시했습니다."
        )

    graph_column, detail_column = st.columns([3, 1])
    widget_selection = {
        "node_ids": selected_node_ids,
        "relationship_ids": selected_relationship_ids,
    }
    with graph_column:
        if not visual_spec["nodes"]:
            st.info("현재 필터에 표시할 노드가 없습니다.")
        else:
            try:
                from neo4j_viz import (
                    GraphSelection,
                    Node,
                    Relationship,
                    Renderer,
                    VisualizationGraph,
                )
                from neo4j_viz.streamlit import display_widget

                graph = VisualizationGraph(
                    nodes=[
                        Node(**node) for node in visual_spec["nodes"]
                    ],
                    relationships=[
                        Relationship(**relationship)
                        for relationship in visual_spec["relationships"]
                    ],
                )
                widget = graph.render_widget(
                    layout=layout,
                    renderer=(
                        Renderer.WEB_GL
                        if performance.renderer == "webgl"
                        else Renderer.CANVAS
                    ),
                    height="640px",
                    max_allowed_nodes=performance.recommended_limit,
                    theme="light",
                )
                widget.selected = GraphSelection(
                    nodeIds=selected_node_ids,
                    relationshipIds=selected_relationship_ids,
                )
                widget_key = (
                    f"graph-widget-{project_id}-{layout}-"
                    f"{st.session_state['explorer_widget_revision']}"
                )
                display_widget(widget, key=widget_key)
                widget_selection = {
                    "node_ids": list(widget.selected.nodeIds),
                    "relationship_ids": list(
                        widget.selected.relationshipIds
                    ),
                }
                st.caption(
                    "드래그로 이동 · 휠로 확대/축소 · 클릭으로 선택 · "
                    "우측 상단에서 레이아웃 전환"
                )
            except Exception as error:
                st.warning(
                    "인터랙티브 렌더러를 사용할 수 없어 안전한 "
                    f"Graphviz 보기로 전환했습니다: {error}"
                )
                st.graphviz_chart(
                    evidence_to_dot(filtered), width="stretch"
                )
    selected_node_ids = [
        node_id
        for node_id in widget_selection["node_ids"]
        if node_id in visible_node_ids
    ]
    selected_relationship_ids = [
        relationship_id
        for relationship_id in widget_selection["relationship_ids"]
        if relationship_id in visible_relationship_ids
    ]
    st.session_state["explorer_selected_node_ids"] = selected_node_ids
    st.session_state[
        "explorer_selected_relationship_ids"
    ] = selected_relationship_ids
    details = selected_entity_details(
        filtered,
        selected_node_ids,
        selected_relationship_ids,
    )
    with detail_column:
        st.markdown("#### 선택 상세")
        if details["nodes"]:
            selected_node = details["nodes"][0]
            st.markdown(
                f"**{node_caption(selected_node, identity_by_label)}**"
                .replace("\n", " · ")
            )
            st.json(selected_node.get("properties") or {}, expanded=True)
            selected_label = str(selected_node["label"])
            selected_identity_property = identity_by_label.get(
                selected_label
            )
            selected_identity = (
                (selected_node.get("properties") or {}).get(
                    selected_identity_property
                )
                if selected_identity_property
                else None
            )
            expand_depth = st.select_slider(
                "이 노드에서 확장",
                options=(1, 2, 3),
                value=1,
                key=f"graph-expand-depth-{project_id}",
            )
            if st.button(
                f"{expand_depth}-hop 추가",
                type="primary",
                width="stretch",
                key=f"graph-expand-action-{project_id}",
                disabled=selected_identity in (None, ""),
            ):
                try:
                    with st.spinner("선택 노드의 이웃을 확장합니다."):
                        incoming = services.graph.subgraph(
                            label=selected_label,
                            identity=str(selected_identity),
                            depth=expand_depth,
                            limit=result_limit,
                        )
                    validate_project_scope(incoming, project_id)
                    explorer_result["payload"] = merge_catalog_payload(
                        payload, incoming
                    )
                    st.session_state[
                        "explorer_result"
                    ] = explorer_result
                    st.session_state[
                        "explorer_expansion_history"
                    ].append(
                        {
                            "label": selected_label,
                            "identity": str(selected_identity),
                            "depth": expand_depth,
                        }
                    )
                    st.rerun()
                except Exception as error:
                    st.error(f"이웃 확장에 실패했습니다: {error}")
        elif details["relationships"]:
            relationship = details["relationships"][0]
            st.markdown(f"**:{relationship.get('type', 'RELATED')}**")
            st.caption(
                f"{relationship['source']} → {relationship['target']}"
            )
            st.json(
                relationship.get("properties") or {},
                expanded=True,
            )
        else:
            st.info("그래프에서 노드나 관계를 클릭하세요.")

    if evidence.get("truncated"):
        st.warning(
            f"서버 안전 한도에 따라 최대 {result_limit}개 경로만 "
            "조회했습니다. 검색어·필터·N-hop을 좁혀 탐색하세요."
        )
    node_tab, relationship_tab, history_tab = st.tabs(
        ["노드 목록", "관계 목록", "확장 이력"]
    )
    with node_tab:
        st.dataframe(
            pd.DataFrame(flatten_rows_for_table(filtered["nodes"])),
            width="stretch",
            hide_index=True,
        )
    with relationship_tab:
        if filtered["relationships"]:
            st.dataframe(
                pd.DataFrame(
                    flatten_rows_for_table(filtered["relationships"])
                ),
                width="stretch",
                hide_index=True,
            )
        else:
            st.info("선택한 깊이에서 연결 관계를 찾지 못했습니다.")
    with history_tab:
        st.dataframe(
            pd.DataFrame(
                st.session_state.get(
                    "explorer_expansion_history", []
                )
            ),
            width="stretch",
            hide_index=True,
        )


def render_startup_failure(error: Exception) -> None:
    st.error(
        f"서비스 연결 준비가 완료되지 않았습니다: {error}",
        icon="🩺",
    )
    st.code(str(error))
    checks = collect_demo_diagnostics(PROJECT_ROOT)
    st.markdown("#### 실행 진단")
    st.dataframe(
        pd.DataFrame(checks),
        width="stretch",
        hide_index=True,
    )
    st.markdown("#### 복구 명령")
    st.code(
        "./scripts/run_demo.sh\n"
        "# 또는\n"
        "./infra/set_homebrew_mode.sh reader\n"
        "./scripts/run_streamlit.sh",
        language="bash",
    )
    st.info(
        "생성 모델 인증이 없으면 자동 모드가 Gold 고정 데모로 전환됩니다. "
        "Neo4j 연결은 질의 실행에 필요합니다."
    )
    if st.button("서비스 다시 연결", type="primary"):
        get_services.clear()
        st.rerun()


def render_data_intake_workflow() -> None:
    intake = get_data_intake_service()
    st.markdown("#### CiP-DMD Data Intake")
    st.caption(
        "검증 기준과 동일한 CiP-DMD ZIP 번들만 staging할 수 있습니다. "
        "일부 파일이나 변경된 데이터는 실제 그래프에 적재되지 않습니다."
    )
    stage_column, policy_column = st.columns([1.45, 1])
    with stage_column:
        uploaded_bundle = st.file_uploader(
            "CiP-DMD 전체 폴더 구조가 포함된 ZIP (25MB 이하)",
            type=("zip",),
            accept_multiple_files=False,
            key="cip-dmd-intake-zip",
            help=(
                "cylinder, cylinder_bottom, piston_rod 하위의 메타데이터와 "
                "품질 CSV 8개를 원래 상대경로로 포함해야 합니다."
            ),
        )
        st.download_button(
            "검증용 CiP-DMD 번들 다운로드",
            data=get_reference_intake_archive(),
            file_name="cip_dmd_reference_bundle.zip",
            mime="application/zip",
            width="stretch",
            help="현재 프로젝트에 포함된 공개 데이터로 만든 데모 번들입니다.",
        )
        if st.button(
            "1 · 번들 staging",
            type="secondary",
            width="stretch",
            disabled=uploaded_bundle is None,
            key="stage-intake-bundle",
        ):
            try:
                with st.spinner("ZIP 경로·크기·필수 파일·해시를 검사합니다."):
                    record = intake.stage_archive(
                        uploaded_bundle.name,
                        uploaded_bundle.getvalue(),
                    )
                st.session_state["intake_record"] = record
                st.session_state["intake_approval_token"] = None
            except Exception as error:
                st.error(f"번들 staging 실패: {error}")
    with policy_column:
        st.markdown(
            """
            <div class="p3-section-note">
              <b>안전 정책</b><br>
              ZIP 경로 탈출 차단 · 압축 해제 크기 제한 · 필수 파일 8개
              고정 매핑 · 기준 원본 SHA-256 일치 · dry-run PASS ·
              30분 승인 토큰 · 단일 적재 잠금 · reader 모드 자동 복귀
            </div>
            """,
            unsafe_allow_html=True,
        )

    record = st.session_state.get("intake_record")
    if record:
        status_columns = st.columns(4)
        status_columns[0].metric("Run 상태", record["status"])
        status_columns[1].metric(
            "필수 파일", len(record.get("source_files", []))
        )
        status_columns[2].metric(
            "원본 일치",
            "PASS" if record.get("canonical_bundle_match") else "REVIEW",
        )
        status_columns[3].metric(
            "Run ID", record["run_id"].split("-")[0]
        )
        with st.expander("파일 매핑·해시 상세"):
            st.dataframe(
                pd.DataFrame(record.get("source_files", [])),
                width="stretch",
                hide_index=True,
                column_config={
                    "sha256": st.column_config.TextColumn(width="medium"),
                    "canonical_sha256": st.column_config.TextColumn(
                        width="medium"
                    ),
                },
            )

        if record["status"] == "staged":
            if not record.get("canonical_bundle_match"):
                st.warning(
                    "필수 구조는 확인했지만 검증 기준 원본과 다른 파일이 "
                    "있어 자동 적재를 중단했습니다."
                )
            if st.button(
                "2 · ETL dry-run",
                type="primary",
                width="stretch",
                disabled=not record.get("canonical_bundle_match"),
                key=f"dry-run-{record['run_id']}",
            ):
                try:
                    with st.spinner(
                        "Extract → Transform → Validate를 실행합니다."
                    ):
                        dry_run = intake.dry_run(record["run_id"])
                    st.session_state["intake_record"] = {
                        key: value
                        for key, value in dry_run.items()
                        if key != "approval_token"
                    }
                    st.session_state["intake_approval_token"] = dry_run[
                        "approval_token"
                    ]
                    st.rerun()
                except Exception as error:
                    st.error(f"ETL dry-run 실패: {error}")

        if record["status"] == "dry_run_pass":
            validation = record["validation"]
            st.success(
                "ETL dry-run PASS · 실제 Neo4j에는 아직 아무것도 "
                "기록하지 않았습니다."
            )
            count_rows = [
                {"entity_or_relation": name, "projected_count": count}
                for name, count in validation["counts"].items()
            ]
            st.dataframe(
                pd.DataFrame(count_rows),
                width="stretch",
                hide_index=True,
            )
            st.caption(
                f"격리 예정 레코드 "
                f"{validation['quarantined_count']}건 · "
                f"승인 만료 {record['approval_expires_at']}"
            )

            confirmation_text = f"LOAD {record['run_id']}"
            st.markdown("##### 실제 적재 승인")
            st.code(confirmation_text)
            acknowledged = st.checkbox(
                "현재 그래프가 일시적으로 재시작되며, 적재 후 reader "
                "모드로 복귀하는 것에 동의합니다.",
                key=f"approve-intake-{record['run_id']}",
            )
            confirmation = st.text_input(
                "위 확인 문구를 정확히 입력",
                key=f"confirm-intake-{record['run_id']}",
            )
            ui_load_enabled = os.getenv("P3_ENABLE_UI_LOAD") == "1"
            approval_token = st.session_state.get(
                "intake_approval_token"
            )
            if not ui_load_enabled:
                st.info(
                    "실제 적재는 기본 비활성화 상태입니다. 관리자가 "
                    "`P3_ENABLE_UI_LOAD=1`로 앱을 시작한 경우에만 "
                    "승인 버튼이 활성화됩니다."
                )
            if approval_token is None:
                st.warning(
                    "승인 토큰이 현재 세션에 없습니다. dry-run을 다시 "
                    "실행해 새 토큰을 발급하세요."
                )
            can_load = (
                ui_load_enabled
                and approval_token is not None
                and acknowledged
                and confirmation == confirmation_text
            )
            if st.button(
                "3 · 승인 후 Neo4j 적재",
                type="primary",
                width="stretch",
                disabled=not can_load,
                key=f"load-intake-{record['run_id']}",
            ):
                try:
                    with st.spinner(
                        "loader 전환 → 적재 → 건수 검증 → reader 복귀"
                    ):
                        loaded = intake.load(
                            record["run_id"],
                            approval_token=approval_token,
                            confirmation=confirmation,
                        )
                    st.session_state["intake_record"] = loaded
                    st.session_state["intake_approval_token"] = None
                    get_services.clear()
                    st.success(
                        "적재와 reader 모드 복귀를 완료했습니다. 다음 "
                        "화면 갱신부터 새 연결을 사용합니다."
                    )
                except Exception as error:
                    st.error(f"승인 적재 실패: {error}")

        if record["status"] == "load_pass":
            st.success("적재 완료 · Neo4j reader 모드 복귀 확인")
        elif record["status"] in {"dry_run_failed", "load_failed"}:
            st.error(record.get("error", "Data Intake 작업이 실패했습니다."))

    with st.expander("최근 Data Intake 실행·감사로그"):
        recent_runs = intake.list_runs(limit=10)
        if recent_runs:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "run_id": item["run_id"],
                            "status": item["status"],
                            "filename": item.get("original_filename"),
                            "created_at": item.get("created_at"),
                            "updated_at": item.get("updated_at"),
                        }
                        for item in recent_runs
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
        events = intake.recent_audit_events(limit=20)
        if events:
            st.dataframe(
                pd.DataFrame(events),
                width="stretch",
                hide_index=True,
            )
        if not recent_runs and not events:
            st.info("아직 Data Intake 실행 기록이 없습니다.")

    with st.expander("개별 파일 빠른 사전검증"):
        uploaded_files = st.file_uploader(
            "메타데이터 JSON 또는 품질 CSV (10MB 이하)",
            type=("json", "csv"),
            accept_multiple_files=True,
            key="candidate-source-files",
            help=(
                "이 검사는 파일 구조와 공통 ID 후보만 확인하며 실제 "
                "적재 승인으로 사용되지 않습니다."
            ),
        )
        if uploaded_files:
            inspections = [
                inspect_uploaded_source(file.name, file.getvalue())
                for file in uploaded_files
            ]
            st.dataframe(
                pd.DataFrame(inspections),
                width="stretch",
                hide_index=True,
            )


def render_data_health_tab(
    services: ServiceBundle | None, snapshot: dict[str, Any] | None
) -> None:
    st.subheader("데이터 적재와 실행 진단")
    st.caption(
        "운영 그래프는 읽기 전용으로 유지합니다. 전체 번들은 staging과 "
        "dry-run을 통과하고 명시적으로 승인된 경우에만 잠시 loader로 "
        "전환됩니다. 현재 질의 provider: "
        f"{services.provider if services is not None else '연결 전'}"
    )
    checks = collect_demo_diagnostics(PROJECT_ROOT)
    check_columns = st.columns(len(checks))
    for column, check in zip(check_columns, checks):
        column.metric(check["check"], check["status"])
        column.caption(check["detail"])

    st.markdown("#### 최근 ETL 실행")
    etl = (snapshot or {}).get("etl")
    if etl:
        etl_columns = st.columns(5)
        etl_columns[0].metric("상태", etl["status"])
        etl_columns[1].metric("모드", etl["mode"])
        etl_columns[2].metric("멱등성", etl["idempotency_status"])
        etl_columns[3].metric("격리 레코드", etl["quarantined_count"])
        etl_columns[4].metric("적재 지표 유형", len(etl["counts"]))
        st.success(f"최근 적재 완료 · {etl['finished_at']}")
        with st.expander("ETL 적재 건수 상세"):
            st.dataframe(
                pd.DataFrame(
                    [
                        {"entity_or_relation": key, "count": value}
                        for key, value in etl["counts"].items()
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
            st.caption(f"실행 리포트 · {etl['report_path']}")
    else:
        st.warning("성공한 ETL load 기록을 찾지 못했습니다.")

    st.divider()
    render_generic_dataset_upload()
    st.divider()
    render_data_intake_workflow()


def get_pipeline_job_store() -> PipelineJobStore:
    return PipelineJobStore(
        PROJECT_ROOT / "data" / "processed" / "pipeline_jobs.sqlite3"
    )


def render_onboarding_stage(project: dict[str, Any]) -> None:
    progress = onboarding_progress(project["status"])
    st.progress(progress["percent"], text=f"온보딩 {progress['percent']}%")
    columns = st.columns(len(progress["steps"]))
    for column, step in zip(columns, progress["steps"]):
        marker = {
            "complete": "✓",
            "active": "●",
            "pending": "○",
        }[step["state"]]
        column.caption(f"{marker} {step['label']}")


def render_pipeline_jobs(project_id: str) -> None:
    jobs = get_pipeline_job_store().list(project_id, limit=8)
    st.markdown("#### 작업 상태")
    if not jobs:
        render_view_state(
            ViewState.EMPTY,
            page="Pipeline",
            detail="업로드·연결·매핑·적재 작업을 시작하면 여기에 기록됩니다.",
        )
        return
    store = get_pipeline_job_store()
    for job in jobs:
        status = job_status_presentation(job["status"])
        with st.expander(
            f"{status['label']} · {job['kind']} · "
            f"{job['job_id'][:8]} · 시도 {job['attempt']}",
            expanded=job["status"] in {"queued", "running", "failed"},
        ):
            st.progress(
                int(job["progress"]),
                text=f"{job['current_step']} · {job['message']}",
            )
            metrics = st.columns(5)
            metrics[0].metric("상태", status["label"])
            metrics[1].metric("진행률", f"{job['progress']}%")
            metrics[2].metric(
                "처리량",
                (
                    f"{job['processed_rows']:,}/"
                    f"{job['total_rows']:,}"
                    if job["total_rows"]
                    else f"{job['processed_rows']:,}"
                ),
            )
            metrics[3].metric("현재 단계", job["current_step"])
            metrics[4].metric(
                "경과시간",
                format_elapsed(job_elapsed_seconds(job)),
            )
            if job.get("error"):
                st.error(job["error"])
            logs = store.logs(job["job_id"])
            if logs:
                st.dataframe(
                    pd.DataFrame(logs),
                    width="stretch",
                    hide_index=True,
                )
            action_columns = st.columns([1, 1, 4])
            if job["status"] in {"queued", "running"}:
                if action_columns[0].button(
                    "취소",
                    key=f"cancel-job-{job['job_id']}",
                ):
                    try:
                        store.cancel(job["job_id"])
                        st.rerun()
                    except ValueError as error:
                        st.warning(str(error))
            if job["status"] in {"failed", "cancelled"}:
                if action_columns[1].button(
                    "재시도 등록",
                    key=f"retry-job-{job['job_id']}",
                ):
                    store.retry(job["job_id"])
                    st.rerun()
    if st.button("작업 상태 새로고침", key=f"refresh-jobs-{project_id}"):
        st.rerun()


def _profile_uploaded_files(
    project: dict[str, Any],
    files: list[Any],
) -> dict[str, Any]:
    project_id = project["project_id"]
    payload = [
        {
            "filename": file.name,
            "content_base64": base64.b64encode(file.getvalue()).decode(),
        }
        for file in files
    ]
    api = FactoryGraphApiClient()
    try:
        if api.live():
            return api.profile_project_files(project_id, payload)
    finally:
        api.close()

    registry = ProjectRegistry(
        PROJECT_ROOT / "data" / "processed" / "projects.sqlite3"
    )
    current = registry.require(project_id)
    if current["status"] != "profiling":
        registry.transition(
            project_id, "profiling", reason="ui_profile_started"
        )
    datasets = DatasetWorkspace(
        PROJECT_ROOT / "data" / "processed" / "project_uploads"
    )
    try:
        result = datasets.profile_upload(project_id, payload)
        registry.update(project_id, source_version=result["upload_id"])
        registry.record_artifact(
            project_id,
            "source",
            version=result["upload_id"],
            fingerprint=result.get("source_sha256"),
            metadata={
                "upload_id": result["upload_id"],
                "file_count": len(result.get("files", [])),
            },
        )
        registry.transition(
            project_id,
            "mapping_review",
            reason="ui_profile_completed",
        )
        return result
    except Exception:
        if registry.require(project_id)["status"] == "profiling":
            registry.transition(
                project_id, "failed", reason="ui_profile_failed"
            )
        raise


def render_generic_dataset_upload() -> None:
    project_id = st.session_state.get("active_project_id", "cip-dmd")
    projects = ProjectRegistry(
        PROJECT_ROOT / "data" / "processed" / "projects.sqlite3"
    )
    project = projects.require(project_id)
    if notice := st.session_state.pop("project_created_notice", None):
        st.success(
            f"`{notice}` 프로젝트를 만들었습니다. 첫 데이터 소스를 등록하세요."
        )
    st.markdown("#### 프로젝트 데이터 온보딩")
    st.caption(
        f"`{project_id}` · {project['source_type']} 소스 · "
        "승인 전에는 운영 Neo4j가 변경되지 않습니다."
    )
    render_onboarding_stage(project)
    if project["source_type"] == "neo4j":
        render_neo4j_source_connection(project)
        render_pipeline_jobs(project_id)
        return

    files = st.file_uploader(
        "파일을 끌어 놓거나 선택하세요 (CSV/JSON/XLSX/ZIP)",
        type=("csv", "json", "xlsx", "zip"),
        accept_multiple_files=True,
        key=f"project-upload-{project_id}",
        help="파일당 10MB, 한 번에 최대 10개. ZIP은 안전 검사 후 펼칩니다.",
    )
    if st.button(
        "업로드·정제·프로파일링",
        disabled=not files,
        width="stretch",
        key=f"profile-upload-{project_id}",
    ):
        store = get_pipeline_job_store()
        job = store.create(
            project_id,
            "profile",
            message=f"{len(files)}개 원본 파일 검증 대기",
        )
        try:
            store.start(
                job["job_id"],
                "extract",
                "파일 해시·확장자·압축 경로를 검증합니다.",
            )
            store.update(
                job["job_id"],
                current_step="profile",
                progress=45,
                message="정규화된 테이블의 타입·결측·ID 후보를 분석합니다.",
            )
            result = _profile_uploaded_files(project, files)
            total_rows = sum(
                int(file.get("row_count", 0)) for file in result["files"]
            )
            store.succeed(
                job["job_id"],
                step="profile_complete",
                message="데이터 프로파일과 lineage 저장을 완료했습니다.",
                result={
                    "upload_id": result["upload_id"],
                    "file_count": len(result["files"]),
                },
                processed_rows=total_rows,
                total_rows=total_rows,
            )
            st.session_state["latest_project_upload"] = result
            st.success(
                f"{len(result['files'])}개 파일 프로파일 완료 · "
                f"upload {result['upload_id'][:8]}"
            )
        except Exception as error:
            store.fail(
                job["job_id"], step="profile", error=str(error)
            )
            st.error(f"프로파일링 실패: {error}")
    datasets = DatasetWorkspace(
        PROJECT_ROOT / "data" / "processed" / "project_uploads"
    )
    uploads = datasets.list(project_id)
    latest = (
        st.session_state.get("latest_project_upload")
        if st.session_state.get("latest_project_upload", {}).get(
            "project_id"
        )
        == project_id
        else uploads[0]
        if uploads
        else None
    )
    if latest:
        warnings = profile_quality_warnings(latest)
        summary = st.columns(4)
        summary[0].metric("원본 파일", len(latest.get("sources", [])))
        summary[1].metric("정규화 테이블", len(latest["files"]))
        summary[2].metric(
            "전체 행",
            f"{sum(file['row_count'] for file in latest['files']):,}",
        )
        summary[3].metric("품질 경고", len(warnings))
        if warnings:
            st.warning("\n".join(f"- {warning}" for warning in warnings))
        else:
            st.success("ID 후보와 컬럼 품질 기본 검사를 통과했습니다.")
        for file in latest["files"]:
            with st.expander(
                f"{file['filename']} · {file['row_count']}행 "
                f"× {file['column_count']}열"
            ):
                st.dataframe(
                    pd.DataFrame(file["columns"]),
                    width="stretch",
                    hide_index=True,
                )
                source_path = (
                    PROJECT_ROOT
                    / "data"
                    / "processed"
                    / "project_uploads"
                    / project_id
                    / latest["upload_id"]
                    / "source"
                    / file["filename"]
                )
                try:
                    sample_rows = pd.read_csv(source_path, nrows=20)
                    st.caption("샘플 20행")
                    st.dataframe(
                        sample_rows, width="stretch", hide_index=True
                    )
                except Exception:
                    st.caption("샘플은 Pipeline dry-run에서 확인합니다.")
        if st.button(
            "Pipeline에서 매핑 검토 →",
            type="primary",
            key=f"goto-schema-{project_id}",
        ):
            navigate_to_page("Pipeline")
            st.rerun()
    render_pipeline_jobs(project_id)


def render_neo4j_source_connection(project: dict[str, Any]) -> None:
    st.markdown("##### 기존 Neo4j 연결")
    st.info(
        "비밀번호 값은 저장하지 않습니다. 서버 환경변수 이름만 등록하고 "
        "스키마 introspection·샘플 READ 질의를 통과해야 승인할 수 있습니다."
    )
    with st.form(f"neo4j-source-{project['project_id']}"):
        uri = st.text_input("URI", placeholder="neo4j://graph.internal:7687")
        database = st.text_input("Database", value="neo4j")
        username = st.text_input("Username", value="neo4j")
        password_env = st.text_input(
            "비밀번호 환경변수", placeholder="FACTORY_NEO4J_PASSWORD"
        )
        submitted = st.form_submit_button(
            "연결·스키마 검증",
            type="primary",
            width="stretch",
        )
    if submitted:
        store = get_pipeline_job_store()
        job = store.create(
            project["project_id"],
            "neo4j_connect",
            message="Neo4j 연결 검증 대기",
        )
        api = FactoryGraphApiClient()
        try:
            store.start(
                job["job_id"], "connect", "연결과 READ 권한을 확인합니다."
            )
            result = api.validate_neo4j_connector(
                project["project_id"],
                {
                    "uri": uri,
                    "database": database,
                    "username": username,
                    "password_env": password_env,
                },
            )
            store.update(
                job["job_id"],
                current_step="introspection",
                progress=70,
                message="라벨·관계·속성과 샘플 건수를 확인했습니다.",
            )
            store.succeed(
                job["job_id"],
                step="validated",
                message="Neo4j 연결 검증이 완료됐습니다.",
                result=result,
            )
            st.session_state["validated_connector"] = result
        except Exception as error:
            store.fail(job["job_id"], step="connect", error=str(error))
            st.error(str(error))
        finally:
            api.close()
    connector = st.session_state.get("validated_connector")
    if connector and connector.get("project_id") == project["project_id"]:
        st.success(
            f"연결 검증 완료 · 노드 {connector['counts'].get('nodes', 0):,} · "
            f"관계 {connector['counts'].get('relationships', 0):,}"
        )
        if st.button(
            "검증된 연결 승인",
            key=f"approve-connector-{connector['connector_id']}",
            type="primary",
        ):
            api = FactoryGraphApiClient()
            try:
                approved = api.approve_neo4j_connector(
                    project["project_id"], connector["connector_id"]
                )
                st.session_state["validated_connector"] = approved
                st.success("연결 승인과 프로젝트 스키마 등록을 완료했습니다.")
            except Exception as error:
                st.error(str(error))
            finally:
                api.close()


def render_evidence_tab() -> None:
    st.subheader("답변 근거")
    result = st.session_state.get("last_result")
    if not result:
        st.info(
            "Query Studio에서 질문을 실행하면 결과표와 관계 경로가 표시됩니다.",
            icon="ℹ️",
        )
        return

    render_response_summary(result)
    row_metric, node_metric, rel_metric, attempt_metric = st.columns(4)
    row_metric.metric("결과 행", result.get("row_count", 0))
    evidence = result.get("evidence", {})
    node_metric.metric("근거 노드", evidence.get("node_count", 0))
    rel_metric.metric("근거 관계", evidence.get("relationship_count", 0))
    attempt_metric.metric(
        "검증 시도", result.get("validation", {}).get("attempts", 0)
    )

    table_tab, graph_tab, cypher_tab, trace_tab = st.tabs(
        ["결과표", "부분 그래프", "Cypher", "검증 이력"]
    )
    with table_tab:
        rows = result.get("rows", [])
        if rows:
            flattened = flatten_rows_for_table(rows)
            st.dataframe(
                pd.DataFrame(flattened),
                width="stretch",
                hide_index=True,
            )
            st.download_button(
                "CSV 다운로드",
                data=rows_to_csv(rows),
                file_name="p3_query_result.csv",
                mime="text/csv",
            )
        else:
            st.info("표시할 결과 행이 없습니다.")

    with graph_tab:
        if evidence.get("nodes"):
            available_labels = sorted(
                {node["label"] for node in evidence["nodes"]}
            )
            available_relationships = sorted(
                {
                    relationship["type"]
                    for relationship in evidence.get("relationships", [])
                }
            )
            filter_column, relationship_column, layout_column = st.columns(
                [2, 2, 1]
            )
            selected_labels = filter_column.multiselect(
                "노드 유형",
                available_labels,
                default=available_labels,
                key="evidence-label-filter",
            )
            selected_relationships = relationship_column.multiselect(
                "관계 유형",
                available_relationships,
                default=available_relationships,
                key="evidence-relationship-filter",
            )
            layout = layout_column.radio(
                "방향",
                options=("좌→우", "위→아래"),
                horizontal=True,
                key="evidence-layout",
            )
            include_isolated = st.checkbox(
                "연결되지 않은 근거 노드도 표시",
                value=True,
                key="evidence-isolated",
            )
            filtered_evidence = filter_evidence(
                evidence,
                labels=set(selected_labels),
                relationship_types=set(selected_relationships),
                include_isolated=include_isolated,
            )
            filtered_metrics = st.columns(2)
            filtered_metrics[0].caption(
                f"현재 표시 · 노드 {filtered_evidence['node_count']}개"
            )
            filtered_metrics[1].caption(
                f"현재 표시 · 관계 {filtered_evidence['relationship_count']}개"
            )
            st.graphviz_chart(
                evidence_to_dot(
                    filtered_evidence,
                    rankdir="LR" if layout == "좌→우" else "TB",
                ),
                width="stretch",
            )
            legend = " · ".join(
                f"{label} {sum(node['label'] == label for node in filtered_evidence['nodes'])}"
                for label in sorted(
                    {node["label"] for node in filtered_evidence["nodes"]}
                )
            )
            if legend:
                st.caption(f"범례 · {legend}")
            with st.expander("그래프 근거 상세"):
                node_detail, relationship_detail = st.tabs(
                    ["노드", "관계"]
                )
                with node_detail:
                    st.dataframe(
                        pd.DataFrame(
                            flatten_rows_for_table(
                                filtered_evidence["nodes"]
                            )
                        ),
                        width="stretch",
                        hide_index=True,
                    )
                with relationship_detail:
                    if filtered_evidence["relationships"]:
                        st.dataframe(
                            pd.DataFrame(
                                flatten_rows_for_table(
                                    filtered_evidence["relationships"]
                                )
                            ),
                            width="stretch",
                            hide_index=True,
                        )
                    else:
                        st.info("현재 필터에 해당하는 관계가 없습니다.")
            truncation = evidence.get("truncated", {})
            if any(truncation.values()):
                st.info(
                    "가독성을 위해 전체 결과 중 일부 근거만 표시합니다. "
                    f"전체 {evidence.get('source_row_count', 0)}행 중 "
                    f"{evidence.get('visualized_row_count', 0)}행을 시각화했습니다."
                )
        else:
            st.info(
                "이 질의는 집계 결과이거나 경로 ID가 없어 관계를 추측해 표시하지 않습니다."
            )

    with cypher_tab:
        if result.get("cypher"):
            st.code(result["cypher"], language="cypher", line_numbers=True)
        else:
            st.info("실행된 Cypher가 없습니다.")

    with trace_tab:
        validation = result.get("validation", {})
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
            st.success("모든 검증 단계를 통과했습니다.")


def normalize_dashboard_snapshot(
    raw_snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Keep domain-specific dashboards usable when optional KPIs do not exist."""

    snapshot = deepcopy(raw_snapshot)
    snapshot.setdefault("totals", {"nodes": 0, "relationships": 0})
    snapshot.setdefault("node_counts", [])
    snapshot.setdefault("relationship_counts", [])
    snapshot.setdefault("equipment_runs", [])
    snapshot.setdefault("anomaly_runs", [])
    snapshot.setdefault("quality_failures", [])
    integrity = snapshot.setdefault("integrity", {})
    for key in (
        "complete_genealogy",
        "incomplete_genealogy",
        "orphan_process_runs",
        "orphan_measurements",
        "quality_failure_count",
    ):
        if integrity.get(key) is None:
            integrity[key] = 0
    integrity.setdefault("genealogy_rate", 0.0)
    evaluation = snapshot.setdefault("evaluation", {})
    evaluation_defaults = {
        "schema_version": "project-defined",
        "gold_execution_success_rate": 0.0,
        "read_only_compliance_rate": 0.0,
        "unit_test_count": 0,
        "blind_result_accuracy": None,
        "blind_evaluation_status": "not_run",
    }
    for key, value in evaluation_defaults.items():
        evaluation.setdefault(key, value)
    runtime = snapshot.setdefault("runtime", {})
    runtime_defaults = {
        "query_count": 0,
        "success_rate": None,
        "average_elapsed_ms": 0.0,
        "median_elapsed_ms": 0.0,
        "p95_elapsed_ms": 0.0,
        "correction_count": 0,
        "correction_success_rate": None,
        "status_counts": [],
        "provider_counts": [],
        "recent_queries": [],
        "model_call_count": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "estimated_cost_usd": 0.0,
        "error_count": 0,
        "error_rate": None,
    }
    for key, value in runtime_defaults.items():
        runtime.setdefault(key, value)
    snapshot.setdefault("runtime_scope", {})
    snapshot.setdefault("provenance", {})
    return snapshot


def render_dashboard_scope_filters(
    snapshot: dict[str, Any],
    *,
    key_prefix: str = "dashboard",
) -> dict[str, Any]:
    runtime = snapshot.get("runtime") or {}
    providers = [
        str(row.get("provider"))
        for row in runtime.get("provider_counts", [])
        if row.get("provider")
    ]
    statuses = [
        str(row.get("status"))
        for row in runtime.get("status_counts", [])
        if row.get("status")
    ]
    st.markdown("#### 전역 운영 필터")
    project_id = st.session_state.get("active_project_id", "cip-dmd")
    columns = st.columns([1, 2, 2, 2])
    columns[0].text_input(
        "프로젝트",
        value=project_id,
        disabled=True,
        key=f"{key_prefix}-project-{project_id}",
    )
    selected_providers = columns[1].multiselect(
        "Provider",
        options=providers,
        default=[],
        placeholder="전체 provider",
        key=f"{key_prefix}-provider-{project_id}",
    )
    selected_statuses = columns[2].multiselect(
        "실행 상태",
        options=statuses,
        default=[],
        placeholder="전체 상태",
        key=f"{key_prefix}-status-{project_id}",
    )
    window = columns[3].selectbox(
        "기간",
        options=("전체", "최근 7일", "최근 30일", "최근 90일"),
        key=f"{key_prefix}-window-{project_id}",
    )
    days = {
        "전체": None,
        "최근 7일": 7,
        "최근 30일": 30,
        "최근 90일": 90,
    }[window]
    filters = {
        "providers": selected_providers,
        "statuses": selected_statuses,
        "days": days,
    }
    st.session_state["evaluation_filters"][project_id] = filters
    return filters


def render_metric_provenance(snapshot: dict[str, Any]) -> None:
    provenance = snapshot.get("provenance") or {}
    scope = snapshot.get("runtime_scope") or {}
    etl = snapshot.get("etl")
    with st.expander("지표 원본·집계 범위"):
        rows = [
            {
                "source": "Neo4j",
                "scope": provenance.get("graph_project_id", "현재 프로젝트"),
                "records": (
                    snapshot.get("totals", {}).get("nodes", 0)
                ),
                "version": snapshot.get("evaluation", {}).get(
                    "schema_version", "project-defined"
                ),
            },
            {
                "source": provenance.get("metrics_file") or "평가 미실행",
                "scope": "승인된 평가 결과",
                "records": snapshot.get("evaluation", {}).get(
                    "blind_question_count", 0
                ),
                "version": (
                    provenance.get("metrics_sha256") or "—"
                )[:12],
            },
            {
                "source": provenance.get("audit_file", "query audit"),
                "scope": (
                    f"{scope.get('filtered_event_count', 0)} / "
                    f"{scope.get('source_event_count', 0)} events"
                ),
                "records": scope.get("filtered_event_count", 0),
                "version": provenance.get("generated_at", "현재"),
            },
        ]
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        if etl:
            st.caption(
                "최근 ETL · "
                f"{etl.get('finished_at') or etl.get('started_at')} · "
                f"{etl.get('status')} · 멱등성 {etl.get('idempotency_status')}"
            )


def render_dashboard_tab(
    services: ServiceBundle, snapshot: dict[str, Any] | None = None
) -> None:
    st.subheader("그래프와 평가 현황")
    st.caption(
        "모든 위젯은 현재 프로젝트와 동일한 provider·상태·기간 범위를 "
        "사용합니다. 그래프 수치는 Neo4j, 품질 수치는 승인된 평가 산출물에서 조회합니다."
    )
    if snapshot is None:
        try:
            snapshot = services.dashboard.snapshot()
        except Exception as error:
            st.error(f"대시보드 데이터를 불러오지 못했습니다: {error}")
            return
    runtime_filters = render_dashboard_scope_filters(snapshot)
    if any(runtime_filters.values()):
        try:
            snapshot = services.dashboard.snapshot(runtime_filters)
        except Exception as error:
            st.warning(f"필터 적용에 실패해 전체 범위를 표시합니다: {error}")
    snapshot = normalize_dashboard_snapshot(snapshot)

    totals = snapshot["totals"]
    evaluation = snapshot["evaluation"]
    metric_columns = st.columns(6)
    metric_columns[0].metric("전체 노드", f"{totals['nodes']:,}")
    metric_columns[1].metric(
        "전체 관계", f"{totals['relationships']:,}"
    )
    metric_columns[2].metric("스키마", evaluation["schema_version"])
    metric_columns[3].metric(
        "Gold 실행", f"{evaluation['gold_execution_success_rate']:.0%}"
    )
    metric_columns[4].metric(
        "읽기 전용", f"{evaluation['read_only_compliance_rate']:.0%}"
    )
    metric_columns[5].metric("자동 테스트", evaluation["unit_test_count"])

    st.markdown("#### 데이터 무결성")
    integrity = snapshot["integrity"]
    integrity_columns = st.columns(5)
    integrity_columns[0].metric(
        "Genealogy 완전성", f"{integrity['genealogy_rate']:.1%}"
    )
    integrity_columns[1].metric(
        "완전 연결 제품", f"{integrity['complete_genealogy']:,}"
    )
    integrity_columns[2].metric(
        "불완전 연결", f"{integrity['incomplete_genealogy']:,}"
    )
    integrity_columns[3].metric(
        "고아 공정/측정",
        f"{integrity['orphan_process_runs']} / "
        f"{integrity['orphan_measurements']}",
    )
    integrity_columns[4].metric(
        "품질 불합격", f"{integrity['quality_failure_count']:,}"
    )

    structure_tab, process_tab, quality_tab = st.tabs(
        ["그래프 구조", "공정·장비", "이상·품질"]
    )
    with structure_tab:
        left, right = st.columns(2)
        with left:
            st.markdown("##### 노드 유형")
            st.bar_chart(
                pd.DataFrame(snapshot["node_counts"]),
                x="label",
                y="count",
                color="#0F766E",
                horizontal=True,
            )
        with right:
            st.markdown("##### 관계 유형")
            st.bar_chart(
                pd.DataFrame(snapshot["relationship_counts"]),
                x="relationship_type",
                y="count",
                color="#2563EB",
                horizontal=True,
            )
    with process_tab:
        left, right = st.columns(2)
        with left:
            st.markdown("##### 장비별 공정 실행")
            if snapshot["equipment_runs"]:
                st.bar_chart(
                    pd.DataFrame(snapshot["equipment_runs"]),
                    x="equipment",
                    y="run_count",
                    color="#7C3AED",
                    horizontal=True,
                )
            else:
                st.info("이 스키마에는 장비별 공정 집계가 정의되지 않았습니다.")
        with right:
            st.markdown("##### 장비 상세")
            if snapshot["equipment_runs"]:
                st.dataframe(
                    pd.DataFrame(snapshot["equipment_runs"]),
                    width="stretch",
                    hide_index=True,
                )
            else:
                st.info("표시할 장비 집계가 없습니다.")
    with quality_tab:
        left, right = st.columns(2)
        with left:
            st.markdown("##### 이상 유형 분포")
            if snapshot["anomaly_runs"]:
                st.bar_chart(
                    pd.DataFrame(snapshot["anomaly_runs"]),
                    x="anomaly_code",
                    y="run_count",
                    color="#DC2626",
                )
            else:
                st.info("이 스키마에는 이상 유형 집계가 정의되지 않았습니다.")
        with right:
            st.markdown("##### 품질 불합격 상위 항목")
            if snapshot["quality_failures"]:
                st.bar_chart(
                    pd.DataFrame(snapshot["quality_failures"]),
                    x="feature",
                    y="failure_count",
                    color="#D97706",
                    horizontal=True,
                )
            else:
                st.info("이 스키마에는 품질 불합격 집계가 정의되지 않았습니다.")

    st.markdown("#### Agent 품질과 런타임")
    runtime = snapshot["runtime"]

    def rate_text(value: float | None) -> str:
        return "—" if value is None else f"{value:.0%}"

    runtime_columns = st.columns(6)
    runtime_columns[0].metric("누적 질의", runtime["query_count"])
    runtime_columns[1].metric(
        "런타임 성공률", rate_text(runtime["success_rate"])
    )
    runtime_columns[2].metric(
        "평균 응답시간", f"{runtime['average_elapsed_ms']:.0f}ms"
    )
    runtime_columns[3].metric(
        "자기수정 시도", runtime["correction_count"]
    )
    runtime_columns[4].metric(
        "자기수정 성공률",
        rate_text(runtime["correction_success_rate"]),
    )
    blind_accuracy = evaluation.get("blind_result_accuracy")
    runtime_columns[5].metric(
        "Blind 의미값 정확도",
        "평가 전" if blind_accuracy is None else f"{blind_accuracy:.0%}",
    )

    usage_columns = st.columns(4)
    usage_columns[0].metric(
        "모델 호출", f"{runtime['model_call_count']:,}"
    )
    usage_columns[1].metric(
        "입력 토큰", f"{runtime['input_tokens']:,}"
    )
    usage_columns[2].metric(
        "출력 토큰", f"{runtime['output_tokens']:,}"
    )
    usage_columns[3].metric(
        "추정 모델 비용",
        f"${runtime['estimated_cost_usd']:.4f}",
    )

    status_column, recent_column = st.columns([1, 2])
    with status_column:
        st.markdown("##### 질의 상태")
        if runtime["status_counts"]:
            st.bar_chart(
                pd.DataFrame(runtime["status_counts"]),
                x="status",
                y="count",
                color="#0F766E",
            )
        else:
            st.info("아직 기록된 질의가 없습니다.")
    with recent_column:
        st.markdown("##### 최근 질의")
        if runtime["recent_queries"]:
            st.dataframe(
                pd.DataFrame(runtime["recent_queries"]),
                width="stretch",
                hide_index=True,
                column_config={
                    "question": st.column_config.TextColumn(width="large"),
                    "elapsed_ms": st.column_config.NumberColumn(
                        "elapsed_ms", format="%d ms"
                    ),
                },
            )
        else:
            st.info("Query Studio에서 질문을 실행하면 이력이 기록됩니다.")

    st.markdown("#### 도메인 전문가 검증")
    feedback_service = getattr(services, "feedback", None)
    if feedback_service is None:
        st.info("전문가 검증 기록 서비스가 구성되지 않았습니다.")
    else:
        feedback = feedback_service.summary()
        feedback_columns = st.columns(5)
        feedback_columns[0].metric(
            "전체 판정", feedback["total_reviews"]
        )
        feedback_columns[1].metric(
            "검토한 질의", feedback["unique_queries_reviewed"]
        )
        feedback_columns[2].metric(
            "검증 완료", feedback["decision_counts"]["verified"]
        )
        feedback_columns[3].metric(
            "추가 확인",
            feedback["decision_counts"]["needs_followup"],
        )
        feedback_columns[4].metric(
            "이견 있음", feedback["decision_counts"]["disputed"]
        )
        if feedback["recent"]:
            st.dataframe(
                pd.DataFrame(feedback["recent"]),
                width="stretch",
                hide_index=True,
                column_config={
                    "question": st.column_config.TextColumn(width="large"),
                    "cypher": st.column_config.TextColumn(width="large"),
                    "note": st.column_config.TextColumn(width="large"),
                },
            )
        else:
            st.info("아직 기록된 전문가 판정이 없습니다.")

    with st.expander("평가 지표 해석"):
        st.markdown(
            """
            - **Gold 실행 성공률**은 사람이 작성한 Gold Cypher의 실행 기준선입니다.
            - **런타임 성공률**은 현재 UI에서 실행한 질의의 `success + empty` 비율입니다.
            - **Blind 의미값 정확도**는 컬럼 별칭을 무시하고 승인된
              기대값을 모두 포함하는지 봅니다. 엄격 계약 일치율은
              비교표에서 별도로 표시합니다.
            - **자기수정 성공률**은 교정 노드를 실제 거친 질의만 분모로 사용합니다.
            """
        )

    st.markdown("#### Blind 비교 실험")
    blind_evaluation = snapshot.get("blind_evaluation")
    if blind_evaluation:
        comparison = pd.DataFrame(blind_evaluation["comparison"])
        display_columns = [
            "variant",
            "execution_success_rate",
            "result_accuracy",
            "strict_result_accuracy",
            "contract_variance_rate",
            "schema_compliance_rate",
            "read_only_compliance_rate",
            "empty_result_handling_rate",
            "correction_success_rate",
            "evidence_display_rate",
            "average_elapsed_ms",
            "model_call_count",
            "input_tokens",
            "output_tokens",
            "estimated_cost_usd",
        ]
        comparison_display = comparison.reindex(columns=display_columns)
        st.dataframe(
            comparison_display,
            width="stretch",
            hide_index=True,
            column_config={
                "execution_success_rate": st.column_config.NumberColumn(
                    format="percent"
                ),
                "result_accuracy": st.column_config.NumberColumn(
                    format="percent"
                ),
                "strict_result_accuracy": st.column_config.NumberColumn(
                    format="percent"
                ),
                "contract_variance_rate": st.column_config.NumberColumn(
                    format="percent"
                ),
                "schema_compliance_rate": st.column_config.NumberColumn(
                    format="percent"
                ),
                "read_only_compliance_rate": st.column_config.NumberColumn(
                    format="percent"
                ),
                "empty_result_handling_rate": st.column_config.NumberColumn(
                    format="percent"
                ),
                "correction_success_rate": st.column_config.NumberColumn(
                    format="percent"
                ),
                "evidence_display_rate": st.column_config.NumberColumn(
                    format="percent"
                ),
                "estimated_cost_usd": st.column_config.NumberColumn(
                    format="$%.4f"
                ),
            },
        )
        st.bar_chart(
            comparison,
            x="variant",
            y="result_accuracy",
            color="#2563EB",
        )
        st.caption(
            f"모델 · {blind_evaluation['provider']} / "
            f"{blind_evaluation['model']} · "
            f"질문 {blind_evaluation['question_count']}개 · "
            f"전체 추정비용 "
            f"${blind_evaluation['total_usage']['estimated_cost_usd']:.4f}"
        )
        st.caption(
            "result_accuracy는 컬럼 별칭을 무시한 의미값 일치율이고, "
            "strict_result_accuracy는 컬럼 이름·행·값이 모두 같은 "
            "출력 계약 일치율입니다."
        )
        correction_case_count = evaluation.get("correction_case_count", 0)
        if correction_case_count:
            st.markdown("##### 자기수정 스트레스 테스트")
            correction_columns = st.columns(4)
            correction_columns[0].metric(
                "오류 주입 케이스", correction_case_count
            )
            correction_columns[1].metric(
                "수정 후 검증 통과",
                f"{evaluation['correction_validation_success_rate']:.0%}",
            )
            correction_columns[2].metric(
                "의미값 회복",
                f"{evaluation['correction_result_accuracy']:.0%}",
            )
            correction_columns[3].metric(
                "엄격 계약 회복",
                f"{evaluation['correction_strict_result_accuracy']:.0%}",
            )
            st.caption(
                "문법·도메인 값·관계 토폴로지·필드 누락 오류를 의도적으로 "
                "주입해 실제 Gemini 교정 결과를 측정합니다."
            )
        status_evaluation = snapshot.get("status_evaluation")
        if status_evaluation:
            st.markdown("##### 상태 분류 혼동행렬")
            status_metrics = st.columns(2)
            status_metrics[0].metric(
                "상태 분류 정확도",
                f"{status_evaluation['accuracy']:.0%}",
            )
            status_metrics[1].metric(
                "Macro F1",
                f"{status_evaluation['macro_f1']:.0%}",
            )
            matrix_column, class_column = st.columns(2)
            with matrix_column:
                st.caption("행=기대 상태 · 열=실제 상태")
                st.dataframe(
                    pd.DataFrame(status_evaluation["matrix"]),
                    width="stretch",
                    hide_index=True,
                )
            with class_column:
                st.caption("상태별 Precision / Recall / F1")
                st.dataframe(
                    pd.DataFrame(status_evaluation["per_class"]),
                    width="stretch",
                    hide_index=True,
                    column_config={
                        "precision": st.column_config.NumberColumn(
                            format="percent"
                        ),
                        "recall": st.column_config.NumberColumn(
                            format="percent"
                        ),
                        "f1": st.column_config.NumberColumn(
                            format="percent"
                        ),
                    },
                )
    else:
        st.info(
            "Blind 26문항과 평가기는 준비됐습니다. 생성 모델 평가가 끝나면 "
            "Baseline → Few-shot → 자기수정 비교가 여기에 표시됩니다."
        )

    st.markdown("#### Agent 처리 흐름")
    st.graphviz_chart(
        """
        digraph Workflow {
          graph [rankdir="LR", bgcolor="transparent"];
          node [shape="box", style="rounded,filled", fillcolor="#EAF2F2",
                color="#0F766E", fontname="Arial"];
          question [label="자연어 질문"];
          generate [label="Cypher 생성"];
          validate [label="쓰기 차단 + 의미 검사 + EXPLAIN"];
          correct [label="자기수정"];
          execute [label="읽기 전용 실행"];
          evidence [label="답변 + 근거"];
          question -> generate -> validate;
          validate -> correct [label="오류"];
          correct -> validate;
          validate -> execute [label="통과"];
          execute -> evidence;
        }
        """,
        width="stretch",
    )
    if evaluation["blind_evaluation_status"] != "complete":
        st.info(
            "Blind 평가셋·정답 기준선·평가기 구현은 완료됐습니다. "
            "생성 모델 연결 후 실제 비교 점수가 확정됩니다."
        )

    render_metric_provenance(snapshot)


def render_evaluations_workspace(
    services: ServiceBundle,
    snapshot: dict[str, Any] | None = None,
) -> None:
    render_page_header("Evaluations")
    if snapshot is None:
        try:
            snapshot = services.dashboard.snapshot()
        except Exception as error:
            render_view_state(
                ViewState.ERROR,
                page="Evaluations",
                detail=f"평가 결과를 불러오지 못했습니다: {error}",
            )
            return
    runtime_filters = render_dashboard_scope_filters(
        snapshot, key_prefix="evaluations"
    )
    if any(runtime_filters.values()):
        try:
            snapshot = services.dashboard.snapshot(runtime_filters)
        except Exception as error:
            st.warning(f"필터 적용에 실패해 전체 범위를 표시합니다: {error}")
    snapshot = normalize_dashboard_snapshot(snapshot)
    evaluation = snapshot["evaluation"]
    blind = snapshot.get("blind_evaluation")
    status_evaluation = snapshot.get("status_evaluation")

    st.markdown("### 평가 릴리스 게이트")
    gate_columns = st.columns(6)
    gate_columns[0].metric(
        "Gold 실행",
        f"{evaluation['gold_execution_success_rate']:.0%}",
    )
    gate_columns[1].metric(
        "Blind 의미값",
        "미실행"
        if evaluation.get("blind_result_accuracy") is None
        else f"{evaluation['blind_result_accuracy']:.1%}",
    )
    gate_columns[2].metric(
        "엄격 계약",
        "미실행"
        if evaluation.get("blind_strict_result_accuracy") is None
        else f"{evaluation['blind_strict_result_accuracy']:.1%}",
    )
    gate_columns[3].metric(
        "Macro F1",
        "미실행"
        if evaluation.get("status_macro_f1") is None
        else f"{evaluation['status_macro_f1']:.1%}",
    )
    gate_columns[4].metric(
        "읽기 전용",
        f"{evaluation['read_only_compliance_rate']:.0%}",
    )
    gate_columns[5].metric(
        "테스트",
        f"{evaluation['unit_test_count']} PASS",
    )

    if not blind:
        render_view_state(
            ViewState.EMPTY,
            page="Evaluations",
            detail=(
                "이 프로젝트의 승인된 Gold·Blind 평가 결과가 없습니다. "
                "Pipeline에서 스키마와 기준셋을 승인한 뒤 평가를 실행하세요."
            ),
        )
        render_metric_provenance(snapshot)
        return

    comparison_rows = blind.get("comparison", [])
    comparison_tab, failures_tab, questions_tab, contract_tab = st.tabs(
        ["모델·프롬프트 비교", "실패 유형", "질문별 결과", "평가 계약"]
    )
    with comparison_tab:
        comparison = pd.DataFrame(comparison_rows)
        if not comparison.empty:
            visible_columns = [
                column
                for column in (
                    "variant",
                    "execution_success_rate",
                    "result_accuracy",
                    "strict_result_accuracy",
                    "schema_compliance_rate",
                    "read_only_compliance_rate",
                    "correction_success_rate",
                    "average_elapsed_ms",
                    "model_call_count",
                    "input_tokens",
                    "output_tokens",
                    "estimated_cost_usd",
                )
                if column in comparison.columns
            ]
            st.dataframe(
                comparison[visible_columns],
                width="stretch",
                hide_index=True,
            )
            chart_columns = st.columns(2)
            with chart_columns[0]:
                st.caption("Baseline → Few-shot → Self-correction 정확도")
                st.bar_chart(
                    comparison,
                    x="variant",
                    y="result_accuracy",
                    color="#2563EB",
                )
            with chart_columns[1]:
                st.caption("평균 지연시간")
                st.bar_chart(
                    comparison,
                    x="variant",
                    y="average_elapsed_ms",
                    color="#D97706",
                )
        st.caption(
            f"{blind.get('provider', 'unknown')} / "
            f"{blind.get('model', 'unknown')} · "
            f"prompt {blind.get('prompt_version', 'unknown')} · "
            f"{blind.get('question_count', 0)}문항"
        )
    with failures_tab:
        failure_rows = []
        for row in comparison_rows:
            for failure, count in (row.get("failure_counts") or {}).items():
                failure_rows.append(
                    {
                        "variant": row.get("variant"),
                        "failure_type": failure,
                        "count": count,
                    }
                )
        if failure_rows:
            failure_frame = pd.DataFrame(failure_rows)
            st.bar_chart(
                failure_frame,
                x="failure_type",
                y="count",
                color="variant",
            )
            st.dataframe(
                failure_frame, width="stretch", hide_index=True
            )
        else:
            st.success("기록된 실패 유형이 없습니다.")
        if status_evaluation:
            st.markdown("#### 상태 분류 혼동행렬")
            matrix_column, class_column = st.columns(2)
            matrix_column.dataframe(
                pd.DataFrame(status_evaluation["matrix"]),
                width="stretch",
                hide_index=True,
            )
            class_column.dataframe(
                pd.DataFrame(status_evaluation["per_class"]),
                width="stretch",
                hide_index=True,
            )
    with questions_tab:
        variants = blind.get("variants") or {}
        variant_names = list(variants)
        selected_variant = st.selectbox(
            "평가 조건",
            variant_names,
            index=max(0, len(variant_names) - 1),
            key="evaluation-question-variant",
        )
        questions = (
            variants.get(selected_variant, {}).get("questions", [])
            if selected_variant
            else []
        )
        outcome = st.multiselect(
            "결과 필터",
            sorted(
                {
                    str(question.get("outcome", "unknown"))
                    for question in questions
                }
            ),
            placeholder="전체 결과",
            key="evaluation-outcome-filter",
        )
        filtered_questions = [
            question
            for question in questions
            if not outcome
            or str(question.get("outcome", "unknown")) in outcome
        ]
        st.dataframe(
            pd.DataFrame(flatten_rows_for_table(filtered_questions)),
            width="stretch",
            hide_index=True,
        )
    with contract_tab:
        contract_rows = [
            {
                "contract": "Project scope",
                "value": snapshot.get("provenance", {}).get(
                    "graph_project_id"
                ),
            },
            {"contract": "Schema", "value": evaluation["schema_version"]},
            {
                "contract": "Evaluation",
                "value": evaluation.get("evaluation_version"),
            },
            {
                "contract": "Prompt",
                "value": evaluation.get("prompt_version"),
            },
            {
                "contract": "Evaluation fingerprint",
                "value": evaluation.get("evaluation_fingerprint"),
            },
        ]
        st.dataframe(
            pd.DataFrame(contract_rows), width="stretch", hide_index=True
        )
        st.download_button(
            "평가 증적 JSON 다운로드",
            data=json.dumps(blind, ensure_ascii=False, indent=2),
            file_name=(
                f"{st.session_state.get('active_project_id', 'project')}"
                "-evaluation-evidence.json"
            ),
            mime="application/json",
        )
    render_metric_provenance(snapshot)


def render_audit_workspace() -> None:
    render_page_header("Audit Logs")
    project_id = st.session_state.get("active_project_id", "cip-dmd")
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
                    disabled=not bool(rerun_question),
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
                    disabled=not bool(detail.get("question")),
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


def _switch_project(project_id: str) -> None:
    previous = st.session_state.get("active_project_id", "cip-dmd")
    if previous == project_id:
        return
    sync_active_conversation()
    st.session_state["project_conversations"][
        previous
    ] = snapshot_project_context(st.session_state)
    if project_id not in st.session_state["conversation_loaded_projects"]:
        persisted = get_conversation_store().list(project_id, limit=12)
        context = None
        if persisted:
            context = {
                "conversations": persisted,
                "active_conversation_id": persisted[0]["id"],
                "messages": persisted[0]["messages"],
                "last_result": persisted[0].get("last_result"),
            }
        st.session_state["project_conversations"][project_id] = context
        st.session_state["conversation_loaded_projects"].add(project_id)
    restore_project_context(
        st.session_state,
        st.session_state["project_conversations"].get(project_id),
    )
    st.session_state["active_project_id"] = project_id
    ProjectRegistry(
        PROJECT_ROOT / "data" / "processed" / "projects.sqlite3"
    ).activate(project_id)
    get_services.clear()


def render_sidebar() -> tuple[str, str, str, str]:
    st.sidebar.markdown("### Workspace")
    role_value = st.sidebar.selectbox(
        "역할 미리보기",
        options=tuple(role.value for role in Role),
        key="preview_role",
        help=(
            "2-1 UI 권한 설계를 검증하는 프로토타입입니다. "
            "실제 사용자 인증·SSO는 Admin 단계에서 연결합니다."
        ),
    )
    role = Role(role_value)
    allowed_items = navigation_for_role(role)
    allowed_pages = tuple(item.label for item in allowed_items)
    if st.session_state.get("active_page") not in allowed_pages:
        st.session_state["active_page"] = "Home"
    page = st.sidebar.radio(
        "Navigation",
        options=allowed_pages,
        key="active_page",
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
    st.sidebar.caption(
        f"{role.value} 권한 · {len(allowed_pages)}개 작업공간"
    )
    st.sidebar.divider()
    if page == "Home":
        st.sidebar.markdown("### FactoryGraph RCA")
        st.sidebar.caption(
            "자연어 질문 → 검증된 Cypher → Neo4j 근거 → 전문가 판정"
        )
        st.sidebar.success("제품 랜딩")
        return (
            page,
            "auto",
            os.getenv("GOOGLE_VERTEX_MODEL", "gemini-2.5-flash"),
            st.session_state.get("active_project_id", "cip-dmd"),
        )

    registry = ProjectRegistry(
        PROJECT_ROOT / "data" / "processed" / "projects.sqlite3"
    )
    registry.ensure_default()
    project_rows = registry.list()
    project_ids = [row["project_id"] for row in project_rows]
    active_project_id = st.session_state.get(
        "active_project_id", registry.active_project_id() or "cip-dmd"
    )
    if active_project_id not in project_ids:
        active_project_id = project_ids[0]
    st.sidebar.markdown("### 프로젝트")
    selected_project_id = st.sidebar.selectbox(
        "활성 워크스페이스",
        project_ids,
        index=project_ids.index(active_project_id),
        format_func=lambda value: next(
            row["name"] for row in project_rows if row["project_id"] == value
        ),
    )
    _switch_project(selected_project_id)
    if role in {Role.DATA_STEWARD, Role.ADMIN}:
        if st.sidebar.button(
            "＋ 프로젝트 만들기",
            key="sidebar-create-project",
            width="stretch",
        ):
            navigate_to_page("Projects")
            st.rerun()
    st.sidebar.divider()
    st.sidebar.markdown("### 대화")
    if st.sidebar.button(
        "＋ 새 대화",
        type="primary",
        width="stretch",
    ):
        start_new_conversation()
        st.rerun()
    conversations = st.session_state["conversations"]
    if conversations:
        st.sidebar.caption(
            "프로젝트에 저장된 최근 대화 · 최대 12개"
        )
        history_search = st.sidebar.text_input(
            "대화 검색",
            placeholder="질문 제목 또는 내용",
            key=f"conversation-search-{selected_project_id}",
        )
        visible_conversations = (
            get_conversation_store().list(
                selected_project_id,
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
                st.rerun()
        if st.sidebar.button(
            "프로젝트 대화 모두 지우기",
            key="clear-all-conversations",
            width="stretch",
        ):
            get_conversation_store().delete_project(selected_project_id)
            st.session_state["conversations"] = []
            st.session_state["active_conversation_id"] = str(uuid4())
            st.session_state["messages"] = []
            st.session_state["last_result"] = None
            st.rerun()
    else:
        st.sidebar.caption("질문을 실행하면 최근 대화가 여기에 표시됩니다.")

    st.sidebar.divider()
    st.sidebar.markdown("### 실행 설정")
    if role in {Role.DATA_STEWARD, Role.ADMIN}:
        provider = st.sidebar.selectbox(
            "생성 모드",
            options=("auto", "gemini", "gold", "openai"),
            format_func=lambda value: (
                {
                    "auto": "자동 · OpenAI 없으면 Gemini",
                    "gemini": "Vertex Gemini · 자유 질문",
                    "gold": "Gold 데모 · 회귀검증 전용",
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
                "추천 질문과 Gold 15개만 정확히 실행하는 회귀검증 모드입니다."
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

    st.sidebar.divider()
    st.sidebar.markdown("### 안전 설정")
    st.sidebar.success("Neo4j reader mode")
    st.sidebar.caption(
        "쓰기 의도 차단 · Cypher 검사 · EXPLAIN · DB read-only"
    )
    return page, provider, model_name, selected_project_id


def render_schema_studio() -> None:
    render_page_header("Pipeline")
    st.caption(
        "프로파일 → 매핑 dry-run → 명시적 승인 → 격리 적재 → "
        "무결성 검증 순서로 진행합니다."
    )
    projects = ProjectRegistry(
        PROJECT_ROOT / "data" / "processed" / "projects.sqlite3"
    )
    project_rows = projects.list()
    project_ids = [row["project_id"] for row in project_rows]
    active_project = st.session_state.get("active_project_id", "cip-dmd")
    project_id = st.selectbox(
        "프로젝트",
        project_ids,
        index=project_ids.index(active_project)
        if active_project in project_ids
        else 0,
    )
    project = projects.require(project_id)
    render_onboarding_stage(project)
    render_pipeline_jobs(project_id)
    if project["source_type"] == "neo4j":
        st.info(
            "이 프로젝트는 기존 Neo4j 연결형입니다. Data Sources에서 "
            "연결 검증·승인을 완료하면 스키마가 자동 등록됩니다."
        )
        return
    datasets = DatasetWorkspace(
        PROJECT_ROOT / "data" / "processed" / "project_uploads"
    )
    uploads = datasets.list(project_id)
    if not uploads:
        st.info("먼저 Data Sources에서 데이터셋을 업로드해 프로파일링하세요.")
        return
    upload = uploads[0]
    upload_id = st.selectbox(
        "프로파일", [row["upload_id"] for row in uploads]
    )
    upload = next(row for row in uploads if row["upload_id"] == upload_id)
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "file": file["filename"],
                    "rows": file["row_count"],
                    "columns": file["column_count"],
                }
                for file in upload["files"]
            ]
        ),
        width="stretch",
        hide_index=True,
    )
    source = upload["files"][0]
    identity = next(
        (
            column["name"]
            for column in source["columns"]
            if column["identity_candidate"]
        ),
        source["columns"][0]["name"],
    )
    template = {
        "title": f"{project_id} graph",
        "nodes": [
            {
                "label": "Record",
                "source_file": source["filename"],
                "identity": identity,
                "properties": {
                    column["name"]: column["name"]
                    for column in source["columns"]
                },
            }
        ],
        "relationships": [],
    }
    mapping_text = st.text_area(
        "Graph mapping (JSON)",
        value=json.dumps(template, ensure_ascii=False, indent=2),
        height=360,
        help=(
            "노드의 identity와 속성, 관계의 시작·끝 키를 정의합니다. "
            "승인 전 dry-run은 운영 Neo4j를 변경하지 않습니다."
        ),
    )
    schemas = SchemaRegistry(PROJECT_ROOT / "schemas")
    mappings = MappingWorkspace(
        PROJECT_ROOT / "data" / "processed" / "project_mappings",
        datasets,
        schemas,
    )
    preview_column, approve_column = st.columns(2)
    try:
        mapping = json.loads(mapping_text)
        if preview_column.button(
            "1 · ETL dry-run",
            width="stretch",
            key=f"mapping-preview-{project_id}-{upload_id}",
        ):
            store = get_pipeline_job_store()
            job = store.create(
                project_id,
                "mapping_dry_run",
                message="매핑 검증과 ETL dry-run 대기",
            )
            try:
                store.start(
                    job["job_id"],
                    "mapping_validation",
                    "컬럼·identity·관계 키를 검증합니다.",
                )
                api = FactoryGraphApiClient()
                try:
                    if api.live():
                        preview = api.preview_mapping(
                            project_id,
                            upload_id=upload_id,
                            schema_version="1.0",
                            mapping=mapping,
                        )
                    else:
                        preview = mappings.preview(
                            project_id,
                            upload_id,
                            mapping,
                            schema_version="1.0",
                        )
                finally:
                    api.close()
                dry_run = preview.get("dry_run", {})
                total_rows = sum(
                    int(value)
                    for value in preview.get(
                        "estimated_node_rows", {}
                    ).values()
                ) + sum(
                    int(value)
                    for value in preview.get(
                        "estimated_relationship_rows", {}
                    ).values()
                )
                store.update(
                    job["job_id"],
                    current_step="dry_run",
                    progress=80,
                    processed_rows=total_rows,
                    total_rows=total_rows,
                    message=(
                        "노드·관계 투영과 격리 레코드 검사를 완료했습니다."
                    ),
                )
                store.succeed(
                    job["job_id"],
                    step="dry_run_complete",
                    message=(
                        f"ETL dry-run {dry_run.get('status', 'PASS')} · "
                        "운영 그래프 변경 없음"
                    ),
                    result={
                        "upload_id": upload_id,
                        "dry_run": dry_run,
                    },
                    processed_rows=total_rows,
                    total_rows=total_rows,
                )
                st.session_state["mapping_preview"] = preview
                st.success(
                    "ETL dry-run을 마쳤습니다. 운영 Neo4j는 변경되지 않았습니다."
                )
            except Exception as error:
                store.fail(
                    job["job_id"], step="mapping_validation", error=str(error)
                )
                st.error(f"매핑 dry-run 실패: {error}")
        preview = st.session_state.get("mapping_preview")
        preview_matches = bool(
            preview
            and preview.get("project_id") == project_id
            and preview.get("upload_id") == upload_id
        )
        if approve_column.button(
            "2 · 검토한 매핑 승인",
            type="primary",
            width="stretch",
            disabled=not preview_matches,
            key=f"mapping-approve-{project_id}-{upload_id}",
        ):
            store = get_pipeline_job_store()
            job = store.create(
                project_id,
                "mapping_approval",
                message="매핑 승인 대기",
            )
            try:
                store.start(
                    job["job_id"],
                    "approval",
                    "검토한 매핑과 스키마 버전을 고정합니다.",
                )
                api = FactoryGraphApiClient()
                try:
                    if api.live():
                        approved = api.approve_mapping(
                            project_id,
                            upload_id=upload_id,
                            schema_version="1.0",
                            mapping=mapping,
                        )
                    else:
                        approved = mappings.approve(
                            project_id,
                            upload_id,
                            mapping,
                            schema_version="1.0",
                        )
                        projects.update(project_id, schema_version="1.0")
                        projects.record_artifact(
                            project_id,
                            "mapping",
                            version="1.0",
                            metadata={"upload_id": upload_id},
                        )
                        projects.record_artifact(
                            project_id,
                            "schema",
                            version="1.0",
                            metadata={"source_version": upload_id},
                        )
                finally:
                    api.close()
                store.succeed(
                    job["job_id"],
                    step="approved",
                    message="매핑·스키마 승인본을 저장했습니다.",
                    result={"upload_id": upload_id, "schema_version": "1.0"},
                )
                st.session_state["mapping_preview"] = approved
                st.success(
                    "매핑과 schema manifest를 승인했습니다. "
                    "아직 운영 그래프에는 적재하지 않았습니다."
                )
            except Exception as error:
                store.fail(job["job_id"], step="approval", error=str(error))
                st.error(f"매핑 승인 실패: {error}")
    except (ValueError, KeyError, json.JSONDecodeError) as error:
        st.error(f"매핑을 검증할 수 없습니다: {error}")
    preview = st.session_state.get("mapping_preview")
    if (
        preview
        and preview.get("project_id") == project_id
        and preview.get("upload_id") == upload_id
    ):
        st.markdown("### Dry-run 결과")
        dry_run = preview.get("dry_run", {})
        dry_metrics = st.columns(4)
        dry_metrics[0].metric("판정", dry_run.get("status", "—"))
        dry_metrics[1].metric(
            "예상 노드",
            f"{sum(preview.get('estimated_node_rows', {}).values()):,}",
        )
        dry_metrics[2].metric(
            "예상 관계",
            f"{sum(preview.get('estimated_relationship_rows', {}).values()):,}",
        )
        dry_metrics[3].metric(
            "격리 후보",
            f"{int(dry_run.get('isolation_count', 0)):,}",
        )
        dry_tabs = st.tabs(["노드", "관계", "격리·Lineage", "Schema"])
        with dry_tabs[0]:
            st.dataframe(
                pd.DataFrame(
                    [
                        {"label": label, **values}
                        for label, values in dry_run.get("nodes", {}).items()
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
        with dry_tabs[1]:
            st.dataframe(
                pd.DataFrame(
                    [
                        {"type": relation_type, **values}
                        for relation_type, values in dry_run.get(
                            "relationships", {}
                        ).items()
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
        with dry_tabs[2]:
            if dry_run.get("isolation_examples"):
                st.dataframe(
                    pd.DataFrame(dry_run["isolation_examples"]),
                    width="stretch",
                    hide_index=True,
                )
            else:
                st.success("격리해야 할 레코드가 없습니다.")
            st.json(dry_run.get("lineage", {}))
        with dry_tabs[3]:
            st.json(preview["manifest"])
        st.caption(
            f"예상 노드 입력: {preview['estimated_node_rows']} · "
            f"예상 관계 입력: {preview['estimated_relationship_rows']}"
        )
        approved_mapping = None
        try:
            candidate = mappings.get(project_id)
            if candidate.get("upload_id") == upload_id:
                approved_mapping = candidate
        except KeyError:
            pass
        if approved_mapping:
            st.markdown("### Neo4j 적재 승인")
            st.warning(
                "승인된 매핑을 현재 프로젝트 범위로 실제 적재합니다. "
                "다른 프로젝트의 노드·관계는 변경하지 않습니다."
            )
            confirmation = st.text_input(
                f"확인을 위해 `{project_id}` 입력",
                key=f"mapping-load-confirm-{project_id}",
            )
            load_enabled = os.getenv("P3_ENABLE_UI_LOAD") == "1"
            if not load_enabled:
                st.info("관리자가 P3_ENABLE_UI_LOAD=1로 실행해야 활성화됩니다.")
            if st.button(
                "승인된 그래프 적재",
                type="primary",
                disabled=(
                    not load_enabled or confirmation != project_id
                ),
                key=f"mapping-load-{project_id}",
            ):
                store = get_pipeline_job_store()
                total_rows = sum(
                    int(value)
                    for value in preview.get(
                        "estimated_node_rows", {}
                    ).values()
                ) + sum(
                    int(value)
                    for value in preview.get(
                        "estimated_relationship_rows", {}
                    ).values()
                )
                job = store.create(
                    project_id,
                    "graph_load",
                    message="승인된 그래프 적재 대기",
                    total_rows=total_rows,
                )
                api = FactoryGraphApiClient()
                try:
                    store.start(
                        job["job_id"],
                        "load",
                        "프로젝트 격리 범위로 노드·관계를 적재합니다.",
                    )
                    result = api.load_project_graph(project_id, upload_id)
                    store.update(
                        job["job_id"],
                        current_step="integrity",
                        progress=90,
                        processed_rows=total_rows,
                        total_rows=total_rows,
                        message=(
                            "원본·적재 건수, 고아 관계, 프로젝트 범위를 검증합니다."
                        ),
                    )
                    store.succeed(
                        job["job_id"],
                        step="integrity_complete",
                        message="적재와 무결성 gate를 통과했습니다.",
                        result=result,
                        processed_rows=total_rows,
                        total_rows=total_rows,
                    )
                    st.session_state["project_load_result"] = result
                    st.success("프로젝트 격리 적재와 무결성 확인을 완료했습니다.")
                except Exception as error:
                    store.fail(job["job_id"], step="load", error=str(error))
                    st.error(f"그래프 적재 실패: {error}")
                finally:
                    api.close()
    if st.session_state.get("project_load_result"):
        result = st.session_state["project_load_result"]
        st.markdown("### 무결성·Readiness")
        integrity = result.get("integrity", {})
        metrics = st.columns(4)
        metrics[0].metric(
            "프로젝트 범위",
            "PASS" if integrity.get("project_scope_applied") else "FAIL",
        )
        metrics[1].metric(
            "적재 노드", f"{int(integrity.get('scoped_node_count', 0)):,}"
        )
        metrics[2].metric(
            "교차 프로젝트 관계",
            f"{int(integrity.get('cross_project_relationship_count', 0)):,}",
        )
        metrics[3].metric(
            "Reader 복구",
            "PASS" if result.get("reader_mode_restored", True) else "확인 필요",
        )
        api = FactoryGraphApiClient()
        try:
            if api.live():
                readiness = api.project_readiness(project_id)
                st.dataframe(
                    pd.DataFrame(
                        [
                            {"gate": name, **check}
                            for name, check in readiness.get(
                                "checks", {}
                            ).items()
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )
                if readiness.get("ready"):
                    st.success("이 프로젝트는 자유 질의 준비가 완료됐습니다.")
                else:
                    st.info(
                        "무결성 검증은 통과했습니다. Gold/Blind 평가와 "
                        "prompt 승인이 완료되면 Query Studio가 열립니다."
                    )
        finally:
            api.close()


def main() -> None:
    initialize_session()
    page, provider, model_name, project_id = render_sidebar()
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
        render_startup_failure(error)
        return
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
