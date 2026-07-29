"""Stable service boundary used by CLI and Streamlit."""

from __future__ import annotations

from datetime import datetime, timezone
from inspect import Parameter, signature
import json
from pathlib import Path
from threading import Lock
from typing import Any, Callable
from uuid import uuid4

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

    def query(
        self,
        question: str,
        *,
        organization_id: str = "local",
        user_id: str = "anonymous",
        roles: tuple[str, ...] | list[str] = (),
        run_id: str | None = None,
        routing_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        resolved_run_id = run_id or str(uuid4())
        before_usage = self.usage_reader() if self.usage_reader else {}
        invoke_parameters = signature(self.agent.invoke).parameters
        accepts_context = (
            "run_id" in invoke_parameters
            or any(
                parameter.kind is Parameter.VAR_KEYWORD
                for parameter in invoke_parameters.values()
            )
        )
        resolved_thread_id = self._thread_id(resolved_run_id)
        state = (
            self.agent.invoke(
                question,
                run_id=resolved_run_id,
                thread_id=resolved_thread_id,
                organization_id=organization_id,
                user_id=user_id,
                roles=roles,
                routing_state=routing_state,
            )
            if accepts_context
            else self.agent.invoke(question)
        )
        result = format_agent_result(state)
        result["provider"] = self.provider
        result["run_id"] = resolved_run_id
        result["thread_id"] = state.get("run", {}).get(
            "thread_id", resolved_thread_id
        )
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

    def _thread_id(self, run_id: str) -> str:
        namespace = getattr(self.agent, "checkpoint_namespace", "text2cypher")
        return f"{run_id}:{namespace}"

    def run_state(self, run_id: str) -> dict[str, Any]:
        if not hasattr(self.agent, "state"):
            raise RuntimeError("Agent가 persistent state 조회를 지원하지 않습니다.")
        return self.agent.state(self._thread_id(run_id))

    def resume(self, run_id: str) -> dict[str, Any]:
        if not hasattr(self.agent, "resume"):
            raise RuntimeError("Agent가 persistent resume을 지원하지 않습니다.")
        thread_id = self._thread_id(run_id)
        result = format_agent_result(self.agent.resume(thread_id))
        result["provider"] = self.provider
        result["run_id"] = run_id
        result["thread_id"] = thread_id
        self._write_audit(result)
        return result

    def _write_audit(self, result: dict[str, Any]) -> None:
        if self.audit_log_path is None:
            return
        validation = result.get("validation", {})
        trace = validation.get("trace", [])
        event = {
            "run_id": result.get("run_id"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "question": result.get("question", ""),
            "cypher": result.get("cypher", ""),
            "provider": self.provider,
            "model_name": result.get("metadata", {}).get("model_name"),
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
            "routing_status": result.get("routing", {}).get("status"),
            "routing_confidence": result.get("routing", {}).get(
                "confidence"
            ),
            "routed_project_id": result.get("routing", {}).get(
                "selected_project_id"
            ),
            **result.get("usage", {}),
        }
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(event, ensure_ascii=False) + "\n"
        with self._audit_lock:
            with self.audit_log_path.open("a", encoding="utf-8") as stream:
                stream.write(serialized)
