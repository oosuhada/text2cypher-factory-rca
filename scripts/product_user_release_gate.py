#!/usr/bin/env python3
"""Stage 2.9-5 product-user release contracts.

The gate intentionally separates deterministic automation from the required
unmoderated human review. A passing automatic result never upgrades the final
product readiness to READY while the baseline manual review remains pending.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = PROJECT_ROOT / "evaluation" / "product_user_release_baseline.json"
sys.path.insert(0, str(PROJECT_ROOT))

from frontend.design_system import Role, navigation_for_role
from frontend.ui_mode import (
    DEPLOYMENT_FORBIDDEN_COPY,
    UiMode,
    visible_workspace_labels,
)


PRODUCT_ROUTE_FILES = {
    "/": "web/app/page.tsx",
    "/projects": "web/app/projects/page.tsx",
    "/query": "web/app/query/page.tsx",
    "/graph": "web/app/graph/page.tsx",
    "/history": "web/app/history/page.tsx",
}


def _read(relative_path: str) -> str:
    path = PROJECT_ROOT / relative_path
    if not path.is_file():
        raise RuntimeError(f"필수 파일 누락: {relative_path}")
    source = path.read_text(encoding="utf-8")
    if not source.strip():
        raise RuntimeError(f"빈 파일은 Release Gate 증거가 될 수 없습니다: {relative_path}")
    return source


def _require(source: str, markers: tuple[str, ...], label: str) -> None:
    missing = [marker for marker in markers if marker not in source]
    if missing:
        raise RuntimeError(f"{label} 계약 누락: {missing}")


def load_baseline() -> dict[str, Any]:
    baseline = json.loads(_read("evaluation/product_user_release_baseline.json"))
    required_keys = {
        "version",
        "product_entrypoint",
        "internal_console_entrypoint",
        "required_product_routes",
        "product_navigation",
        "internal_console_navigation",
        "viewport_widths",
        "deployment_forbidden_copy",
        "accessibility_contracts",
        "fixtures",
        "critical_journeys",
        "automatic_release_requirements",
        "manual_review",
    }
    missing = sorted(required_keys - baseline.keys())
    if missing:
        raise RuntimeError(f"제품 사용자 baseline 필드 누락: {missing}")
    if baseline["viewport_widths"] != [390, 768, 1280, 1440]:
        raise RuntimeError("반응형 Release Gate 폭은 390·768·1280·1440px이어야 합니다.")
    requirements = baseline["automatic_release_requirements"]
    if requirements.get("visible_link_click_success_rate") != 1.0:
        raise RuntimeError("표시 링크 클릭 성공률 기준은 100%여야 합니다.")
    for key in (
        "empty_body_count",
        "browser_console_error_count",
        "streamlit_exception_count",
        "horizontal_overflow_count",
        "forbidden_copy_count",
        "unauthorized_write_execution_count",
    ):
        if requirements.get(key) != 0:
            raise RuntimeError(f"{key} 기준은 0이어야 합니다.")
    manual_review = baseline["manual_review"]
    if manual_review.get("required_reviewers", 0) < 1:
        raise RuntimeError("실제 사용자 수동 검토자는 1명 이상이어야 합니다.")
    return baseline


def validate_product_routes(baseline: dict[str, Any]) -> dict[str, Any]:
    checked_routes: list[str] = []
    for route in baseline["required_product_routes"]:
        route_path = str(route["path"])
        normalized = route_path.split("?", 1)[0]
        relative_path = PRODUCT_ROUTE_FILES.get(normalized)
        if relative_path is None:
            raise RuntimeError(f"baseline의 제품 route가 코드 소유권 표에 없습니다: {route_path}")
        _read(relative_path)
        checked_routes.append(route_path)

    product_surface = _read("web/lib/product-surface.ts")
    for label, href in zip(
        baseline["product_navigation"],
        ("/projects", "/query", "/graph", "/history"),
        strict=True,
    ):
        _require(
            product_surface,
            (f'label: "{label}"', f'href: "{href}"'),
            f"React 표시 navigation {label}",
        )

    source_parts = []
    for directory in (PROJECT_ROOT / "web" / "app", PROJECT_ROOT / "web" / "components"):
        for path in sorted(directory.rglob("*.tsx")):
            source_parts.append(path.read_text(encoding="utf-8"))
    product_source = "\n".join(source_parts)
    leaked = [term for term in baseline["deployment_forbidden_copy"] if term in product_source]
    if leaked:
        raise RuntimeError(f"React 제품 source에 배포 금지 문구가 남아 있습니다: {leaked}")

    return {
        "entrypoints": 1,
        "routes": checked_routes,
        "navigation_items": len(baseline["product_navigation"]),
        "forbidden_copy_source_hits": 0,
    }


def validate_internal_console(baseline: dict[str, Any]) -> dict[str, Any]:
    all_data_steward_pages = tuple(
        item.label for item in navigation_for_role(Role.DATA_STEWARD)
    )
    production_pages = visible_workspace_labels(all_data_steward_pages, UiMode.PRODUCTION)
    demo_pages = visible_workspace_labels(all_data_steward_pages, UiMode.DEMO)
    expected = tuple(baseline["internal_console_navigation"])
    if production_pages != expected or demo_pages != expected:
        raise RuntimeError(
            "production·demo Internal Console navigation 불일치: "
            f"production={production_pages}, demo={demo_pages}, expected={expected}"
        )

    config = _read(".streamlit/config.toml")
    navigation = _read("frontend/navigation.py")
    console = _read("frontend/internal_console.py")
    router = _read("frontend/streamlit_router.py")
    _require(
        config,
        ("[client]", "showSidebarNavigation = false"),
        "Streamlit 자동 navigation 차단",
    )
    if navigation.count('st.sidebar.markdown("### 작업공간 이동")') != 1:
        raise RuntimeError("Streamlit 표시 navigation 그룹은 정확히 1개여야 합니다.")
    _require(
        console + router,
        (
            "render_internal_console",
            "build_hidden_navigation",
            'st.navigation(pages, position="hidden")',
            'if page == "Home"',
            'if page == "Projects"',
            'if page == "Pipeline"',
            'if page == "Query Studio"',
            'elif page == "Graph Explorer"',
            'elif page == "Dashboard"',
            'elif page == "Evaluations"',
            'elif page == "Audit Logs"',
            'elif page == "Data Sources"',
        ),
        "Internal Console 표시 workspace renderer",
    )
    baseline_forbidden = tuple(baseline["deployment_forbidden_copy"])
    if baseline_forbidden != DEPLOYMENT_FORBIDDEN_COPY:
        raise RuntimeError("제품 baseline과 런타임 배포 금지 문구 계약이 다릅니다.")

    return {
        "navigation_groups": 1,
        "production_workspaces": len(production_pages),
        "demo_workspaces": len(demo_pages),
        "automatic_sidebar_items": 0,
        "streamlit_exception_budget": 0,
    }


def validate_streamlit_navigation_runtime(
    baseline: dict[str, Any],
) -> dict[str, Any]:
    from streamlit.testing.v1 import AppTest

    previous_mode = os.environ.get("P3_UI_MODE")
    previous_role = os.environ.get("P3_UI_ROLE")
    os.environ["P3_UI_MODE"] = "demo"
    os.environ["P3_UI_ROLE"] = Role.DATA_STEWARD.value
    try:
        app = AppTest.from_file(
            str(PROJECT_ROOT / "frontend" / "streamlit_app.py")
        ).run(timeout=30)
        visited: list[str] = []
        forbidden_hits: dict[str, list[str]] = {}
        for page in baseline["internal_console_navigation"]:
            navigation = next(
                radio for radio in app.radio if radio.label == "Navigation"
            )
            navigation.set_value(page).run(timeout=30)
            if app.exception:
                messages = [str(exception.value) for exception in app.exception]
                raise RuntimeError(
                    f"Streamlit workspace exception: {page}: {messages}"
                )
            if not app.markdown:
                raise RuntimeError(f"Streamlit workspace 본문이 비었습니다: {page}")
            rendered_values = [
                str(getattr(element, "value", ""))
                for collection in (
                    app.markdown,
                    app.caption,
                    app.text,
                    app.info,
                    app.warning,
                    app.error,
                )
                for element in collection
            ]
            visible_text = "\n".join(
                value for value in rendered_values if not value.lstrip().startswith("<style")
            )
            leaked = [
                term
                for term in baseline["deployment_forbidden_copy"]
                if term in visible_text
            ]
            if leaked:
                forbidden_hits[page] = leaked
            visited.append(page)
        if forbidden_hits:
            raise RuntimeError(
                "demo Internal Console DOM에 배포 금지 문구가 있습니다: "
                f"{forbidden_hits}"
            )
        return {
            "visible_navigation_targets": len(visited),
            "clicked_navigation_targets": len(visited),
            "click_success_rate": 1.0,
            "empty_body_count": 0,
            "exception_count": 0,
            "forbidden_copy_count": 0,
        }
    finally:
        if previous_mode is None:
            os.environ.pop("P3_UI_MODE", None)
        else:
            os.environ["P3_UI_MODE"] = previous_mode
        if previous_role is None:
            os.environ.pop("P3_UI_ROLE", None)
        else:
            os.environ["P3_UI_ROLE"] = previous_role


def validate_accessibility_contracts(baseline: dict[str, Any]) -> dict[str, Any]:
    layout = _read("web/app/layout.tsx")
    globals_css = _read("web/app/globals.css")
    header = _read("web/components/site-header.tsx")
    project_form = _read("web/components/projects/project-create-form.tsx")
    query_form = _read("web/components/query/query-conversation-panel.tsx")
    graph_form = _read("web/components/graph-explorer.tsx")

    _require(
        layout,
        ('className="skip-link"', 'href="#main-content"', '<main id="main-content"'),
        "React skip link and semantic main",
    )
    _require(
        globals_css,
        (":focus-visible", "outline:", "@media (prefers-reduced-motion: reduce)"),
        "React keyboard focus and reduced-motion",
    )
    _require(
        header,
        (
            'aria-label="FactoryGraph 홈"',
            'aria-label="주요 작업공간"',
            'aria-controls="primary-navigation"',
            "aria-expanded={open}",
        ),
        "React header accessibility",
    )
    _require(
        project_form,
        (
            "프로젝트 ID",
            "프로젝트 이름",
            "도메인",
            "데이터셋/연결 이름",
            "<label>",
        ),
        "프로젝트 form label",
    )
    _require(
        query_form,
        ('aria-label="제조 관계 질문"', 'aria-label="질문 전송"'),
        "Query form label",
    )
    _require(
        graph_form,
        ('aria-label="노드 검색어"', "<label"),
        "Graph form label",
    )

    contracts = set(baseline["accessibility_contracts"])
    required = {
        "skip-link",
        "focus-visible",
        "form-label",
        "semantic-main",
        "keyboard-navigation",
        "reduced-motion",
    }
    missing = sorted(required - contracts)
    if missing:
        raise RuntimeError(f"접근성 baseline 계약 누락: {missing}")
    return {"contracts": sorted(contracts), "status": "PASS"}


def validate_fixture_contracts(baseline: dict[str, Any]) -> dict[str, Any]:
    fixtures = baseline["fixtures"]
    if len(fixtures["long_project_name"]) < 60:
        raise RuntimeError("긴 프로젝트명 fixture는 실제 truncation을 검증할 만큼 길어야 합니다.")
    if fixtures["large_result_rows"] < 100:
        raise RuntimeError("대량 결과 fixture는 최소 100행이어야 합니다.")
    if fixtures["query_error_status"] < 500:
        raise RuntimeError("오류 fixture는 서버 오류 상태를 사용해야 합니다.")
    required_journeys = {
        "project-switch",
        "recommended-question-preview",
        "single-query-submit",
        "evidence-jump",
        "graph-open",
        "history-reopen",
        "write-block",
        "recoverable-error",
    }
    missing = sorted(required_journeys - set(baseline["critical_journeys"]))
    if missing:
        raise RuntimeError(f"핵심 사용자 여정 baseline 누락: {missing}")
    return {
        "long_project_name_characters": len(fixtures["long_project_name"]),
        "large_result_rows": fixtures["large_result_rows"],
        "critical_journeys": len(baseline["critical_journeys"]),
    }


def run_gate() -> dict[str, Any]:
    baseline = load_baseline()
    manual_status = str(baseline["manual_review"].get("status", "PENDING")).upper()
    return {
        "automatic_gate": "PASS",
        "final_ready": manual_status == "PASS",
        "manual_user_review": manual_status,
        "baseline_version": baseline["version"],
        "product": validate_product_routes(baseline),
        "internal_console": {
            **validate_internal_console(baseline),
            **validate_streamlit_navigation_runtime(baseline),
        },
        "accessibility": validate_accessibility_contracts(baseline),
        "fixtures": validate_fixture_contracts(baseline),
        "release_decision": (
            "READY" if manual_status == "PASS" else "AUTOMATION PASS · MANUAL REVIEW PENDING"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="JSON 결과 출력")
    args = parser.parse_args()
    result = run_gate()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
