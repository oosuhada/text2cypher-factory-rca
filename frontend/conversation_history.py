"""Pure helpers for Streamlit's session-scoped conversation history."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from typing import Any


MAX_SESSION_CONVERSATIONS = 12


def _turn_fingerprint(
    user_message: dict[str, Any],
    assistant_message: dict[str, Any],
) -> str:
    response = assistant_message.get("content", {})
    if not isinstance(response, dict):
        response = {"answer": response}
    stable_response = {
        key: response.get(key)
        for key in (
            "question",
            "answer",
            "status",
            "cypher",
            "rows",
            "row_count",
            "evidence",
            "provider",
        )
    }
    return json.dumps(
        {
            "question": user_message.get("content"),
            "response": stable_response,
        },
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )


def deduplicate_conversation_turns(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Repair a conversation dominated by repeated identical turns.

    A short, intentional re-run remains part of the history. Repair only
    activates for a large conversation where repeated semantic turns account
    for at least two thirds of all paired turns—the shape produced by the
    former integration-test persistence leak. Volatile runtime fields such as
    latency and token usage are intentionally ignored when comparing turns.
    """

    if len(messages) < 40:
        return deepcopy(messages)

    fingerprints: list[str] = []
    scan_index = 0
    while scan_index + 1 < len(messages):
        message = messages[scan_index]
        next_message = messages[scan_index + 1]
        if (
            message.get("role") == "user"
            and isinstance(next_message, dict)
            and next_message.get("role") == "assistant"
        ):
            fingerprints.append(_turn_fingerprint(message, next_message))
            scan_index += 2
            continue
        scan_index += 1
    if not fingerprints or len(set(fingerprints)) * 3 > len(fingerprints):
        return deepcopy(messages)

    normalized: list[dict[str, Any]] = []
    seen_turns: set[str] = set()
    index = 0
    while index < len(messages):
        message = messages[index]
        next_message = (
            messages[index + 1] if index + 1 < len(messages) else None
        )
        if (
            message.get("role") == "user"
            and isinstance(next_message, dict)
            and next_message.get("role") == "assistant"
        ):
            fingerprint = _turn_fingerprint(message, next_message)
            if fingerprint not in seen_turns:
                normalized.extend(
                    (deepcopy(message), deepcopy(next_message))
                )
                seen_turns.add(fingerprint)
            index += 2
            continue
        normalized.append(deepcopy(message))
        index += 1
    return normalized


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

    normalized_messages = deduplicate_conversation_turns(messages)
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
        "title": conversation_title(normalized_messages),
        "created_at": (
            created_at
            or (previous or {}).get("created_at")
            or timestamp
        ),
        "updated_at": timestamp,
        "messages": normalized_messages,
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
