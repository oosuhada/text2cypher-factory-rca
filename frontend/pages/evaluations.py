"""Gold, Blind and runtime evaluation workspace."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
import streamlit as st

from frontend.app_services import ServiceBundle
from frontend.common_ui import render_view_state
from frontend.design_system import ViewState
from frontend.navigation import render_page_header
from frontend.pages.dashboard import (
    normalize_dashboard_snapshot,
    render_dashboard_scope_filters,
    render_metric_provenance,
)
from frontend.presentation import flatten_rows_for_table

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


if __name__ == "__main__":
    from frontend.legacy_page_redirect import redirect_legacy_page

    redirect_legacy_page("evaluations")
