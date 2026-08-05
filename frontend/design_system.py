"""Enterprise Streamlit information architecture and design contracts.

This module deliberately contains no Streamlit imports.  Navigation, role
visibility, view-state copy, and visual tokens can therefore be validated
without starting the application.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final


class Role(str, Enum):
    VIEWER = "Viewer"
    ANALYST = "Analyst"
    DOMAIN_EXPERT = "Domain Expert"
    DATA_STEWARD = "Data Steward"
    ADMIN = "Admin"


class ViewState(str, Enum):
    READY = "ready"
    LOADING = "loading"
    EMPTY = "empty"
    ERROR = "error"


@dataclass(frozen=True)
class StateCopy:
    title: str
    message: str
    action: str | None = None


@dataclass(frozen=True)
class NavigationItem:
    key: str
    label: str
    icon: str
    section: str
    description: str
    roles: frozenset[Role]
    delivery: str
    implementation_stage: str


ALL_ROLES: Final = frozenset(Role)
INVESTIGATION_ROLES: Final = frozenset(
    {
        Role.VIEWER,
        Role.ANALYST,
        Role.DOMAIN_EXPERT,
        Role.DATA_STEWARD,
        Role.ADMIN,
    }
)
GOVERNANCE_ROLES: Final = frozenset(
    {
        Role.ANALYST,
        Role.DOMAIN_EXPERT,
        Role.DATA_STEWARD,
        Role.ADMIN,
    }
)
APPROVER_ROLES: Final = frozenset(
    {Role.DOMAIN_EXPERT, Role.DATA_STEWARD, Role.ADMIN}
)
DATA_ROLES: Final = frozenset({Role.DATA_STEWARD, Role.ADMIN})


NAVIGATION_ITEMS: Final[tuple[NavigationItem, ...]] = (
    NavigationItem(
        "home",
        "Home",
        "⌂",
        "Overview",
        "플랫폼 목적, 최근 프로젝트와 시스템 상태",
        ALL_ROLES,
        "available",
        "2-1",
    ),
    NavigationItem(
        "projects",
        "Projects",
        "▦",
        "Overview",
        "프로젝트 생성, 검색, 전환과 준비 상태",
        ALL_ROLES,
        "foundation",
        "2-2",
    ),
    NavigationItem(
        "data_sources",
        "Data Sources",
        "⇧",
        "Data foundation",
        "파일·그래프 연결, 업로드 이력과 프로파일",
        DATA_ROLES,
        "available",
        "2-3",
    ),
    NavigationItem(
        "pipeline",
        "Pipeline",
        "⌁",
        "Data foundation",
        "매핑 검토, dry-run, 적재와 무결성 확인",
        DATA_ROLES,
        "available",
        "2-3",
    ),
    NavigationItem(
        "query_studio",
        "Query Studio",
        "◈",
        "Investigation",
        "자연어 질문, Cypher, 결과와 근거 경로",
        INVESTIGATION_ROLES,
        "available",
        "2-4",
    ),
    NavigationItem(
        "graph_explorer",
        "Graph Explorer",
        "⌘",
        "Investigation",
        "그래프 검색, 필터, 이웃과 경로 탐색",
        INVESTIGATION_ROLES,
        "available",
        "2-5",
    ),
    NavigationItem(
        "dashboard",
        "Dashboard",
        "▥",
        "Investigation",
        "품질·공정·설비 KPI와 운영 지표",
        INVESTIGATION_ROLES,
        "available",
        "2-6",
    ),
    NavigationItem(
        "evaluations",
        "Evaluations",
        "✓",
        "Governance",
        "Gold·Blind 실행, 비교와 실패 유형 분석",
        GOVERNANCE_ROLES,
        "foundation",
        "2-6",
    ),
    NavigationItem(
        "approval_queue",
        "Approval Queue",
        "◇",
        "Governance",
        "스키마·적재·심각 권고와 알림 승인",
        APPROVER_ROLES,
        "foundation",
        "3-6",
    ),
    NavigationItem(
        "audit_logs",
        "Audit Logs",
        "≡",
        "Governance",
        "라우팅·Tool·Cypher·승인·알림 추적",
        GOVERNANCE_ROLES,
        "foundation",
        "3-7",
    ),
    NavigationItem(
        "admin",
        "Admin",
        "⚙",
        "Administration",
        "사용자·역할·연결·모델·보존정책",
        frozenset({Role.ADMIN}),
        "foundation",
        "3-8",
    ),
)

PAGE_BY_LABEL: Final = {item.label: item for item in NAVIGATION_ITEMS}
PAGE_BY_KEY: Final = {item.key: item for item in NAVIGATION_ITEMS}


DESIGN_TOKENS: Final = {
    "color": {
        "brand_950": "#082F2C",
        "brand_800": "#115E59",
        "brand_700": "#0F766E",
        "brand_500": "#14B8A6",
        "brand_100": "#CCFBF1",
        "surface": "#FFFFFF",
        "surface_subtle": "#F8FAFC",
        "border": "#DDE6E8",
        "text": "#0F172A",
        "text_muted": "#64748B",
        "success": "#15803D",
        "warning": "#B45309",
        "error": "#B91C1C",
        "info": "#0369A1",
    },
    "type": {
        "family": (
            '"Pretendard", "Inter", -apple-system, BlinkMacSystemFont, '
            '"Segoe UI", sans-serif'
        ),
        "mono": 'ui-monospace, "SFMono-Regular", Menlo, monospace',
        "size_xs": "0.75rem",
        "size_sm": "0.875rem",
        "size_md": "1rem",
        "size_lg": "1.25rem",
        "size_xl": "1.75rem",
    },
    "space": {
        "1": "0.25rem",
        "2": "0.5rem",
        "3": "0.75rem",
        "4": "1rem",
        "6": "1.5rem",
        "8": "2rem",
        "12": "3rem",
    },
    "radius": {"sm": "8px", "md": "14px", "lg": "20px", "pill": "999px"},
    "shadow": {
        "sm": "0 1px 3px rgba(15, 23, 42, 0.08)",
        "md": "0 12px 30px rgba(15, 118, 110, 0.12)",
    },
}


DEFAULT_STATE_COPY: Final = {
    ViewState.READY: StateCopy(
        "준비됨", "최신 프로젝트 컨텍스트를 불러왔습니다."
    ),
    ViewState.LOADING: StateCopy(
        "불러오는 중", "데이터와 실행 상태를 안전하게 확인하고 있습니다."
    ),
    ViewState.EMPTY: StateCopy(
        "아직 표시할 항목이 없습니다.",
        "첫 작업을 시작하면 결과가 이 화면에 기록됩니다.",
        "시작하기",
    ),
    ViewState.ERROR: StateCopy(
        "요청을 완료하지 못했습니다.",
        "연결 상태와 권한을 확인한 뒤 다시 시도해 주세요.",
        "다시 시도",
    ),
}


REACT_STREAMLIT_BOUNDARY: Final = {
    "streamlit": (
        "인증 이후 사내 업무 화면의 기준 구현",
        "프로젝트·데이터·질의·그래프·평가·승인·감사 상태의 단일 소유자",
        "FastAPI를 통해 업무 상태를 읽고 변경",
    ),
    "react": (
        "외부 공개용 제품 소개와 포트폴리오 셸에 한해 선택 사용",
        "업무 기능을 중복 구현하거나 Streamlit을 iframe으로 감싸지 않음",
        "향후 교체 시 동일 FastAPI 계약을 사용하는 별도 클라이언트",
    ),
    "backend": (
        "프로젝트·작업·권한·평가 상태의 source of truth",
        "두 UI가 파일이나 Neo4j에 직접 접근하지 않도록 API 경계 제공",
    ),
}


WIREFLOWS: Final = {
    "data_onboarding": (
        "Home",
        "Projects",
        "Data Sources",
        "Pipeline",
        "Evaluations",
        "Query Studio",
    ),
    "rca_investigation": (
        "Projects",
        "Query Studio",
        "Graph Explorer",
        "Approval Queue",
        "Audit Logs",
    ),
    "operations_review": (
        "Dashboard",
        "Evaluations",
        "Audit Logs",
    ),
}


def navigation_for_role(role: Role | str) -> tuple[NavigationItem, ...]:
    resolved = role if isinstance(role, Role) else Role(role)
    return tuple(item for item in NAVIGATION_ITEMS if resolved in item.roles)


def can_access(role: Role | str, page_label: str) -> bool:
    item = PAGE_BY_LABEL.get(page_label)
    if item is None:
        return False
    resolved = role if isinstance(role, Role) else Role(role)
    return resolved in item.roles


def state_copy(
    state: ViewState | str,
    *,
    page_label: str | None = None,
) -> StateCopy:
    resolved = state if isinstance(state, ViewState) else ViewState(state)
    copy = DEFAULT_STATE_COPY[resolved]
    if not page_label:
        return copy
    return StateCopy(
        title=copy.title,
        message=f"{page_label}: {copy.message}",
        action=copy.action,
    )


def build_global_css() -> str:
    color = DESIGN_TOKENS["color"]
    type_tokens = DESIGN_TOKENS["type"]
    radius = DESIGN_TOKENS["radius"]
    shadow = DESIGN_TOKENS["shadow"]
    return f"""
    <style>
      :root {{
        --p3-brand-950: {color["brand_950"]};
        --p3-brand-700: {color["brand_700"]};
        --p3-brand-500: {color["brand_500"]};
        --p3-surface: {color["surface"]};
        --p3-surface-subtle: {color["surface_subtle"]};
        --p3-border: {color["border"]};
        --p3-text: {color["text"]};
        --p3-text-muted: {color["text_muted"]};
        --p3-success: {color["success"]};
        --p3-warning: {color["warning"]};
        --p3-error: {color["error"]};
        --p3-info: {color["info"]};
        --p3-radius-md: {radius["md"]};
        --p3-radius-lg: {radius["lg"]};
      }}
      html, body, [class*="css"] {{
        font-family: {type_tokens["family"]};
        color: var(--p3-text);
      }}
      .p3-page-head {{
        display:flex;
        justify-content:space-between;
        align-items:flex-start;
        gap:1rem;
        padding:1rem 0 1.25rem;
        border-bottom:1px solid var(--p3-border);
        margin-bottom:1rem;
      }}
      .p3-page-head h1 {{
        margin:0 0 .3rem;
        font-size:{type_tokens["size_xl"]};
        letter-spacing:-.035em;
      }}
      .p3-page-head p {{
        margin:0;
        color:var(--p3-text-muted);
        font-size:{type_tokens["size_sm"]};
      }}
      .p3-stage-badge {{
        white-space:nowrap;
        border:1px solid #99F6E4;
        border-radius:{radius["pill"]};
        padding:.28rem .65rem;
        background:#F0FDFA;
        color:#115E59;
        font-size:{type_tokens["size_xs"]};
        font-weight:700;
      }}
      .p3-state-card {{
        border:1px solid var(--p3-border);
        border-radius:var(--p3-radius-md);
        padding:1rem 1.1rem;
        background:var(--p3-surface-subtle);
        box-shadow:{shadow["sm"]};
      }}
      .p3-state-card h3 {{margin:0 0 .35rem;font-size:1rem;}}
      .p3-state-card p {{
        margin:0;color:var(--p3-text-muted);font-size:.85rem;line-height:1.55;
      }}
      .p3-foundation-grid {{
        display:grid;
        grid-template-columns:repeat(2,minmax(0,1fr));
        gap:.75rem;
        margin:.9rem 0;
      }}
      .p3-foundation-card {{
        border:1px solid var(--p3-border);
        border-radius:var(--p3-radius-md);
        padding:1rem;
        background:var(--p3-surface);
      }}
      .p3-foundation-card b {{display:block;margin-bottom:.3rem;}}
      .p3-foundation-card span {{
        color:var(--p3-text-muted);font-size:.8rem;line-height:1.5;
      }}
      @media (max-width: 760px) {{
        .p3-page-head {{display:block;}}
        .p3-stage-badge {{display:inline-block;margin-top:.7rem;}}
        .p3-foundation-grid {{grid-template-columns:1fr;}}
      }}
    </style>
    """
