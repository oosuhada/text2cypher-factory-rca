"""Streamlit service composition through the shared FastAPI boundary."""

import os
from pathlib import Path
from typing import Any

from backend.app.services.bootstrap import ServiceBundle, build_service_bundle
from frontend.api_client import (
    ApiRequestError,
    ApiServiceBundle,
    FactoryGraphApiClient,
)


def build_streamlit_service_bundle(
    project_root: Path,
    provider: str = "auto",
    model_name: str | None = None,
    *,
    transport: str | None = None,
    project_id: str = "cip-dmd",
    schema_context: str | None = None,
) -> ServiceBundle | ApiServiceBundle:
    """Prefer FastAPI while preserving an explicit local-service fallback."""

    resolved_transport = (
        transport or os.getenv("P3_STREAMLIT_TRANSPORT", "auto")
    ).strip().lower()
    if resolved_transport not in {"auto", "api", "direct"}:
        raise ValueError(
            "P3_STREAMLIT_TRANSPORT는 auto, api, direct 중 하나여야 합니다."
        )
    # An explicit model choice in the Streamlit UI must not be silently
    # ignored by an already-running API configured with another provider.
    # Operators can still force centralized API mode with
    # P3_STREAMLIT_TRANSPORT=api.
    if resolved_transport == "auto" and provider != "auto":
        resolved_transport = "direct"
    if resolved_transport in {"auto", "api"}:
        api = FactoryGraphApiClient()
        if api.live():
            try:
                return ApiServiceBundle(api, project_id=project_id)
            except ApiRequestError:
                api.close()
                if resolved_transport == "api":
                    raise
        else:
            api.close()
        if resolved_transport == "api":
            raise RuntimeError(
                "FastAPI가 준비되지 않았습니다. P3_API_BASE_URL과 "
                "/api/v1/health/live를 확인하세요."
            )
    bundle = build_service_bundle(
        project_root=project_root,
        provider=provider,
        model_name=model_name,
        project_id=project_id,
        schema_context=schema_context,
    )
    setattr(bundle, "transport", "direct")
    return bundle


__all__: list[str] = [
    "ApiServiceBundle",
    "ServiceBundle",
    "build_service_bundle",
    "build_streamlit_service_bundle",
]
