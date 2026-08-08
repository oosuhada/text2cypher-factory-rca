#!/usr/bin/env python3
"""Validate the Stage 3-3 Tool Registry contract and built-in tools."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.tools import ToolContext, ToolError
from backend.app.tools.capabilities import build_project_tool_registry
from backend.app.tools.registry import TOOL_ERROR_TAXONOMY


def evaluate(root: Path = PROJECT_ROOT) -> dict:
    baseline = json.loads(
        (root / "evaluation" / "tool_registry_baseline.json").read_text(
            encoding="utf-8"
        )
    )
    with TemporaryDirectory() as directory:
        registry = build_project_tool_registry(
            project_root=root,
            project_id="cip-dmd",
            graph_query_handler=lambda payload, context: {
                "question": payload.question,
                "status": "success",
                "answer": "validated",
                "rows": [],
                "row_count": 0,
                "validation": {},
                "evidence": {},
            },
            search_docs_handler=lambda payload, context: {
                "project_id": context.project_id,
                "query": payload.query,
                "status": "success",
                "answer": "document evidence",
                "framework": "LlamaIndex",
                "framework_version": "0.14.23",
                "index_version": "llamaindex-rag-v1",
                "top_k": payload.top_k,
                "matches": [{"citation_id": "doc@1:p1"}],
                "citations": [{"citation_id": "doc@1:p1"}],
            },
            audit_log_path=Path(directory) / "tool_audit.jsonl",
            graph_timeout_seconds=5.0,
        )
        tools = {item["name"]: item for item in registry.list()}
        context = ToolContext(
            organization_id="factory-a",
            user_id="analyst-1",
            project_id="cip-dmd",
            run_id="tool-gate-run",
            roles=("Analyst",),
        )
        graph = registry.invoke(
            "graph_query_tool",
            {"question": "완제품 300002의 구성품을 보여줘."},
            context,
        )
        schema = registry.invoke(
            "schema_lookup_tool",
            {"include_properties": True, "include_scenarios": False},
            context,
        )
        permission_error = None
        try:
            registry.invoke(
                "etl_status_tool",
                {"include_artifacts": False},
                context,
            )
        except ToolError as error:
            permission_error = error

    tool_checks: dict[str, bool] = {}
    for name, expected in baseline["required_tools"].items():
        tool = tools.get(name)
        tool_checks[name] = bool(
            tool
            and tool["allowed_roles"] == expected["allowed_roles"]
            and tool["max_retries"] == expected["max_retries"]
            and "properties" in tool["input_schema"]
            and "properties" in tool["output_schema"]
        )
    trace_checks = {
        field: field in graph.trace
        for field in baseline["required_trace_fields"]
    }
    error_checks = {
        code: code in TOOL_ERROR_TAXONOMY
        for code in baseline["required_error_codes"]
    }
    checks = {
        "required_tools": all(tool_checks.values()),
        "graph_query_invocation": graph.output["status"] == "success",
        "schema_lookup_invocation": (
            schema.output["project_id"] == "cip-dmd"
            and bool(schema.output["node_labels"])
        ),
        "permission_denial": bool(
            permission_error
            and permission_error.code == "TOOL_PERMISSION_DENIED"
        ),
        "trace_contract": all(trace_checks.values()),
        "error_taxonomy": all(error_checks.values()),
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "baseline_version": baseline["version"],
        "tool_count": len(tools),
        "tools": sorted(tools),
        "checks": checks,
        "tool_checks": tool_checks,
        "trace_checks": trace_checks,
        "error_checks": error_checks,
    }


def main() -> int:
    report = evaluate()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
