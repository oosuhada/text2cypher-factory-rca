#!/usr/bin/env python3
"""Cross-surface architecture and critical UX release contracts."""

from __future__ import annotations

import ast
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = PROJECT_ROOT / "frontend"
WEB_COMPONENTS = PROJECT_ROOT / "web" / "components"
WEB_LIB = PROJECT_ROOT / "web" / "lib"

REQUIRED_STREAMLIT_WORKSPACES = {
    "audit.py",
    "dashboard.py",
    "data_sources.py",
    "evaluations.py",
    "evidence.py",
    "graph_explorer.py",
    "home.py",
    "projects.py",
    "query_studio.py",
    "schema_studio.py",
}
REQUIRED_LEGACY_PAGE_REDIRECTS = {
    "audit.py": "audit_logs",
    "dashboard.py": "dashboard",
    "data_sources.py": "data_sources",
    "evaluations.py": "evaluations",
    "evidence.py": "query_studio",
    "graph_explorer_page.py": "graph_explorer",
    "home.py": "home",
    "projects.py": "projects",
    "query_studio.py": "query_studio",
    "schema_studio.py": "pipeline",
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

    actual_workspaces = {
        path.name
        for path in (FRONTEND_ROOT / "workspaces").glob("*.py")
        if path.name != "__init__.py"
    }
    if actual_workspaces != REQUIRED_STREAMLIT_WORKSPACES:
        raise RuntimeError(
            "Streamlit workspace module 계약 불일치: "
            f"missing={sorted(REQUIRED_STREAMLIT_WORKSPACES - actual_workspaces)}, "
            f"unexpected={sorted(actual_workspaces - REQUIRED_STREAMLIT_WORKSPACES)}"
        )
    router_source = _read(FRONTEND_ROOT / "streamlit_router.py")
    console_source = _read(FRONTEND_ROOT / "internal_console.py")
    if "frontend.pages." in entrypoint + router_source + console_source:
        raise RuntimeError(
            "Streamlit runtime 경계가 framework-reserved pages namespace를 import합니다."
        )
    _require(
        entrypoint + router_source + console_source,
        (
            "build_hidden_navigation",
            'st.navigation(pages, position="hidden")',
            "frontend.workspaces.",
        ),
        "Streamlit hidden router and workspace boundary",
    )

    config_source = _read(PROJECT_ROOT / ".streamlit" / "config.toml")
    _require(
        config_source,
        ("[client]", "showSidebarNavigation = false"),
        "Streamlit automatic sidebar suppression",
    )
    legacy_pages = FRONTEND_ROOT / "pages"
    for filename, workspace_key in REQUIRED_LEGACY_PAGE_REDIRECTS.items():
        source = _read(legacy_pages / filename)
        _require(
            source,
            (
                'if __name__ == "__main__":',
                "redirect_legacy_page",
                f'redirect_legacy_page("{workspace_key}")',
            ),
            f"Legacy Streamlit redirect {filename}",
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
    navigation_source = _read(FRONTEND_ROOT / "navigation.py")
    _require(
        navigation_source,
        (
            'st.session_state["pending_page"] = page',
            'st.session_state["consumed_workspace_query"] = workspace_key',
            'st.query_params["workspace"] = workspace_key',
        ),
        "Streamlit atomic navigation",
    )
    return {
        "entrypoint_lines": entrypoint_lines,
        "workspace_modules": len(actual_workspaces),
        "legacy_redirects": len(REQUIRED_LEGACY_PAGE_REDIRECTS),
        "automatic_sidebar": 0,
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
    site_footer = _read(WEB_COMPONENTS / "site-footer.tsx")
    product_surface = _read(WEB_LIB / "product-surface.ts")
    streamlit_entrypoint = _read(FRONTEND_ROOT / "streamlit_app.py")
    streamlit_home = _read(FRONTEND_ROOT / "pages" / "home.py")
    streamlit_sidebar = _read(FRONTEND_ROOT / "sidebar.py")
    data_redirect = _read(PROJECT_ROOT / "web" / "app" / "data" / "page.tsx")
    schema_redirect = _read(
        PROJECT_ROOT / "web" / "app" / "schema" / "page.tsx"
    )
    operations_redirect = _read(
        PROJECT_ROOT / "web" / "app" / "operations" / "page.tsx"
    )
    query_session = _read(
        WEB_COMPONENTS / "query" / "use-query-session.ts"
    )
    evidence_panel = _read(
        WEB_COMPONENTS / "query" / "query-evidence-panel.tsx"
    )
    conversation_panel = _read(
        WEB_COMPONENTS / "query" / "query-conversation-panel.tsx"
    )
    response_next_actions = _read(
        WEB_COMPONENTS / "query" / "response-next-actions.tsx"
    )
    expert_review = _read(
        WEB_COMPONENTS / "query" / "expert-review.tsx"
    )
    history = _read(WEB_COMPONENTS / "history-list.tsx")

    _require(
        site_header,
        (
            "PRODUCT_NAVIGATION",
            "menu-button",
            "nav-backdrop",
            'aria-controls="primary-navigation"',
            "mobile-project-control",
        ),
        "React product navigation",
    )
    _require(
        product_surface,
        (
            'href: "/projects"',
            'href: "/query"',
            'href: "/graph"',
            'href: "/history"',
            'label: "Evidence / Graph"',
            "INTERNAL_CONSOLE_URL",
            "internalConsoleUrl",
            'rcaQuery: "react"',
            'evaluations: "streamlit"',
            'platformState: "backend"',
        ),
        "Product surface ownership",
    )
    forbidden_product_routes = ('href: "/data"', 'href: "/schema"', 'href: "/operations"')
    leaked_routes = [
        route for route in forbidden_product_routes if route in product_surface
    ]
    if leaked_routes:
        raise RuntimeError(
            f"내부 운영 route가 제품 navigation에 남아 있습니다: {leaked_routes}"
        )
    _require(
        site_footer,
        ("INTERNAL_CONSOLE_URL", "Internal Console", "Evidence / Graph"),
        "React internal-console handoff",
    )
    _require(
        streamlit_entrypoint,
        ('APP_TITLE = "Factory Graph RCA — Internal Console"',),
        "Streamlit internal-console title",
    )
    _require(
        streamlit_home,
        (
            "Internal Operations Console",
            "React 제품 UI 열기",
            "최종 사용자 발표 여정은 React 제품 UI에서 완결합니다.",
        ),
        "Streamlit internal-console home",
    )
    _require(
        streamlit_sidebar,
        (
            "Internal Console · 데이터·평가·운영 진단 전용",
            'st.query_params.get("project_id")',
        ),
        "Streamlit internal-console sidebar",
    )
    _require(
        data_redirect,
        ("internalConsoleUrl", '"data_sources"', "projectId", "redirect("),
        "React Data internal-console redirect",
    )
    _require(
        schema_redirect,
        ("internalConsoleUrl", '"pipeline"', "projectId", "redirect("),
        "React Schema internal-console redirect",
    )
    _require(
        operations_redirect,
        ("internalConsoleUrl", '"dashboard"', "projectId", "redirect("),
        "React Operations internal-console redirect",
    )
    _require(
        query_session,
        (
            'useState<EvidenceTab>("table")',
            "requestInFlightRef.current",
            "setQuestionState(\"\")",
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
        ("ResponseNextActions", "session.response.status === \"success\""),
        "React status-aware answer actions",
    )
    _require(
        response_next_actions,
        (
            'className="evidence-jump"',
            'href="#query-evidence"',
            "저장된 기록 보기",
            "조건 바꿔 다시 질문",
            "안전한 조회 질문 작성",
        ),
        "React answer-to-evidence and recovery navigation",
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
        "product_surface_boundary": "PASS",
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
