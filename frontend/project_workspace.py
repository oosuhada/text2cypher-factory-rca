"""Presentation contracts for the Home and Projects workspaces."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable


STATUS_PRESENTATION = {
    "draft": ("초안", "neutral", 5),
    "profiling": ("프로파일링", "info", 20),
    "mapping_review": ("매핑 검토", "warning", 40),
    "loading": ("적재 중", "info", 60),
    "validating": ("무결성 검증", "info", 72),
    "evaluation_required": ("평가 필요", "warning", 85),
    "ready": ("질의 가능", "success", 100),
    "failed": ("조치 필요", "error", 0),
    "archived": ("보관됨", "neutral", 100),
}

NEXT_ACTION_COPY = {
    "upload": ("데이터 등록", "Data Sources"),
    "connect": ("Neo4j 연결", "Data Sources"),
    "map": ("매핑 검토", "Pipeline"),
    "load": ("그래프 적재", "Pipeline"),
    "validate": ("무결성 확인", "Pipeline"),
    "evaluate": ("평가 실행", "Evaluations"),
    "activate": ("프로젝트 활성화", "Evaluations"),
    "query": ("질문 시작", "Query Studio"),
}


def status_presentation(status: str) -> dict[str, Any]:
    label, tone, progress = STATUS_PRESENTATION.get(
        status, (status, "neutral", 0)
    )
    return {
        "status": status,
        "label": label,
        "tone": tone,
        "progress": progress,
    }


def next_action_presentation(next_action: str) -> dict[str, str]:
    label, page = NEXT_ACTION_COPY.get(
        next_action, ("상태 확인", "Projects")
    )
    return {"label": label, "page": page}


def project_destination_page(readiness: dict[str, Any]) -> str:
    """Return the first useful workspace for a project's current readiness."""
    if readiness.get("can_query"):
        return "Query Studio"
    return next_action_presentation(
        str(readiness.get("next_action", ""))
    )["page"]


def filter_projects(
    projects: Iterable[dict[str, Any]],
    *,
    search: str = "",
    statuses: set[str] | None = None,
    favorites_only: bool = False,
) -> list[dict[str, Any]]:
    needle = search.strip().casefold()
    result = []
    for project in projects:
        haystack = " ".join(
            str(project.get(field, ""))
            for field in (
                "project_id",
                "name",
                "description",
                "industry",
                "domain_type",
                "owner",
            )
        ).casefold()
        if needle and needle not in haystack:
            continue
        if statuses and project.get("status") not in statuses:
            continue
        if favorites_only and not bool(project.get("favorite")):
            continue
        result.append(project)
    return sorted(
        result,
        key=lambda item: (
            not bool(item.get("favorite")),
            not bool(item.get("is_active")),
        ),
        reverse=False,
    )


def relative_updated_at(value: str, *, now: datetime | None = None) -> str:
    try:
        updated = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError):
        return "갱신 시각 없음"
    reference = now or datetime.now(updated.tzinfo)
    seconds = max(0, int((reference - updated).total_seconds()))
    if seconds < 60:
        return "방금 갱신"
    if seconds < 3600:
        return f"{seconds // 60}분 전"
    if seconds < 86400:
        return f"{seconds // 3600}시간 전"
    return f"{seconds // 86400}일 전"
