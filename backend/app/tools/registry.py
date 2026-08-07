"""Validated, permission-aware, audited tool execution registry."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from threading import Lock
from time import perf_counter, sleep
from typing import Any, Callable, Generic, TypeVar
from uuid import uuid4

from pydantic import BaseModel, ValidationError


InputModel = TypeVar("InputModel", bound=BaseModel)
OutputModel = TypeVar("OutputModel", bound=BaseModel)


TOOL_ERROR_TAXONOMY = {
    "TOOL_INPUT_INVALID": {"category": "validation", "retryable": False},
    "TOOL_OUTPUT_INVALID": {"category": "contract", "retryable": False},
    "TOOL_PERMISSION_DENIED": {"category": "authorization", "retryable": False},
    "TOOL_TIMEOUT": {"category": "timeout", "retryable": True},
    "TOOL_NOT_FOUND": {"category": "configuration", "retryable": False},
    "TOOL_DUPLICATE": {"category": "configuration", "retryable": False},
    "TOOL_EXECUTION_FAILED": {"category": "execution", "retryable": True},
}


class ToolError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        retryable: bool | None = None,
    ):
        taxonomy = TOOL_ERROR_TAXONOMY.get(
            code,
            {"category": "unknown", "retryable": False},
        )
        self.code = code
        self.category = str(taxonomy["category"])
        self.retryable = (
            bool(taxonomy["retryable"])
            if retryable is None
            else bool(retryable)
        )
        self.details = details or {}
        super().__init__(message)

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "category": self.category,
            "message": str(self),
            "retryable": self.retryable,
            "details": self.details,
        }


@dataclass(frozen=True)
class ToolContext:
    organization_id: str
    user_id: str
    project_id: str
    run_id: str
    roles: tuple[str, ...] = ()
    routing: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolInvocation:
    invocation_id: str
    tool_name: str
    output: dict[str, Any]
    trace: dict[str, Any]


@dataclass(frozen=True)
class ToolSpec(Generic[InputModel, OutputModel]):
    name: str
    description: str
    input_model: type[InputModel]
    output_model: type[OutputModel]
    handler: Callable[[InputModel, ToolContext], OutputModel | dict[str, Any]]
    allowed_roles: frozenset[str] = frozenset()
    timeout_seconds: float = 30.0
    max_retries: int = 0
    retry_backoff_seconds: float = 0.0

    def __post_init__(self) -> None:
        if not self.name or not self.name.replace("_", "").isalnum():
            raise ValueError("Tool name must be an alphanumeric snake_case value.")
        if self.timeout_seconds <= 0:
            raise ValueError("Tool timeout_seconds must be positive.")
        if self.max_retries < 0:
            raise ValueError("Tool max_retries cannot be negative.")
        if self.retry_backoff_seconds < 0:
            raise ValueError("Tool retry_backoff_seconds cannot be negative.")


class ToolRegistry:
    def __init__(self, audit_log_path: Path | None = None):
        self.audit_log_path = audit_log_path
        self._tools: dict[str, ToolSpec[Any, Any]] = {}
        self._lock = Lock()
        self._audit_lock = Lock()

    def register(self, spec: ToolSpec[Any, Any]) -> None:
        with self._lock:
            if spec.name in self._tools:
                raise ToolError(
                    "TOOL_DUPLICATE",
                    f"이미 등록된 Tool입니다: {spec.name}",
                    details={"tool_name": spec.name},
                )
            self._tools[spec.name] = spec

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            specs = list(self._tools.values())
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "allowed_roles": sorted(spec.allowed_roles),
                "timeout_seconds": spec.timeout_seconds,
                "max_retries": spec.max_retries,
                "input_schema": spec.input_model.model_json_schema(),
                "output_schema": spec.output_model.model_json_schema(),
            }
            for spec in sorted(specs, key=lambda item: item.name)
        ]

    def get(self, name: str) -> ToolSpec[Any, Any]:
        with self._lock:
            spec = self._tools.get(name)
        if spec is None:
            raise ToolError(
                "TOOL_NOT_FOUND",
                f"등록되지 않은 Tool입니다: {name}",
                details={"tool_name": name},
            )
        return spec

    @staticmethod
    def _input_sha256(payload: dict[str, Any]) -> str:
        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    def _check_permission(spec: ToolSpec[Any, Any], context: ToolContext) -> None:
        if not spec.allowed_roles:
            return
        if set(context.roles).isdisjoint(spec.allowed_roles):
            raise ToolError(
                "TOOL_PERMISSION_DENIED",
                f"{spec.name} Tool을 실행할 권한이 없습니다.",
                details={
                    "required_roles": sorted(spec.allowed_roles),
                    "actual_roles": sorted(context.roles),
                },
            )

    @staticmethod
    def _validate_input(
        spec: ToolSpec[Any, Any], payload: dict[str, Any]
    ) -> BaseModel:
        try:
            return spec.input_model.model_validate(payload)
        except ValidationError as error:
            raise ToolError(
                "TOOL_INPUT_INVALID",
                f"{spec.name} Tool 입력 검증에 실패했습니다.",
                details={"errors": error.errors(include_url=False)},
            ) from error

    @staticmethod
    def _validate_output(
        spec: ToolSpec[Any, Any], output: BaseModel | dict[str, Any]
    ) -> BaseModel:
        try:
            return spec.output_model.model_validate(output)
        except ValidationError as error:
            raise ToolError(
                "TOOL_OUTPUT_INVALID",
                f"{spec.name} Tool 출력 검증에 실패했습니다.",
                details={"errors": error.errors(include_url=False)},
            ) from error

    @staticmethod
    def _execute_once(
        spec: ToolSpec[Any, Any],
        validated_input: BaseModel,
        context: ToolContext,
    ) -> BaseModel | dict[str, Any]:
        executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix=f"tool-{spec.name}",
        )
        future = executor.submit(spec.handler, validated_input, context)
        try:
            return future.result(timeout=spec.timeout_seconds)
        except FutureTimeout as error:
            future.cancel()
            raise ToolError(
                "TOOL_TIMEOUT",
                f"{spec.name} Tool이 {spec.timeout_seconds:.2f}초 안에 완료되지 않았습니다.",
                details={"timeout_seconds": spec.timeout_seconds},
            ) from error
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def invoke(
        self,
        name: str,
        payload: dict[str, Any],
        context: ToolContext,
    ) -> ToolInvocation:
        spec = self.get(name)
        invocation_id = str(uuid4())
        started = perf_counter()
        validated_input: BaseModel | None = None
        attempts = 0
        last_error: ToolError | None = None

        try:
            self._check_permission(spec, context)
            validated_input = self._validate_input(spec, payload)
            while attempts <= spec.max_retries:
                attempts += 1
                try:
                    raw_output = self._execute_once(
                        spec,
                        validated_input,
                        context,
                    )
                    validated_output = self._validate_output(spec, raw_output)
                    elapsed_ms = int((perf_counter() - started) * 1000)
                    trace = {
                        "invocation_id": invocation_id,
                        "tool": spec.name,
                        "status": "success",
                        "attempts": attempts,
                        "elapsed_ms": elapsed_ms,
                        "organization_id": context.organization_id,
                        "user_id": context.user_id,
                        "project_id": context.project_id,
                        "run_id": context.run_id,
                        "roles": list(context.roles),
                        "input_sha256": self._input_sha256(payload),
                        "error": None,
                    }
                    self._write_audit(trace)
                    return ToolInvocation(
                        invocation_id=invocation_id,
                        tool_name=spec.name,
                        output=validated_output.model_dump(mode="json"),
                        trace=trace,
                    )
                except ToolError as error:
                    last_error = error
                except Exception as error:
                    last_error = ToolError(
                        "TOOL_EXECUTION_FAILED",
                        f"{spec.name} Tool 실행에 실패했습니다: {error}",
                        details={"exception_type": type(error).__name__},
                    )

                if (
                    last_error is None
                    or not last_error.retryable
                    or attempts > spec.max_retries
                ):
                    break
                if spec.retry_backoff_seconds:
                    sleep(spec.retry_backoff_seconds * attempts)

            assert last_error is not None
            raise last_error
        except ToolError as error:
            elapsed_ms = int((perf_counter() - started) * 1000)
            trace = {
                "invocation_id": invocation_id,
                "tool": spec.name,
                "status": "failed",
                "attempts": attempts,
                "elapsed_ms": elapsed_ms,
                "organization_id": context.organization_id,
                "user_id": context.user_id,
                "project_id": context.project_id,
                "run_id": context.run_id,
                "roles": list(context.roles),
                "input_sha256": self._input_sha256(payload),
                "error": error.as_dict(),
            }
            self._write_audit(trace)
            error.details = {**error.details, "tool_trace": trace}
            raise

    def _write_audit(self, event: dict[str, Any]) -> None:
        if self.audit_log_path is None:
            return
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "tool_invocation",
            **event,
        }
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._audit_lock:
            with self.audit_log_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
