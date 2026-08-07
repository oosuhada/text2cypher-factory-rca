"""Shared Streamlit runtime resources and project paths."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from backend.app.services.data_intake_service import DataIntakeService
from backend.app.schema_registry import SchemaRegistry
from frontend.app_services import build_streamlit_service_bundle


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVICE_BUNDLE_VERSION = "2026-07-28-shared-api-v2"


@st.cache_resource(show_spinner=False)
def get_services(
    provider: str,
    model_name: str | None,
    bundle_version: str,
    project_id: str,
) -> Any:
    """Build and cache the project-scoped application service bundle."""

    del bundle_version
    schemas = SchemaRegistry(PROJECT_ROOT / "schemas")
    return build_streamlit_service_bundle(
        project_root=PROJECT_ROOT,
        provider=provider,
        model_name=model_name,
        project_id=project_id,
        schema_context=schemas.context(project_id),
    )


def clear_service_cache() -> None:
    """Close the active bundle before invalidating Streamlit's resource cache."""

    bundle = st.session_state.pop("_active_service_bundle", None)
    if bundle is not None:
        bundle.close()
    get_services.clear()


@st.cache_resource(show_spinner=False)
def get_data_intake_service() -> DataIntakeService:
    return DataIntakeService(PROJECT_ROOT)


@st.cache_data(show_spinner=False)
def get_reference_intake_archive() -> bytes:
    return DataIntakeService(PROJECT_ROOT).build_reference_archive()
