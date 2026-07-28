#!/usr/bin/env python3
"""Cross-surface architecture and critical UX release contracts."""

from __future__ import annotations

import ast
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = PROJECT_ROOT / "frontend"
WEB_COMPONENTS = PROJECT_ROOT / "web" / "components"

REQUIRED_STREAMLIT_PAGES = {
    "audit.py",
    "dashboard.py",
    "data_sources.py",
    "evaluations.py",
    "evidence.py",
    "graph_explorer_page.py",
    "home.py",
    "projects.py",
    "query_studio.py",
    "schema_studio.py",
}
REQUIRED_REACT_QUERY_MODULES = {
    "expert-review.tsx",
    "query-config.ts",
    "query-conversation-panel.tsx",
    "query-evidence-panel.tsx",
    "query-sidebar.tsx",
    "use-query-session.ts",
}


def _read(path: Path) -> str:
    if not path.is_file():
        raise RuntimeError(f"필수 파일 누락: {path.relative_to(PROJECT_ROOT)}")
    return path.read_text(encoding="utf-8")


def _require(source: str, markers: tuple[str, ...], label: str) -> None:
    missing = [marker for marker in markers if marker not in source]
    if missing:
        raise RuntimeError(f"{label} 계약 누락: {missing}")


def validate_streamlit_architecture() -> dict[str, int]:
    entrypoint_path = FRONTEND_ROOT / "streamlit_app.py"
    entrypoint = _read(entrypoint_path)
    function_names = {
        node.name
        for node in ast.parse(entrypoint).body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    if function_names != {"main"}:
        raise RuntimeError(
            "Streamlit entrypoint에는 main()만 있어야 합니다: "
            f"{sorted(function_names)}"
        )
    entrypoint_lines = len(entrypoint.splitlines())
    if entrypoint_lines > 150:
        raise RuntimeError(
            f"Streamlit entrypoint가 다시 비대해졌습니다: {entrypoint_lines}행"
        )

    actual_pages = {
        path.name
        for path in (FRONTEND_ROOT / "pages").glob("*.py")
        if path.name != "__init__.py"
    }
    if actual_pages != REQUIRED_STREAMLIT_PAGES:
        raise RuntimeError(
            "Streamlit page module 계약 불일치: "
            f"missing={sorted(REQUIRED_STREAMLIT_PAGES - actual_pages)}, "
            f"unexpected={sorted(actual_pages - REQUIRED_STREAMLIT_PAGES)}"
        )

    query_source = _read(FRONTEND_ROOT / "pages" / "query_studio.py")
    _require(
        query_source,
        (
            "st.tabs(",
            '"조회 결과"',
            '"생성 Cypher"',
            '"관계 경로"',
            '"검증 이력"',
            '"도메인 전문가 검증 · 전문가 전용"',
        ),
        "Streamlit Query Studio",
    )
    return {
        "entrypoint_lines": entrypoint_lines,
        "page_modules": len(actual_pages),
    }


def validate_react_architecture() -> dict[str, int]:
    query_workspace = _read(WEB_COMPONENTS / "query-workspace.tsx")
    query_lines = len(query_workspace.splitlines())
    if query_lines > 150:
        raise RuntimeError(
            f"React Query orchestrator가 다시 비대해졌습니다: {query_lines}행"
        )
    _require(
        query_workspace,
        (
            "QuerySidebar",
            "QueryConversationPanel",
            "QueryEvidencePanel",
            "useQuerySession",
        ),
        "React Query orchestrator",
    )

    actual_query_modules = {
        path.name
        for path in (WEB_COMPONENTS / "query").iterdir()
        if path.is_file()
    }
    missing_modules = REQUIRED_REACT_QUERY_MODULES - actual_query_modules
    if missing_modules:
        raise RuntimeError(
            f"React Query module 누락: {sorted(missing_modules)}"
        )

    overview_lines = len(
        _read(WEB_COMPONENTS / "project-overview.tsx").splitlines()
    )
    workspace_lines = len(
        _read(WEB_COMPONENTS / "project-workspace.tsx").splitlines()
    )
    if overview_lines > 120 or workspace_lines > 100:
        raise RuntimeError(
            "React Project workspace가 다시 비대해졌습니다: "
            f"overview={overview_lines}, workspace={workspace_lines}"
        )
    return {
        "query_orchestrator_lines": query_lines,
        "query_modules": len(actual_query_modules),
        "project_overview_lines": overview_lines,
        "project_workspace_lines": workspace_lines,
    }


def validate_critical_ux() -> dict[str, str]:
    site_header = _read(WEB_COMPONENTS / "site-header.tsx")
    query_session = _read(
        WEB_COMPONENTS / "query" / "use-query-session.ts"
    )
    evidence_panel = _read(
        WEB_COMPONENTS / "query" / "query-evidence-panel.tsx"
    )
    conversation_panel = _read(
        WEB_COMPONENTS / "query" / "query-conversation-panel.tsx"
    )
    expert_review = _read(
        WEB_COMPONENTS / "query" / "expert-review.tsx"
    )
    history = _read(WEB_COMPONENTS / "history-list.tsx")

    _require(
        site_header,
        (
            "menu-button",
            "nav-backdrop",
            'aria-controls="primary-navigation"',
            "mobile-project-control",
        ),
        "React mobile navigation",
    )
    _require(
        query_session,
        (
            'useState<EvidenceTab>("table")',
            "requestInFlightRef.current",
            "setQuestion(\"\")",
        ),
        "React query submission",
    )
    _require(
        evidence_panel,
        (
            'id="query-evidence"',
            'id: "table" as const',
            "aria-selected={session.activeTab === tab.id}",
        ),
        "React evidence",
    )
    _require(
        conversation_panel,
        ('className="evidence-jump"', 'href="#query-evidence"'),
        "React answer-to-evidence navigation",
    )
    _require(
        expert_review,
        ("<details", "전문가 전용"),
        "React expert review",
    )
    _require(
        history,
        (
            "아직 저장된 대화가 없습니다.",
            "/query?project_id=",
            "첫 질문 시작",
        ),
        "React history empty state",
    )
    return {
        "mobile_navigation": "PASS",
        "query_deduplication": "PASS",
        "evidence_default": "table",
        "expert_review": "collapsed",
        "history_empty_state": "PASS",
    }


def run_gate() -> dict[str, object]:
    return {
        "status": "PASS",
        "streamlit": validate_streamlit_architecture(),
        "react": validate_react_architecture(),
        "critical_ux": validate_critical_ux(),
    }


def main() -> None:
    print(json.dumps(run_gate(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
