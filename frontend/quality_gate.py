"""Deterministic enterprise UI release and visual-contract checks."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from .design_system import (
    ACTION_ROLES,
    INTERNAL_CONSOLE_NAVIGATION,
    NAVIGATION_ITEMS,
    PRODUCT_UI_NAVIGATION,
    REACT_STREAMLIT_BOUNDARY,
    SIDEBAR_SECTION_ORDER,
    SUPPORTED_LOCALES,
    SURFACE_OWNERSHIP,
    Action,
    Role,
    build_global_css,
    can_access,
    can_perform,
)


VISUAL_LANDMARKS = {
    "Home": ("Internal Console", "Workspace overview"),
    "Projects": ("Projects", "새 프로젝트"),
    "Data Sources": ("Data Sources", "데이터"),
    "Pipeline": ("Pipeline", "Graph mapping"),
    "Query Studio": ("Query Studio", "Cypher", "근거"),
    "Graph Explorer": ("Interactive Graph Explorer", "N-hop"),
    "Dashboard": ("전역 운영 필터", "Agent 품질과 런타임"),
    "Evaluations": ("평가 릴리스 게이트", "모델·프롬프트 비교"),
    "Audit Logs": ("대화 History", "운영 Timeline", "Run detail"),
}


def current_visual_contract() -> dict[str, Any]:
    css = build_global_css()
    return {
        "version": "enterprise-ui-2.11-product-surface",
        "css_sha256": sha256(css.encode("utf-8")).hexdigest(),
        "locales": list(SUPPORTED_LOCALES),
        "responsive_breakpoints": [760],
        "accessibility_contracts": [
            "skip-link",
            "focus-visible",
            "reduced-motion",
            "forced-colors",
            "44px-equivalent-control-target",
        ],
        "screens": {
            page: list(landmarks)
            for page, landmarks in VISUAL_LANDMARKS.items()
        },
        "sidebar_order": list(SIDEBAR_SECTION_ORDER),
        "navigation_contracts": [
            "pending-page-transition",
            "explicit-home-return",
        ],
        "navigation": [
            {
                "label": item.label,
                "delivery": item.delivery,
                "stage": item.implementation_stage,
            }
            for item in NAVIGATION_ITEMS
        ],
        "product_surface": {
            "product_navigation": list(PRODUCT_UI_NAVIGATION),
            "internal_console_navigation": list(
                INTERNAL_CONSOLE_NAVIGATION
            ),
            "ownership": dict(SURFACE_OWNERSHIP),
            "boundary": {
                surface: list(statements)
                for surface, statements in REACT_STREAMLIT_BOUNDARY.items()
            },
        },
    }


def role_journey_contract() -> dict[str, list[str]]:
    return {
        role.value: [
            item.label
            for item in NAVIGATION_ITEMS
            if can_access(role, item.label)
        ]
        for role in Role
    }


def run_ui_quality_gate(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    baseline_path = root / "evaluation" / "ui_visual_baseline.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    current = current_visual_contract()
    if baseline != current:
        raise RuntimeError(
            "UI visual contract가 승인 baseline과 다릅니다. "
            "브라우저 검증 후 baseline을 명시적으로 갱신하세요."
        )

    expected_actions = set(Action)
    if set(ACTION_ROLES) != expected_actions:
        raise RuntimeError("RBAC action matrix가 완전하지 않습니다.")
    if can_perform(Role.VIEWER, Action.MANAGE_DATA):
        raise RuntimeError("Viewer가 데이터 변경 권한을 가집니다.")
    if not can_perform(Role.ADMIN, Action.MANAGE_PLATFORM):
        raise RuntimeError("Admin 운영 권한이 누락됐습니다.")

    if SURFACE_OWNERSHIP["rca_query"] != "react":
        raise RuntimeError("RCA 질의 제품 소유자가 React가 아닙니다.")
    if SURFACE_OWNERSHIP["evaluations"] != "streamlit":
        raise RuntimeError("평가 기능이 내부 콘솔로 격리되지 않았습니다.")
    if SURFACE_OWNERSHIP["platform_state"] != "backend":
        raise RuntimeError("플랫폼 상태 source of truth가 backend가 아닙니다.")

    required_schemas = (
        root / "schemas" / "cip-dmd" / "schema.yml",
        root / "schemas" / "equipment-history" / "schema.yml",
    )
    missing_schemas = [
        str(path.relative_to(root))
        for path in required_schemas
        if not path.exists()
    ]
    if missing_schemas:
        raise RuntimeError(
            f"두 도메인 UI 검증 schema가 누락됐습니다: {missing_schemas}"
        )

    frontend_sources = {
        name: (root / "frontend" / name).read_text(encoding="utf-8")
        for name in (
            "streamlit_app.py",
            "streamlit_router.py",
            "internal_console.py",
            "runtime.py",
            "session_state.py",
            "navigation.py",
            "sidebar.py",
            "common_ui.py",
            "ui_mode.py",
        )
    }
    frontend_sources.update(
        {
            f"workspaces/{path.name}": path.read_text(encoding="utf-8")
            for path in sorted(
                (root / "frontend" / "workspaces").glob("*.py")
            )
        }
    )
    frontend_sources.update(
        {
            f"legacy-pages/{path.name}": path.read_text(encoding="utf-8")
            for path in sorted((root / "frontend" / "pages").glob("*.py"))
        }
    )
    config_source = (
        root / ".streamlit" / "config.toml"
    ).read_text(encoding="utf-8")
    if "showSidebarNavigation = false" not in config_source:
        raise RuntimeError("Streamlit 자동 사이드바 내비게이션이 활성화돼 있습니다.")
    runtime_boundary = "\n".join(
        frontend_sources[name]
        for name in (
            "streamlit_app.py",
            "streamlit_router.py",
            "internal_console.py",
        )
    )
    if "frontend.pages." in runtime_boundary:
        raise RuntimeError("Streamlit runtime 경계가 예약된 pages namespace를 사용합니다.")
    if "frontend.workspaces." not in runtime_boundary:
        raise RuntimeError("Streamlit 공식 workspace boundary가 누락됐습니다.")
    if 'st.navigation(pages, position="hidden")' not in runtime_boundary:
        raise RuntimeError("Streamlit 숨김 공식 라우터가 누락됐습니다.")
    ui_mode_source = frontend_sources["ui_mode.py"]
    for marker in (
        "P3_UI_MODE",
        "production",
        "demo",
        "development",
        "DEPLOYMENT_FORBIDDEN_COPY",
    ):
        if marker not in ui_mode_source:
            raise RuntimeError(f"UI mode 계약 누락: {marker}")
    runtime_source = "\n".join(frontend_sources.values())
    required_runtime_markers = (
        "pending_audit_question",
        "render_startup_failure",
        "st.toast",
        "clear_service_cache",
        "evaluation_filters",
        "explorer_widget_revision",
        "navigation_widget_revision",
        "pending_page",
        "render_workspace_link(",
    )
    missing_markers = [
        marker
        for marker in required_runtime_markers
        if marker not in runtime_source
    ]
    if missing_markers:
        raise RuntimeError(
            f"Streamlit 상태·복구 계약 누락: {missing_markers}"
        )
    sidebar_module = frontend_sources["sidebar.py"]
    sidebar_start = sidebar_module.index("def render_sidebar(")
    sidebar_source = sidebar_module[sidebar_start:]
    sidebar_markers = (
        "_render_sidebar_project(",
        "render_sidebar_navigation(",
        "_render_sidebar_conversations(",
        "_render_sidebar_execution(",
        '"역할 미리보기"',
        '"언어 / Language"',
        '"### 안전 설정"',
    )
    sidebar_positions = [
        sidebar_source.index(marker) for marker in sidebar_markers
    ]
    if sidebar_positions != sorted(sidebar_positions):
        raise RuntimeError(
            "Streamlit sidebar가 프로젝트 → 작업공간 → 대화 → "
            "실행 설정 → 역할 → 언어 → 안전 설정 순서가 아닙니다."
        )
    return {
        "status": "PASS",
        "roles": role_journey_contract(),
        "actions": {
            action.value: sorted(role.value for role in roles)
            for action, roles in ACTION_ROLES.items()
        },
        "projects": ["cip-dmd", "equipment-history"],
        "visual_contract": current["version"],
        "visual_contract_sha256": current["css_sha256"],
        "failure_fallback": "PASS",
        "session_cache_stability": "PASS",
    }
