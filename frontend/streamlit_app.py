"""P3 manufacturing knowledge-graph RCA Streamlit application."""

from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Any
from copy import deepcopy
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import streamlit as st

from backend.app.services.diagnostics import collect_demo_diagnostics
from backend.app.services.graph_service import NODE_IDENTITIES
from frontend.app_services import ServiceBundle, build_service_bundle
from frontend.conversation_history import upsert_conversation
from frontend.data_preflight import inspect_uploaded_source
from frontend.presentation import (
    evidence_to_dot,
    filter_evidence,
    flatten_rows_for_table,
    normalize_catalog_evidence,
    rows_to_csv,
)


APP_TITLE = "Factory Graph RCA"
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
    @media (max-width: 900px) {
      .p3-feature-grid {grid-template-columns: repeat(2, minmax(0, 1fr));}
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner=False)
def get_services(provider: str, model_name: str) -> ServiceBundle:
    return build_service_bundle(
        project_root=PROJECT_ROOT,
        provider=provider,
        model_name=model_name,
    )


def initialize_session() -> None:
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("last_result", None)
    st.session_state.setdefault("conversations", [])
    st.session_state.setdefault(
        "active_conversation_id", str(uuid4())
    )
    st.session_state.setdefault("explorer_result", None)


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
    status_label = {
        "success": "조회 완료",
        "empty": "결과 없음",
        "blocked": "요청 차단",
        "failed": "처리 실패",
        "needs_clarification": "조건 확인 필요",
        "unsupported": "데모 범위 밖",
    }.get(status, status)
    st.markdown(
        f'<span class="p3-status">{status_label}</span>',
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
    if response.get("status") not in {"success", "empty"}:
        return
    with st.expander(
        "근거 바로 보기 · 결과표 / Cypher / 관계 경로",
        expanded=expanded and response.get("status") == "success",
    ):
        result_tab, graph_tab, cypher_tab, trace_tab = st.tabs(
            ["조회 결과", "관계 경로", "Cypher", "검증 이력"]
        )
        with result_tab:
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
                st.info("정상 실행됐지만 일치하는 데이터가 없습니다.")
        with graph_tab:
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
                    "집계 질의이거나 경로 ID가 없어 그래프를 임의 생성하지 "
                    "않습니다."
                )
        with cypher_tab:
            st.markdown("##### 생성·검증된 Cypher")
            if response.get("cypher"):
                st.code(response["cypher"], language="cypher")
            else:
                st.info("실행된 Cypher가 없습니다.")
        with trace_tab:
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
                st.caption("별도의 교정 없이 검증을 통과했습니다.")


def render_chat_history() -> None:
    messages = st.session_state["messages"]
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


def submit_question(question: str, services: ServiceBundle) -> None:
    st.session_state["messages"].append(
        {"role": "user", "content": question}
    )
    try:
        with st.spinner("스키마 확인 → Cypher 생성 → 안전성 검증 → 실행"):
            response = services.query_with_fallback(question)
    except Exception as error:
        response = failure_response(question, error)
    st.session_state["messages"].append(
        {"role": "assistant", "content": response}
    )
    st.session_state["last_result"] = response
    sync_active_conversation()


def render_chat_tab(services: ServiceBundle) -> None:
    st.subheader("제조 관계를 자연어로 조회")
    st.caption(
        "답변과 함께 생성된 Cypher, 결과표, 근거 경로를 확인할 수 있습니다."
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
    render_chat_history()
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
    question = typed_question or selected_question
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


def render_graph_explorer(services: ServiceBundle) -> None:
    st.subheader("지식그래프 탐색")
    st.caption(
        "노드의 실제 ID를 기준으로 최대 3-hop 관계를 읽기 전용으로 "
        "탐색합니다."
    )
    if services.graph is None:
        st.error("그래프 탐색 서비스가 구성되지 않았습니다.")
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
    with st.form("graph-explorer-form"):
        label_column, identity_column, depth_column = st.columns([1, 1.5, 1])
        with label_column:
            label = st.selectbox(
                "노드 유형",
                options=tuple(NODE_IDENTITIES),
                index=1,
                format_func=lambda value: label_names.get(value, value),
            )
        with identity_column:
            identity = st.text_input(
                f"식별값 · {NODE_IDENTITIES[label]}",
                value="300002" if label == "Cylinder" else "",
                placeholder="예: 300002",
            )
        with depth_column:
            depth = st.slider("탐색 깊이", 1, 3, 2)
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
                        depth=depth,
                        limit=70,
                    )
                st.session_state["explorer_result"] = {
                    "label": label,
                    "identity": identity.strip(),
                    "depth": depth,
                    "payload": payload,
                }
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
    if payload.get("root") is None:
        st.info(
            f"{explorer_result['label']} "
            f"'{explorer_result['identity']}'에 해당하는 노드가 없습니다."
        )
        return

    evidence = normalize_catalog_evidence(payload)
    node_metric, relation_metric, depth_metric = st.columns(3)
    node_metric.metric("표시 노드", evidence["node_count"])
    relation_metric.metric("표시 관계", evidence["relationship_count"])
    depth_metric.metric("탐색 깊이", explorer_result["depth"])
    st.graphviz_chart(evidence_to_dot(evidence), width="stretch")
    if evidence.get("truncated"):
        st.info("가독성을 위해 최대 70개 경로까지만 표시합니다.")
    node_tab, relationship_tab = st.tabs(["노드 상세", "관계 상세"])
    with node_tab:
        st.dataframe(
            pd.DataFrame(flatten_rows_for_table(evidence["nodes"])),
            width="stretch",
            hide_index=True,
        )
    with relationship_tab:
        if evidence["relationships"]:
            st.dataframe(
                pd.DataFrame(
                    flatten_rows_for_table(evidence["relationships"])
                ),
                width="stretch",
                hide_index=True,
            )
        else:
            st.info("선택한 깊이에서 연결 관계를 찾지 못했습니다.")


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


def render_data_health_tab(
    services: ServiceBundle, snapshot: dict[str, Any] | None
) -> None:
    st.subheader("데이터 적재와 실행 진단")
    st.caption(
        "운영 그래프는 읽기 전용으로 유지하고, 업로드 파일은 메모리에서 "
        f"스키마만 사전검증합니다. 현재 질의 provider: {services.provider}"
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

    st.markdown("#### 업로드 파일 사전검증")
    uploaded_files = st.file_uploader(
        "CiP-DMD 메타데이터 JSON 또는 품질 CSV (10MB 이하)",
        type=("json", "csv"),
        accept_multiple_files=True,
        help=(
            "여기서는 구조와 공통 ID만 확인합니다. 검증되지 않은 파일을 "
            "Neo4j에 자동 적재하지 않습니다."
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
        if all(item["status"] == "PASS" for item in inspections):
            st.success(
                "모든 파일에서 CiP-DMD 공통 ID 후보를 확인했습니다. "
                "운영 적재 전 ETL dry-run을 수행하세요."
            )
        else:
            st.warning("일부 파일은 매핑 검토 또는 형식 수정이 필요합니다.")
    st.code(
        ".venv/bin/python -m backend.app.etl.cli --dry-run\n"
        "# PASS 후에만 loader 모드에서 적재하고 즉시 reader로 복귀",
        language="bash",
    )


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


def render_dashboard_tab(
    services: ServiceBundle, snapshot: dict[str, Any] | None = None
) -> None:
    st.subheader("그래프와 평가 현황")
    st.caption("화면의 수치는 현재 Neo4j와 검증 결과 파일에서 조회합니다.")
    if snapshot is None:
        try:
            snapshot = services.dashboard.snapshot()
        except Exception as error:
            st.error(f"대시보드 데이터를 불러오지 못했습니다: {error}")
            return

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
            st.bar_chart(
                pd.DataFrame(snapshot["equipment_runs"]),
                x="equipment",
                y="run_count",
                color="#7C3AED",
                horizontal=True,
            )
        with right:
            st.markdown("##### 장비 상세")
            st.dataframe(
                pd.DataFrame(snapshot["equipment_runs"]),
                width="stretch",
                hide_index=True,
            )
    with quality_tab:
        left, right = st.columns(2)
        with left:
            st.markdown("##### 이상 유형 분포")
            st.bar_chart(
                pd.DataFrame(snapshot["anomaly_runs"]),
                x="anomaly_code",
                y="run_count",
                color="#DC2626",
            )
        with right:
            st.markdown("##### 품질 불합격 상위 항목")
            st.bar_chart(
                pd.DataFrame(snapshot["quality_failures"]),
                x="feature",
                y="failure_count",
                color="#D97706",
                horizontal=True,
            )

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


def render_sidebar() -> tuple[str, str]:
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
            "현재 브라우저 세션의 최근 대화 · 최대 12개"
        )
        for conversation in conversations[:6]:
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
            "세션 기록 모두 지우기",
            key="clear-all-conversations",
            width="stretch",
        ):
            st.session_state["conversations"] = []
            st.session_state["active_conversation_id"] = str(uuid4())
            st.session_state["messages"] = []
            st.session_state["last_result"] = None
            st.rerun()
    else:
        st.sidebar.caption("질문을 실행하면 최근 대화가 여기에 표시됩니다.")

    st.sidebar.divider()
    st.sidebar.markdown("### 실행 설정")
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

    st.sidebar.divider()
    st.sidebar.markdown("### 안전 설정")
    st.sidebar.success("Neo4j reader mode")
    st.sidebar.caption(
        "쓰기 의도 차단 · Cypher 검사 · EXPLAIN · DB read-only"
    )
    return provider, model_name


def main() -> None:
    initialize_session()
    provider, model_name = render_sidebar()
    st.markdown(
        """
        <div class="p3-hero">
          <div class="p3-kicker">Manufacturing Knowledge Graph</div>
          <h1>Factory Graph RCA</h1>
          <p>완제품 · 구성품 · 공정 · 장비 · 이상 · 품질을 연결해
          검증 가능한 RCA 후보를 탐색합니다.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    try:
        services = get_services(provider, model_name)
    except Exception as error:
        render_startup_failure(error)
        return
    st.sidebar.caption(
        f"실제 연결: {services.provider} / {services.model_name}"
    )
    try:
        dashboard_snapshot = services.dashboard.snapshot()
    except Exception as error:
        dashboard_snapshot = None
        st.warning(f"대시보드 진단 일부를 불러오지 못했습니다: {error}")

    render_landing_overview()
    chat_tab, evidence_tab, explorer_tab, dashboard_tab, data_tab = st.tabs(
        [
            "Query Studio",
            "Evidence Lab",
            "Graph Explorer",
            "Operations",
            "Data & Health",
        ]
    )
    with chat_tab:
        render_chat_tab(services)
    with evidence_tab:
        render_evidence_tab()
    with explorer_tab:
        render_graph_explorer(services)
    with dashboard_tab:
        render_dashboard_tab(services, dashboard_snapshot)
    with data_tab:
        render_data_health_tab(services, dashboard_snapshot)


if __name__ == "__main__":
    main()
