"""Stable service boundary used by CLI and Streamlit."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from threading import Lock
from typing import Any, Callable

from backend.app.agent.workflow import TextToCypherAgent

from .result_formatter import format_agent_result


class QueryService:
    def __init__(
        self,
        agent: TextToCypherAgent,
        audit_log_path: Path | None = None,
        provider: str = "unknown",
        usage_reader: Callable[[], dict[str, Any]] | None = None,
    ):
        self.agent = agent
        self.audit_log_path = audit_log_path
        self.provider = provider
        self.usage_reader = usage_reader
        self._audit_lock = Lock()

    def query(self, question: str) -> dict[str, Any]:
        before_usage = self.usage_reader() if self.usage_reader else {}
        result = format_agent_result(self.agent.invoke(question))
        result["provider"] = self.provider
        after_usage = self.usage_reader() if self.usage_reader else {}
        result["usage"] = {
            key: round(
                float(after_usage.get(key, 0))
                - float(before_usage.get(key, 0)),
                8,
            )
            for key in (
                "call_count",
                "input_tokens",
                "output_tokens",
                "total_tokens",
                "model_elapsed_ms",
                "estimated_cost_usd",
            )
        }
        self._write_audit(result)
        return result

    def _write_audit(self, result: dict[str, Any]) -> None:
        if self.audit_log_path is None:
            return
        validation = result.get("validation", {})
        trace = validation.get("trace", [])
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "question": result.get("question", ""),
            "provider": self.provider,
            "project_id": result.get("metadata", {}).get("project_id"),
            "schema_version": result.get("metadata", {}).get(
                "schema_version"
            ),
            "prompt_version": result.get("metadata", {}).get(
                "prompt_version"
            ),
            "status": result.get("status", "failed"),
            "row_count": result.get("row_count", 0),
            "attempts": validation.get("attempts", 0),
            "elapsed_ms": validation.get("elapsed_ms", 0),
            "corrected": any(
                step.get("step") == "correct_cypher" for step in trace
            ),
            "evidence_node_count": result.get("evidence", {}).get(
                "node_count", 0
            ),
            "evidence_relationship_count": result.get("evidence", {}).get(
                "relationship_count", 0
            ),
            "error_count": len(validation.get("errors", [])),
            "execution_verified": validation.get(
                "execution_verified", False
            ),
            **result.get("usage", {}),
        }
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(event, ensure_ascii=False) + "\n"
        with self._audit_lock:
            with self.audit_log_path.open("a", encoding="utf-8") as stream:
                stream.write(serialized)
