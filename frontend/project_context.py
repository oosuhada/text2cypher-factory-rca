"""Project-scoped UI context helpers.

The functions operate on plain mutable mappings so they are testable without
Streamlit and can be reused by another frontend client.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, MutableMapping
from uuid import uuid4


PROJECT_CONTEXT_KEYS = (
    "conversations",
    "messages",
    "last_result",
    "active_conversation_id",
    "explorer_result",
    "explorer_search_result",
    "latest_project_upload",
    "project_load_result",
    "mapping_preview",
    "validated_connector",
    "query_filters",
    "evaluation_filters",
)


def empty_project_context() -> dict[str, Any]:
    return {
        "conversations": [],
        "messages": [],
        "last_result": None,
        "active_conversation_id": str(uuid4()),
        "explorer_result": None,
        "explorer_search_result": None,
        "latest_project_upload": None,
        "project_load_result": None,
        "mapping_preview": None,
        "validated_connector": None,
        "query_filters": {},
        "evaluation_filters": {},
    }


def snapshot_project_context(
    state: MutableMapping[str, Any],
) -> dict[str, Any]:
    defaults = empty_project_context()
    return {
        key: deepcopy(state.get(key, defaults[key]))
        for key in PROJECT_CONTEXT_KEYS
    }


def restore_project_context(
    state: MutableMapping[str, Any],
    context: dict[str, Any] | None,
) -> None:
    resolved = empty_project_context()
    if context:
        for key in PROJECT_CONTEXT_KEYS:
            if key in context:
                resolved[key] = deepcopy(context[key])
    for key, value in resolved.items():
        state[key] = value
