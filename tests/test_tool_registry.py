from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from time import sleep
import unittest

from pydantic import BaseModel, ConfigDict, Field

from backend.app.tools import (
    ToolContext,
    ToolError,
    ToolRegistry,
    ToolSpec,
)


class EchoInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str = Field(min_length=1)


class EchoOutput(BaseModel):
    value: str
    attempts: int = 1


class ToolRegistryTest(unittest.TestCase):
    def context(self, *roles: str) -> ToolContext:
        return ToolContext(
            organization_id="factory-a",
            user_id="analyst-1",
            project_id="cip-dmd",
            run_id="run-1",
            roles=roles,
        )

    def test_input_schema_failure_blocks_handler(self):
        called = []
        registry = ToolRegistry()
        registry.register(
            ToolSpec(
                name="echo_tool",
                description="Echo",
                input_model=EchoInput,
                output_model=EchoOutput,
                handler=lambda payload, context: called.append(payload) or {
                    "value": payload.value
                },
            )
        )

        with self.assertRaises(ToolError) as captured:
            registry.invoke(
                "echo_tool",
                {"value": "ok", "unexpected": True},
                self.context(),
            )

        self.assertEqual(captured.exception.code, "TOOL_INPUT_INVALID")
        self.assertFalse(captured.exception.retryable)
        self.assertEqual(called, [])

    def test_permission_failure_never_calls_handler(self):
        called = []
        registry = ToolRegistry()
        registry.register(
            ToolSpec(
                name="admin_tool",
                description="Admin",
                input_model=EchoInput,
                output_model=EchoOutput,
                handler=lambda payload, context: called.append(payload) or {
                    "value": payload.value
                },
                allowed_roles=frozenset({"Admin"}),
            )
        )

        with self.assertRaises(ToolError) as captured:
            registry.invoke(
                "admin_tool",
                {"value": "secret"},
                self.context("Viewer"),
            )

        self.assertEqual(captured.exception.code, "TOOL_PERMISSION_DENIED")
        self.assertEqual(called, [])

    def test_retry_recovers_retryable_execution_failure(self):
        attempts = 0

        def flaky(payload, context):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise RuntimeError("temporary dependency error")
            return {"value": payload.value, "attempts": attempts}

        registry = ToolRegistry()
        registry.register(
            ToolSpec(
                name="retry_tool",
                description="Retry",
                input_model=EchoInput,
                output_model=EchoOutput,
                handler=flaky,
                max_retries=1,
            )
        )
        invocation = registry.invoke(
            "retry_tool",
            {"value": "recovered"},
            self.context(),
        )

        self.assertEqual(invocation.output["value"], "recovered")
        self.assertEqual(invocation.trace["attempts"], 2)
        self.assertEqual(attempts, 2)

    def test_timeout_has_stable_error_taxonomy(self):
        registry = ToolRegistry()
        registry.register(
            ToolSpec(
                name="slow_tool",
                description="Slow",
                input_model=EchoInput,
                output_model=EchoOutput,
                handler=lambda payload, context: (
                    sleep(0.05) or {"value": payload.value}
                ),
                timeout_seconds=0.001,
            )
        )

        with self.assertRaises(ToolError) as captured:
            registry.invoke(
                "slow_tool",
                {"value": "wait"},
                self.context(),
            )

        self.assertEqual(captured.exception.code, "TOOL_TIMEOUT")
        self.assertEqual(captured.exception.category, "timeout")
        self.assertTrue(captured.exception.retryable)

    def test_output_validation_failure_is_not_retried(self):
        called = 0

        def invalid_output(payload, context):
            nonlocal called
            called += 1
            return {"attempts": called}

        registry = ToolRegistry()
        registry.register(
            ToolSpec(
                name="invalid_output_tool",
                description="Invalid output",
                input_model=EchoInput,
                output_model=EchoOutput,
                handler=invalid_output,
                max_retries=2,
            )
        )

        with self.assertRaises(ToolError) as captured:
            registry.invoke(
                "invalid_output_tool",
                {"value": "x"},
                self.context(),
            )

        self.assertEqual(captured.exception.code, "TOOL_OUTPUT_INVALID")
        self.assertEqual(called, 1)

    def test_audit_trace_is_reproducible_and_does_not_store_raw_input(self):
        with TemporaryDirectory() as directory:
            audit = Path(directory) / "tool_audit.jsonl"
            registry = ToolRegistry(audit_log_path=audit)
            registry.register(
                ToolSpec(
                    name="echo_tool",
                    description="Echo",
                    input_model=EchoInput,
                    output_model=EchoOutput,
                    handler=lambda payload, context: {"value": payload.value},
                )
            )
            first = registry.invoke(
                "echo_tool",
                {"value": "sensitive value"},
                self.context("Analyst"),
            )
            second = registry.invoke(
                "echo_tool",
                {"value": "sensitive value"},
                self.context("Analyst"),
            )
            events = [
                json.loads(line)
                for line in audit.read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual(len(events), 2)
        self.assertEqual(
            first.trace["input_sha256"], second.trace["input_sha256"]
        )
        self.assertNotIn("sensitive value", json.dumps(events, ensure_ascii=False))
        self.assertEqual(events[0]["project_id"], "cip-dmd")
        self.assertEqual(events[0]["run_id"], "run-1")
        self.assertEqual(events[0]["status"], "success")

    def test_registry_list_exposes_input_and_output_contracts(self):
        registry = ToolRegistry()
        registry.register(
            ToolSpec(
                name="echo_tool",
                description="Echo",
                input_model=EchoInput,
                output_model=EchoOutput,
                handler=lambda payload, context: {"value": payload.value},
            )
        )
        tools = registry.list()

        self.assertEqual([tool["name"] for tool in tools], ["echo_tool"])
        self.assertIn("properties", tools[0]["input_schema"])
        self.assertIn("properties", tools[0]["output_schema"])


if __name__ == "__main__":
    unittest.main()
