"""Versioned, project-specific prompt and few-shot contracts."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import yaml

from backend.app.schema_registry import SchemaRegistry
from evaluation.registry import EvaluationRegistry


PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{2,62}$")


@dataclass(frozen=True)
class PromptContract:
    project_id: str
    prompt_version: str
    schema_version: str
    source_version: str
    evaluation_version: str
    schema_context: str
    examples_path: Path
    few_shot_count: int
    max_attempts: int
    timeout_seconds: float
    domain_validator: str
    template_sha256: str
    fingerprint: str

    def metadata(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "prompt_version": self.prompt_version,
            "schema_version": self.schema_version,
            "source_version": self.source_version,
            "evaluation_version": self.evaluation_version,
            "prompt_template_sha256": self.template_sha256,
            "prompt_fingerprint": self.fingerprint,
        }


class PromptRegistry:
    """Resolve one immutable prompt contract for each graph project."""

    def __init__(self, project_root: Path):
        self.project_root = project_root.resolve()
        self.root = self.project_root / "prompts"
        self.schemas = SchemaRegistry(self.project_root / "schemas")
        self.evaluations = EvaluationRegistry(
            self.project_root / "evaluation",
            self.project_root / "schemas",
        )

    def _path(self, project_id: str) -> Path:
        if not PROJECT_ID.fullmatch(project_id):
            raise ValueError("유효하지 않은 prompt project_id입니다.")
        return self.root / project_id / "manifest.yml"

    def _resolve_project_path(self, raw_path: str) -> Path:
        path = (self.project_root / raw_path).resolve()
        if (
            path != self.project_root
            and self.project_root not in path.parents
        ):
            raise ValueError("prompt 참조 경로가 프로젝트 범위를 벗어났습니다.")
        return path

    def load(self, project_id: str) -> PromptContract:
        path = self._path(project_id)
        if not path.exists():
            raise KeyError(f"prompt manifest가 없습니다: {project_id}")
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("prompt manifest는 객체여야 합니다.")
        document = deepcopy(payload)
        self.validate(document, expected_project_id=project_id)

        schema = self.schemas.load(project_id)
        evaluation = self.evaluations.load(project_id)
        examples_path = self._resolve_project_path(
            str(document["few_shot"]["questions"])
        )
        rules = [str(rule) for rule in document.get("rules") or []]
        context_parts = [
            self.schemas.context(project_id),
            (
                "Project isolation:\n"
                f"- Restrict graph matches to project_id '{project_id}'.\n"
                "- Never query or combine another project's records."
            ),
        ]
        if rules:
            context_parts.append(
                "Project-specific query rules:\n"
                + "\n".join(f"- {rule}" for rule in rules)
            )
        template_path = (
            self.project_root / "backend" / "app" / "agent" / "prompts.py"
        )
        template_sha256 = hashlib.sha256(template_path.read_bytes()).hexdigest()
        fingerprint_source = {
            "manifest": document,
            "schema": schema,
            "evaluation_fingerprint": evaluation["fingerprint"],
            "prompt_template_sha256": template_sha256,
        }
        fingerprint = hashlib.sha256(
            json.dumps(
                fingerprint_source,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return PromptContract(
            project_id=project_id,
            prompt_version=str(document["prompt_version"]),
            schema_version=str(document["schema_version"]),
            source_version=str(schema["source_version"]),
            evaluation_version=str(evaluation["evaluation_version"]),
            schema_context="\n\n".join(context_parts),
            examples_path=examples_path,
            few_shot_count=int(document["few_shot"].get("count", 6)),
            max_attempts=int(document.get("max_attempts", 3)),
            timeout_seconds=float(document.get("timeout_seconds", 30)),
            domain_validator=str(document.get("domain_validator", "schema")),
            template_sha256=template_sha256,
            fingerprint=fingerprint,
        )

    def validate(
        self,
        payload: dict[str, Any],
        *,
        expected_project_id: str | None = None,
    ) -> None:
        project_id = str(payload.get("project_id", ""))
        if expected_project_id and project_id != expected_project_id:
            raise ValueError("prompt manifest project_id가 다릅니다.")
        if not PROJECT_ID.fullmatch(project_id):
            raise ValueError("유효하지 않은 prompt project_id입니다.")
        for field in ("prompt_version", "schema_version"):
            if not str(payload.get(field, "")).strip():
                raise ValueError(f"prompt manifest {field}가 필요합니다.")
        schema = self.schemas.load(project_id)
        if str(schema["version"]) != str(payload["schema_version"]):
            raise ValueError("prompt schema_version과 실제 schema가 다릅니다.")
        evaluation = self.evaluations.load(project_id)
        if str(evaluation["prompt_version"]) != str(
            payload["prompt_version"]
        ):
            raise ValueError(
                "prompt_version과 evaluation prompt_version이 다릅니다."
            )
        few_shot = payload.get("few_shot")
        if not isinstance(few_shot, dict):
            raise ValueError("few_shot 설정이 필요합니다.")
        examples_path = self._resolve_project_path(
            str(few_shot.get("questions", ""))
        )
        if not examples_path.is_file():
            raise ValueError("few-shot 질문 파일이 없습니다.")
        expected_examples = Path(evaluation["gold"]["questions_path"]).resolve()
        if examples_path != expected_examples:
            raise ValueError(
                "few-shot 질문은 해당 프로젝트의 Gold 질의셋이어야 합니다."
            )
        count = int(few_shot.get("count", 6))
        if not 1 <= count <= 12:
            raise ValueError("few_shot.count는 1~12여야 합니다.")
        max_attempts = int(payload.get("max_attempts", 3))
        if not 1 <= max_attempts <= 5:
            raise ValueError("max_attempts는 1~5여야 합니다.")
        timeout_seconds = float(payload.get("timeout_seconds", 30))
        if not 1 <= timeout_seconds <= 120:
            raise ValueError("timeout_seconds는 1~120이어야 합니다.")
        if payload.get("domain_validator", "schema") not in {
            "schema",
            "cip-dmd",
            "equipment-history",
        }:
            raise ValueError("지원하지 않는 domain_validator입니다.")
