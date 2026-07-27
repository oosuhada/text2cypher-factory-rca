"""Pure helpers for Streamlit's session-scoped conversation history."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any


MAX_SESSION_CONVERSATIONS = 12


def conversation_title(messages: list[dict[str, Any]]) -> str:
    """Build a compact title from the first user question."""

    question = next(
        (
            str(message.get("content", "")).strip()
            for message in messages
            if message.get("role") == "user"
        ),
        "새 대화",
    )
    return question if len(question) <= 34 else f"{question[:33]}…"


def upsert_conversation(
    conversations: list[dict[str, Any]],
    *,
    conversation_id: str,
    messages: list[dict[str, Any]],
    last_result: dict[str, Any] | None,
    created_at: str | None = None,
    updated_at: str | None = None,
) -> list[dict[str, Any]]:
    """Return newest-first session history without sharing mutable messages."""

    previous = next(
        (
            conversation
            for conversation in conversations
            if conversation.get("id") == conversation_id
        ),
        None,
    )
    timestamp = updated_at or datetime.now(timezone.utc).isoformat()
    item = {
        "id": conversation_id,
        "title": conversation_title(messages),
        "created_at": (
            created_at
            or (previous or {}).get("created_at")
            or timestamp
        ),
        "updated_at": timestamp,
        "messages": deepcopy(messages),
        "last_result": deepcopy(last_result),
    }
    return [
        item,
        *[
            deepcopy(conversation)
            for conversation in conversations
            if conversation.get("id") != conversation_id
        ],
    ][:MAX_SESSION_CONVERSATIONS]
