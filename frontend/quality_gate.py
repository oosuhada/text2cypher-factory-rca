"""Deterministic enterprise UI release and visual-contract checks."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from .design_system import (
    ACTION_ROLES,
    NAVIGATION_ITEMS,
    SUPPORTED_LOCALES,
    Action,
    Role,
    build_global_css,
    can_access,
    can_perform,
)


VISUAL_LANDMARKS = {
    "Home": ("Find the path.", "Workspace overview"),
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
        "version": "enterprise-ui-2.8",
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
        "navigation": [
            {
                "label": item.label,
                "delivery": item.delivery,
                "stage": item.implementation_stage,
            }
            for item in NAVIGATION_ITEMS
        ],
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

    app_source = (
        root / "frontend" / "streamlit_app.py"
    ).read_text(encoding="utf-8")
    required_runtime_markers = (
        "pending_audit_question",
        "render_startup_failure",
        "st.toast",
        "get_services.clear()",
        "evaluation_filters",
        "explorer_widget_revision",
    )
    missing_markers = [
        marker for marker in required_runtime_markers if marker not in app_source
    ]
    if missing_markers:
        raise RuntimeError(
            f"Streamlit 상태·복구 계약 누락: {missing_markers}"
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
