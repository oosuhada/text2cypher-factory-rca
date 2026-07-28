"""Shared Streamlit view states and recoverable error presentation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import pandas as pd
import streamlit as st

from backend.app.services.diagnostics import collect_demo_diagnostics
from frontend.design_system import (
    PAGE_BY_LABEL,
    ViewState,
    state_copy,
)
from frontend.navigation import render_page_header


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


def render_startup_failure(
    error: Exception,
    *,
    project_root: Path,
    clear_services: Callable[[], None],
) -> None:
    st.error(
        f"서비스 연결 준비가 완료되지 않았습니다: {error}",
        icon="🩺",
    )
    st.code(str(error))
    checks = collect_demo_diagnostics(project_root)
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
        clear_services()
        st.rerun()

