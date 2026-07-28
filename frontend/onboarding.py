"""Data onboarding and pipeline presentation helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


ONBOARDING_STEPS = (
    ("project", "프로젝트"),
    ("source", "데이터 소스"),
    ("profile", "프로파일"),
    ("mapping", "매핑"),
    ("load", "적재"),
    ("validate", "무결성"),
    ("evaluate", "평가"),
    ("ready", "질의 가능"),
)

STATUS_STEP = {
    "draft": "source",
    "profiling": "profile",
    "mapping_review": "mapping",
    "loading": "load",
    "validating": "validate",
    "evaluation_required": "evaluate",
    "ready": "ready",
    "failed": "source",
}

JOB_STATUS_COPY = {
    "queued": ("대기", "info"),
    "running": ("실행 중", "info"),
    "succeeded": ("완료", "success"),
    "failed": ("실패", "error"),
    "cancelled": ("취소", "warning"),
}


def onboarding_progress(status: str) -> dict[str, Any]:
    current_key = STATUS_STEP.get(status, "source")
    keys = [key for key, _label in ONBOARDING_STEPS]
    current_index = keys.index(current_key)
    return {
        "current": current_key,
        "current_index": current_index,
        "percent": int(current_index / (len(keys) - 1) * 100),
        "steps": [
            {
                "key": key,
                "label": label,
                "state": (
                    "complete"
                    if index < current_index
                    else "active"
                    if index == current_index
                    else "pending"
                ),
            }
            for index, (key, label) in enumerate(ONBOARDING_STEPS)
        ],
    }


def profile_quality_warnings(upload: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    for file in upload.get("files", []):
        if not file.get("columns"):
            warnings.append(f"{file.get('filename', 'unknown')}: 컬럼이 없습니다.")
            continue
        if not any(
            column.get("identity_candidate")
            for column in file.get("columns", [])
        ):
            warnings.append(
                f"{file['filename']}: 고유 ID 후보를 찾지 못했습니다."
            )
        for column in file.get("columns", []):
            null_count = int(
                column.get("missing_count", column.get("null_count", 0)) or 0
            )
            row_count = int(file.get("row_count", 0) or 0)
            if row_count and null_count / row_count >= 0.3:
                warnings.append(
                    f"{file['filename']}.{column['name']}: "
                    f"결측 {null_count}/{row_count}"
                )
    return warnings


def job_status_presentation(status: str) -> dict[str, str]:
    label, tone = JOB_STATUS_COPY.get(status, (status, "neutral"))
    return {"label": label, "tone": tone}


def job_elapsed_seconds(
    job: dict[str, Any], *, now: datetime | None = None
) -> float:
    """Return stable elapsed time for active and terminal persisted jobs."""

    started_at = job.get("started_at") or job.get("created_at")
    finished_at = job.get("finished_at")
    if not started_at:
        return 0.0
    start = datetime.fromisoformat(str(started_at))
    end = (
        datetime.fromisoformat(str(finished_at))
        if finished_at
        else now or datetime.now(timezone.utc)
    )
    return max(0.0, (end - start).total_seconds())


def format_elapsed(seconds: float) -> str:
    total = max(0, int(seconds))
    minutes, remainder = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}시간 {minutes}분"
    if minutes:
        return f"{minutes}분 {remainder}초"
    return f"{remainder}초"
