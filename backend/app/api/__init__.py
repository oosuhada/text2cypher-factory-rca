"""HTTP API for product frontends and external integrations."""

from .main import app, create_app

__all__ = ["app", "create_app"]
