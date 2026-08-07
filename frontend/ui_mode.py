"""Runtime visibility contract for product, demo, and development UI modes."""

from __future__ import annotations

from enum import Enum
import os

from frontend.design_system import Role


class UiMode(str, Enum):
    PRODUCTION = "production"
    DEMO = "demo"
    DEVELOPMENT = "development"


DEFAULT_UI_MODE = UiMode.DEMO


def current_ui_mode() -> UiMode:
    raw = os.getenv("P3_UI_MODE", DEFAULT_UI_MODE.value).strip().lower()
    try:
        return UiMode(raw)
    except ValueError as error:
        allowed = ", ".join(mode.value for mode in UiMode)
        raise ValueError(f"P3_UI_MODE는 {allowed} 중 하나여야 합니다.") from error


def is_development(mode: UiMode | None = None) -> bool:
    return (mode or current_ui_mode()) is UiMode.DEVELOPMENT


def configured_role(mode: UiMode | None = None) -> Role:
    resolved_mode = mode or current_ui_mode()
    if resolved_mode is UiMode.DEVELOPMENT:
        return Role.ADMIN
    raw = os.getenv("P3_UI_ROLE", Role.DATA_STEWARD.value).strip()
    try:
        return Role(raw)
    except ValueError:
        return Role.DATA_STEWARD


def visible_workspace_labels(
    labels: tuple[str, ...],
    mode: UiMode | None = None,
) -> tuple[str, ...]:
    resolved_mode = mode or current_ui_mode()
    if resolved_mode is UiMode.DEVELOPMENT:
        return labels
    hidden = {"Approval Queue", "Admin"}
    return tuple(label for label in labels if label not in hidden)


def runtime_provider_and_model() -> tuple[str, str | None]:
    """Resolve server-managed generation settings without rendering controls."""

    provider = os.getenv("P3_API_PROVIDER", "auto").strip().lower() or "auto"
    model = os.getenv("P3_API_MODEL", "").strip() or None
    return provider, model


DEPLOYMENT_FORBIDDEN_COPY = (
    "OpenAI 키",
    "Gemini를 자동 사용",
    "Gold Question 데모",
    "역할 미리보기",
    "Stage 3-",
    "foundation",
    "실제 연결:",
    "transport",
)
