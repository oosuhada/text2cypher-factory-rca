"""Backward-compatible imports for the Streamlit presentation layer."""

from backend.app.services.bootstrap import ServiceBundle, build_service_bundle

__all__ = ["ServiceBundle", "build_service_bundle"]
