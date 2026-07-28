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


class Action(str, Enum):
    VIEW = "view"
    RUN_QUERY = "run_query"
    RERUN_QUERY = "rerun_query"
    EXPORT_EVIDENCE = "export_evidence"
    REVIEW_RESULT = "review_result"
    MANAGE_DATA = "manage_data"
    RUN_EVALUATION = "run_evaluation"
    MANAGE_PLATFORM = "manage_platform"


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

ACTION_ROLES: Final = {
    Action.VIEW: ALL_ROLES,
    Action.RUN_QUERY: INVESTIGATION_ROLES,
    Action.RERUN_QUERY: GOVERNANCE_ROLES,
    Action.EXPORT_EVIDENCE: INVESTIGATION_ROLES,
    Action.REVIEW_RESULT: APPROVER_ROLES,
    Action.MANAGE_DATA: DATA_ROLES,
    Action.RUN_EVALUATION: GOVERNANCE_ROLES,
    Action.MANAGE_PLATFORM: frozenset({Role.ADMIN}),
}

SIDEBAR_SECTION_ORDER: Final = (
    "프로젝트",
    "작업공간 이동",
    "대화",
    "실행 설정",
    "역할 미리보기",
    "언어 / Language",
    "안전 설정",
)

SUPPORTED_LOCALES: Final = ("ko", "en")
PAGE_DESCRIPTIONS_EN: Final = {
    "Home": "Internal console responsibilities, project readiness and operations",
    "Projects": "Inspect registry, readiness and internal project operations",
    "Data Sources": "File and graph connections, uploads and profiles",
    "Pipeline": "Mapping review, dry-run, load and integrity validation",
    "Query Studio": "Internal query diagnostics, Cypher and validation traces",
    "Graph Explorer": "Internal graph diagnostics and path inspection",
    "Dashboard": "Quality, process, equipment and operational KPIs",
    "Evaluations": "Gold and Blind comparison with failure analysis",
    "Approval Queue": "Approve schemas, loads and high-risk recommendations",
    "Audit Logs": "Trace queries, ETL, evaluation and approvals",
    "Admin": "Users, roles, connections, models and retention policy",
}

UI_COPY: Final = {
    "ko": {
        "workspace": "Internal Console",
        "language": "언어 / Language",
        "operational": "내부 운영",
        "preparing": "준비",
        "skip": "본문으로 건너뛰기",
    },
    "en": {
        "workspace": "Internal Console",
        "language": "Language / 언어",
        "operational": "Internal console",
        "preparing": "Planned",
        "skip": "Skip to main content",
    },
}


NAVIGATION_ITEMS: Final[tuple[NavigationItem, ...]] = (
    NavigationItem(
        "home",
        "Home",
        "⌂",
        "Overview",
        "내부 콘솔 역할, 프로젝트 준비 상태와 운영 진단",
        ALL_ROLES,
        "available",
        "2-1",
    ),
    NavigationItem(
        "projects",
        "Projects",
        "▦",
        "Overview",
        "프로젝트 Registry, 전환과 readiness 진단",
        ALL_ROLES,
        "available",
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
        "내부 질의 진단, Cypher와 검증 trace",
        INVESTIGATION_ROLES,
        "available",
        "2-4",
    ),
    NavigationItem(
        "graph_explorer",
        "Graph Explorer",
        "⌘",
        "Investigation",
        "내부 그래프 진단, 검색과 관계 경로 점검",
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
        "available",
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
        "available",
        "2-7",
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


PRODUCT_UI_NAVIGATION: Final = (
    "Projects",
    "Query Studio",
    "Evidence / Graph",
    "History",
    "Expert Review",
)

INTERNAL_CONSOLE_NAVIGATION: Final = (
    "Projects",
    "Data Sources",
    "Pipeline",
    "Query Diagnostics",
    "Graph Diagnostics",
    "Dashboard",
    "Evaluations",
    "Audit Logs",
    "Admin",
)

SURFACE_OWNERSHIP: Final = {
    "project_selection": "react",
    "rca_query": "react",
    "evidence_graph": "react",
    "conversation_history": "react",
    "expert_review": "react",
    "data_sources": "streamlit",
    "pipeline": "streamlit",
    "evaluations": "streamlit",
    "audit_logs": "streamlit",
    "model_diagnostics": "streamlit",
    "platform_state": "backend",
}

REACT_STREAMLIT_BOUNDARY: Final = {
    "react": (
        "최종 사용자와 발표 평가자의 단일 제품 진입점",
        "프로젝트 선택·RCA 질문·답변·근거·기록·전문가 검토의 소유자",
        "내부 운영 기능을 중복 구현하지 않고 필요 시 내부 콘솔로 연결",
    ),
    "streamlit": (
        "개발자·Data Steward·Admin을 위한 내부 운영 콘솔",
        "데이터 온보딩·ETL·평가·감사·모델 진단 기능의 소유자",
        "React 제품 UI를 iframe으로 감싸거나 별도 제품처럼 경쟁하지 않음",
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
    "enterprise_release_gate": (
        "Projects",
        "Data Sources",
        "Pipeline",
        "Evaluations",
        "Query Studio",
        "Graph Explorer",
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


def can_perform(role: Role | str, action: Action | str) -> bool:
    resolved_role = role if isinstance(role, Role) else Role(role)
    resolved_action = (
        action if isinstance(action, Action) else Action(action)
    )
    return resolved_role in ACTION_ROLES[resolved_action]


def ui_text(key: str, locale: str = "ko") -> str:
    resolved = locale if locale in SUPPORTED_LOCALES else "ko"
    return UI_COPY[resolved].get(key, UI_COPY["ko"].get(key, key))


def page_description(page_label: str, locale: str = "ko") -> str:
    if locale == "en":
        return PAGE_DESCRIPTIONS_EN.get(
            page_label, PAGE_BY_LABEL[page_label].description
        )
    return PAGE_BY_LABEL[page_label].description


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
        --p3-brand-100: {color["brand_100"]};
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
      .p3-skip-link {{
        position:absolute;
        left:-9999px;
        top:.5rem;
        z-index:99999;
        padding:.6rem .9rem;
        border-radius:{radius["sm"]};
        background:var(--p3-brand-950);
        color:white !important;
      }}
      .p3-skip-link:focus {{left:.75rem;}}
      :where(button, input, textarea, select, [role="button"], [tabindex]):focus-visible {{
        outline:3px solid #0EA5E9 !important;
        outline-offset:2px !important;
      }}
      button, [role="button"] {{min-height:2.5rem;}}
      [data-testid="stSidebarHeader"] {{
        min-height:2.7rem;
        height:2.7rem;
      }}
      [data-testid="stSidebarUserContent"] {{
        padding-top:0 !important;
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
      .p3-workspace-link {{
        display:inline-flex;
        align-items:center;
        justify-content:center;
        min-height:2.55rem;
        border:1px solid var(--p3-border);
        border-radius:var(--p3-radius-md);
        padding:.6rem .9rem;
        color:var(--p3-text) !important;
        background:var(--p3-surface);
        font-size:.86rem;
        font-weight:650;
        line-height:1;
        text-decoration:none !important;
        transition:border-color 120ms ease,background 120ms ease;
      }}
      .p3-workspace-link:hover {{
        border-color:var(--p3-brand-500);
        background:var(--p3-brand-100);
      }}
      .p3-workspace-link--stretch {{width:100%;}}
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
        .block-container {{
          padding-left:.8rem !important;
          padding-right:.8rem !important;
        }}
        [data-testid="stHorizontalBlock"] {{flex-wrap:wrap;}}
        [data-testid="column"] {{min-width:100% !important;}}
      }}
      @media (prefers-reduced-motion: reduce) {{
        *, *::before, *::after {{
          scroll-behavior:auto !important;
          animation-duration:.01ms !important;
          transition-duration:.01ms !important;
        }}
      }}
      @media (forced-colors: active) {{
        .p3-stage-badge, .p3-state-card, .p3-foundation-card {{
          border:1px solid CanvasText;
        }}
      }}
    </style>
    """
