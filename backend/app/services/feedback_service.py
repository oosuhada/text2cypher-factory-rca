"""Append-only domain-expert verification records for HITL review."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4


REVIEW_DECISIONS = ("verified", "disputed", "needs_followup")


class FeedbackService:
    """Persist bounded expert decisions without mutating query evidence."""

    def __init__(self, audit_log_path: Path):
        self.audit_log_path = audit_log_path
        self._lock = Lock()

    def record_review(
        self,
        *,
        question: str,
        cypher: str,
        query_status: str,
        provider: str,
        row_count: int,
        decision: str,
        reviewer: str = "domain-expert",
        note: str = "",
    ) -> dict[str, Any]:
        normalized_question = question.strip()
        normalized_cypher = cypher.strip()
        normalized_decision = decision.strip().lower()
        normalized_reviewer = reviewer.strip() or "domain-expert"
        normalized_note = note.strip()
        if not normalized_question:
            raise ValueError("검증할 질문은 공백일 수 없습니다.")
        if normalized_decision not in REVIEW_DECISIONS:
            raise ValueError(
                "decision은 verified, disputed, needs_followup 중 하나여야 합니다."
            )
        if len(normalized_question) > 2000:
            raise ValueError("질문은 2,000자 이하여야 합니다.")
        if len(normalized_cypher) > 20_000:
            raise ValueError("Cypher는 20,000자 이하여야 합니다.")
        if len(normalized_reviewer) > 120:
            raise ValueError("검토자 표시는 120자 이하여야 합니다.")
        if len(normalized_note) > 2000:
            raise ValueError("검토 의견은 2,000자 이하여야 합니다.")
        if row_count < 0:
            raise ValueError("row_count는 음수일 수 없습니다.")

        query_fingerprint = sha256(
            f"{normalized_question}\n{normalized_cypher}".encode("utf-8")
        ).hexdigest()
        event = {
            "review_id": str(uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "query_fingerprint": query_fingerprint,
            "question": normalized_question,
            "cypher": normalized_cypher,
            "query_status": query_status.strip() or "unknown",
            "provider": provider.strip() or "unknown",
            "row_count": row_count,
            "decision": normalized_decision,
            "reviewer": normalized_reviewer,
            "note": normalized_note,
        }
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(event, ensure_ascii=False) + "\n"
        with self._lock:
            with self.audit_log_path.open("a", encoding="utf-8") as stream:
                stream.write(serialized)
                stream.flush()
        return event

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        if not 1 <= limit <= 100:
            raise ValueError("limit은 1~100이어야 합니다.")
        return list(reversed(self._read_events()))[:limit]

    def _read_events(self) -> list[dict[str, Any]]:
        if not self.audit_log_path.exists():
            return []
        events: list[dict[str, Any]] = []
        with self._lock:
            lines = self.audit_log_path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                events.append(event)
        return events

    def summary(self, recent_limit: int = 10) -> dict[str, Any]:
        if not 1 <= recent_limit <= 100:
            raise ValueError("recent_limit은 1~100이어야 합니다.")
        events = self._read_events()
        counts = Counter(
            event.get("decision", "unknown") for event in events
        )
        reviewed_queries = {
            event.get("query_fingerprint")
            for event in events
            if event.get("query_fingerprint")
        }
        return {
            "total_reviews": len(events),
            "unique_queries_reviewed": len(reviewed_queries),
            "decision_counts": {
                decision: counts.get(decision, 0)
                for decision in REVIEW_DECISIONS
            },
            "recent": list(reversed(events))[:recent_limit],
            "storage": "append-only-jsonl",
        }
