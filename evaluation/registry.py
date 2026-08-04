"""Versioned, project-specific Gold and Blind evaluation contracts."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import yaml

from backend.app.schema_registry import SchemaRegistry
from backend.app.security.read_only import validate_read_only


PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{2,62}$")


class EvaluationRegistry:
    def __init__(
        self,
        evaluation_root: Path,
        schema_root: Path,
    ):
        self.evaluation_root = evaluation_root.resolve()
        self.schema_registry = SchemaRegistry(schema_root)
        self.manifest_root = self.evaluation_root / "projects"

    def _manifest_path(self, project_id: str) -> Path:
        if not PROJECT_ID.fullmatch(project_id):
            raise ValueError("유효하지 않은 evaluation project_id입니다.")
        return self.manifest_root / project_id / "manifest.yml"

    def _resolve(self, value: str) -> Path:
        path = (self.evaluation_root / value).resolve()
        if (
            path != self.evaluation_root
            and self.evaluation_root not in path.parents
        ):
            raise ValueError("평가 파일 경로가 evaluation 범위를 벗어났습니다.")
        return path

    @staticmethod
    def _read_questions(path: Path) -> list[dict[str, Any]]:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise ValueError(f"평가 질문 파일은 객체여야 합니다: {path}")
        questions = document.get("questions")
        if not isinstance(questions, list):
            raise ValueError(f"questions 배열이 필요합니다: {path}")
        return questions

    def load(self, project_id: str) -> dict[str, Any]:
        path = self._manifest_path(project_id)
        if not path.exists():
            raise KeyError(f"평가 manifest가 없습니다: {project_id}")
        manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise ValueError("평가 manifest는 객체여야 합니다.")
        self.validate(manifest, expected_project_id=project_id)
        result = deepcopy(manifest)
        result["manifest_path"] = str(path)
        for split in ("gold", "blind"):
            result[split]["questions_path"] = str(
                self._resolve(result[split]["questions"])
            )
            result[split]["snapshots_path"] = str(
                self._resolve(result[split]["snapshots"])
            )
        result["fingerprint"] = self.fingerprint(manifest)
        return result

    def validate(
        self,
        manifest: dict[str, Any],
        *,
        expected_project_id: str | None = None,
    ) -> None:
        project_id = str(manifest.get("project_id", ""))
        if expected_project_id and project_id != expected_project_id:
            raise ValueError("평가 manifest project_id가 다릅니다.")
        if not PROJECT_ID.fullmatch(project_id):
            raise ValueError("유효하지 않은 evaluation project_id입니다.")
        for field in (
            "evaluation_version",
            "schema_version",
            "source_version",
            "prompt_version",
            "dataset",
        ):
            if not str(manifest.get(field, "")).strip():
                raise ValueError(f"평가 manifest {field}가 필요합니다.")
        schema = self.schema_registry.load(project_id)
        if str(schema["version"]) != str(manifest["schema_version"]):
            raise ValueError("평가 schema_version과 실제 schema가 다릅니다.")
        if str(schema.get("source_version")) != str(
            manifest["source_version"]
        ):
            raise ValueError("평가 source_version과 실제 schema가 다릅니다.")

        split_questions: dict[str, list[dict[str, Any]]] = {}
        for split in ("gold", "blind"):
            config = manifest.get(split)
            if not isinstance(config, dict):
                raise ValueError(f"{split} 평가 설정이 필요합니다.")
            questions_path = self._resolve(str(config.get("questions", "")))
            snapshots_path = self._resolve(
                str(config.get("snapshots", ""))
            )
            if not questions_path.exists():
                raise ValueError(f"{split} 질문 파일이 없습니다.")
            if not snapshots_path.is_dir():
                raise ValueError(f"{split} snapshot 폴더가 없습니다.")
            questions = self._read_questions(questions_path)
            minimum = int(config.get("min_questions", 0))
            maximum = int(config.get("max_questions", 10_000))
            if not minimum <= len(questions) <= maximum:
                raise ValueError(
                    f"{split} 질문 수가 범위를 벗어났습니다: "
                    f"{len(questions)} not in {minimum}..{maximum}"
                )
            ids = [str(question.get("id", "")) for question in questions]
            if any(not question_id for question_id in ids):
                raise ValueError(f"{split} 질문 ID가 비어 있습니다.")
            if len(ids) != len(set(ids)):
                raise ValueError(f"{split} 질문 ID가 중복됩니다.")
            for question in questions:
                expected_status = str(
                    question.get("expected_status", "success")
                )
                cypher = question.get("gold_cypher")
                if expected_status in {"success", "empty"}:
                    if not cypher:
                        raise ValueError(
                            f"{split}/{question['id']} Gold Cypher가 없습니다."
                        )
                    errors = validate_read_only(str(cypher))
                    if errors:
                        raise ValueError(
                            f"{split}/{question['id']}가 READ 전용이 아닙니다: "
                            f"{errors}"
                        )
                    snapshot_path = (
                        snapshots_path / f"{question['id']}.json"
                    )
                    if not snapshot_path.exists():
                        raise ValueError(
                            f"{split}/{question['id']} snapshot이 없습니다."
                        )
                    snapshot = json.loads(
                        snapshot_path.read_text(encoding="utf-8")
                    )
                    if snapshot.get("question_id") != question["id"]:
                        raise ValueError(
                            f"{split}/{question['id']} snapshot ID가 다릅니다."
                        )
            split_questions[split] = questions

        gold_text = {
            str(question.get("question", "")).strip()
            for question in split_questions["gold"]
        }
        blind_text = {
            str(question.get("question", "")).strip()
            for question in split_questions["blind"]
        }
        overlap = gold_text & blind_text
        if overlap:
            raise ValueError(
                f"Gold와 Blind 질문이 겹칩니다: {sorted(overlap)}"
            )
        policy = manifest.get("evaluation_policy") or {}
        if policy.get("semantic") != "alias_agnostic_value_match":
            raise ValueError("semantic 평가 정책을 명시해야 합니다.")
        if policy.get("strict") != "exact_contract_match":
            raise ValueError("strict 평가 정책을 명시해야 합니다.")

    def fingerprint(self, manifest: dict[str, Any]) -> str:
        digest = hashlib.sha256()
        stable_manifest = {
            key: value
            for key, value in manifest.items()
            if key != "manifest_path"
        }
        digest.update(
            json.dumps(
                stable_manifest,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        for split in ("gold", "blind"):
            config = manifest[split]
            question_path = self._resolve(config["questions"])
            digest.update(question_path.read_bytes())
            snapshots = self._resolve(config["snapshots"])
            for path in sorted(snapshots.glob("*.json")):
                digest.update(path.name.encode("utf-8"))
                digest.update(path.read_bytes())
        return digest.hexdigest()
