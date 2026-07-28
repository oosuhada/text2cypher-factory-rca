"""Streamlit session and project-context state contracts.

The core functions operate on mutable mappings so state transitions can be
tested without rendering the Streamlit application.
"""

from __future__ import annotations

from copy import deepcopy
import os
from pathlib import Path
from typing import Any, MutableMapping
from uuid import uuid4

import streamlit as st

from backend.app.conversations import ConversationStore
from frontend.conversation_history import (
    deduplicate_conversation_turns,
    upsert_conversation,
)
from frontend.project_context import (
    restore_project_context,
    snapshot_project_context,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def get_conversation_store(
    project_root: Path = PROJECT_ROOT,
) -> ConversationStore:
    configured_path = os.getenv("P3_CONVERSATION_DB_PATH", "").strip()
    store_path = (
        Path(configured_path).expanduser()
        if configured_path
        else project_root
        / "data"
        / "processed"
        / "conversations.sqlite3"
    )
    return ConversationStore(store_path)


def ensure_session_defaults(state: MutableMapping[str, Any]) -> None:
    """Install the complete cross-page state contract once per session."""

    state.setdefault("active_page", "Home")
    state.setdefault("preview_role", "Admin")
    state.setdefault("locale", "ko")
    state.setdefault("messages", [])
    state.setdefault("last_result", None)
    state.setdefault("conversations", [])
    state.setdefault("active_conversation_id", str(uuid4()))
    state.setdefault("explorer_result", None)
    state.setdefault("explorer_search_result", None)
    state.setdefault("explorer_selected_node_ids", [])
    state.setdefault("explorer_selected_relationship_ids", [])
    state.setdefault("explorer_expansion_history", [])
    state.setdefault("explorer_filters", {})
    state.setdefault("explorer_widget_revision", 0)
    state.setdefault("navigation_widget_revision", 0)
    state.setdefault("expert_reviews", {})
    state.setdefault("intake_record", None)
    state.setdefault("intake_approval_token", None)
    state.setdefault("active_project_id", "cip-dmd")
    state.setdefault("project_conversations", {})
    state.setdefault("conversation_loaded_projects", set())
    state.setdefault("query_filters", {})
    state.setdefault("evaluation_filters", {})


def sync_active_conversation_state(
    state: MutableMapping[str, Any],
    store: ConversationStore,
) -> None:
    messages = state["messages"]
    if not messages:
        return
    state["conversations"] = upsert_conversation(
        state["conversations"],
        conversation_id=state["active_conversation_id"],
        messages=messages,
        last_result=state.get("last_result"),
    )
    active = next(
        conversation
        for conversation in state["conversations"]
        if conversation["id"] == state["active_conversation_id"]
    )
    store.save(state.get("active_project_id", "cip-dmd"), active)


def load_project_conversations(
    state: MutableMapping[str, Any],
    store: ConversationStore,
    project_id: str,
) -> None:
    """Load and repair one project's persisted history exactly once."""

    if project_id in state["conversation_loaded_projects"]:
        return
    conversations = store.list(project_id, limit=12)
    for conversation in conversations:
        normalized = deduplicate_conversation_turns(
            conversation["messages"]
        )
        if normalized != conversation["messages"]:
            conversation["messages"] = normalized
            store.save(project_id, conversation)
    state["conversations"] = conversations
    if conversations and not state["messages"]:
        current = conversations[0]
        state["active_conversation_id"] = current["id"]
        state["messages"] = deepcopy(current["messages"])
        state["last_result"] = deepcopy(current.get("last_result"))
    state["conversation_loaded_projects"].add(project_id)


def initialize_session_state(
    state: MutableMapping[str, Any],
    store: ConversationStore,
) -> None:
    ensure_session_defaults(state)
    active_project_id = state["active_project_id"]
    load_project_conversations(state, store, active_project_id)
    normalized_messages = deduplicate_conversation_turns(state["messages"])
    if normalized_messages != state["messages"]:
        state["messages"] = normalized_messages
        sync_active_conversation_state(state, store)


def start_new_conversation_state(
    state: MutableMapping[str, Any],
    store: ConversationStore,
) -> None:
    sync_active_conversation_state(state, store)
    state["active_conversation_id"] = str(uuid4())
    state["messages"] = []
    state["last_result"] = None


def open_conversation_state(
    state: MutableMapping[str, Any],
    conversation_id: str,
) -> bool:
    conversation = next(
        (
            item
            for item in state["conversations"]
            if item["id"] == conversation_id
        ),
        None,
    )
    if conversation is None:
        return False
    state["active_conversation_id"] = conversation_id
    state["messages"] = deepcopy(conversation["messages"])
    state["last_result"] = deepcopy(conversation.get("last_result"))
    return True


def switch_project_state(
    state: MutableMapping[str, Any],
    project_id: str,
    store: ConversationStore,
) -> bool:
    """Atomically preserve the old project and restore the selected project."""

    previous = state.get("active_project_id", "cip-dmd")
    if previous == project_id:
        return False
    sync_active_conversation_state(state, store)
    state["project_conversations"][previous] = snapshot_project_context(state)
    if project_id not in state["conversation_loaded_projects"]:
        persisted = store.list(project_id, limit=12)
        context = None
        if persisted:
            context = {
                "conversations": persisted,
                "active_conversation_id": persisted[0]["id"],
                "messages": persisted[0]["messages"],
                "last_result": persisted[0].get("last_result"),
            }
        state["project_conversations"][project_id] = context
        state["conversation_loaded_projects"].add(project_id)
    restore_project_context(
        state,
        state["project_conversations"].get(project_id),
    )
    state["active_project_id"] = project_id
    return True


def initialize_session() -> None:
    initialize_session_state(st.session_state, get_conversation_store())


def sync_active_conversation() -> None:
    sync_active_conversation_state(
        st.session_state,
        get_conversation_store(),
    )


def start_new_conversation() -> None:
    start_new_conversation_state(
        st.session_state,
        get_conversation_store(),
    )


def open_conversation(conversation_id: str) -> bool:
    return open_conversation_state(st.session_state, conversation_id)

