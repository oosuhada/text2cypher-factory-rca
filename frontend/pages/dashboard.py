"""Project-scoped operational and quality dashboard."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pandas as pd
import streamlit as st

from frontend.app_services import ServiceBundle
from frontend.dashboard_plotly import (
    build_anomaly_runs_figure,
    build_blind_comparison_figure,
    build_equipment_runs_figure,
    build_node_counts_figure,
    build_provider_counts_figure,
    build_quality_failures_figure,
    build_recent_latency_figure,
    build_relationship_counts_figure,
    build_status_counts_figure,
)

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
            st.plotly_chart(
                build_node_counts_figure(snapshot["node_counts"]),
                width="stretch",
                key="dashboard-node-counts",
            )
        with right:
            st.markdown("##### 관계 유형")
            st.plotly_chart(
                build_relationship_counts_figure(snapshot["relationship_counts"]),
                width="stretch",
                key="dashboard-relationship-counts",
            )
    with process_tab:
        left, right = st.columns(2)
        with left:
            st.markdown("##### 장비별 공정 실행")
            if snapshot["equipment_runs"]:
                st.plotly_chart(
                    build_equipment_runs_figure(snapshot["equipment_runs"]),
                    width="stretch",
                    key="dashboard-equipment-runs",
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
                st.plotly_chart(
                    build_anomaly_runs_figure(snapshot["anomaly_runs"]),
                    width="stretch",
                    key="dashboard-anomaly-runs",
                )
            else:
                st.info("이 스키마에는 이상 유형 집계가 정의되지 않았습니다.")
        with right:
            st.markdown("##### 품질 불합격 상위 항목")
            if snapshot["quality_failures"]:
                st.plotly_chart(
                    build_quality_failures_figure(snapshot["quality_failures"]),
                    width="stretch",
                    key="dashboard-quality-failures",
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
            st.plotly_chart(
                build_status_counts_figure(runtime["status_counts"]),
                width="stretch",
                key="dashboard-runtime-status",
            )
        else:
            st.info("아직 기록된 질의가 없습니다.")
        if runtime["provider_counts"]:
            st.plotly_chart(
                build_provider_counts_figure(runtime["provider_counts"]),
                width="stretch",
                key="dashboard-runtime-provider",
            )
    with recent_column:
        st.markdown("##### 최근 질의")
        if runtime["recent_queries"]:
            recent_queries = pd.DataFrame(runtime["recent_queries"])
            st.dataframe(
                recent_queries,
                width="stretch",
                hide_index=True,
                column_config={
                    "question": st.column_config.TextColumn(width="large"),
                    "elapsed_ms": st.column_config.NumberColumn(
                        "elapsed_ms", format="%d ms"
                    ),
                },
            )
            if "elapsed_ms" in recent_queries:
                st.plotly_chart(
                    build_recent_latency_figure(runtime["recent_queries"]),
                    width="stretch",
                    key="dashboard-recent-latency",
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
        st.plotly_chart(
            build_blind_comparison_figure(comparison),
            width="stretch",
            key="dashboard-blind-comparison",
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


if __name__ == "__main__":
    from frontend.legacy_page_redirect import redirect_legacy_page

    redirect_legacy_page("dashboard")
