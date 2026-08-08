"""Project readiness contract independent from LLM service initialization."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any, Callable

from backend.app.agent.prompt_registry import PromptRegistry
from backend.app.ingestion import DatasetWorkspace
from backend.app.mapping import MappingWorkspace
from backend.app.projects.registry import ProjectRegistry
from backend.app.schema_registry import SchemaRegistry
from evaluation.registry import EvaluationRegistry


GraphCounter = Callable[[str], dict[str, int]]


class ProjectReadinessService:
    """Evaluate immutable versions and runtime evidence before free queries."""

    def __init__(
        self,
        project_root: Path,
        projects: ProjectRegistry,
        schemas: SchemaRegistry,
        datasets: DatasetWorkspace,
        mappings: MappingWorkspace,
        *,
        graph_counter: GraphCounter | None = None,
    ):
        self.project_root = project_root.resolve()
        self.projects = projects
        self.schemas = schemas
        self.datasets = datasets
        self.mappings = mappings
        self.prompts = PromptRegistry(self.project_root)
        self.evaluations = EvaluationRegistry(
            self.project_root / "evaluation",
            self.project_root / "schemas",
        )
        self.graph_counter = graph_counter

    @staticmethod
    def _check(
        checks: dict[str, dict[str, Any]],
        name: str,
        passed: bool,
        detail: str,
        *,
        version: str | None = None,
    ) -> None:
        checks[name] = {
            "status": "PASS" if passed else "FAIL",
            "detail": detail,
            "version": version,
        }

    def _metrics(self, project_id: str) -> dict[str, Any] | None:
        paths = [
            self.project_root
            / "evaluation"
            / "projects"
            / project_id
            / "metrics.json",
        ]
        if project_id == "cip-dmd":
            paths.append(self.project_root / "evaluation" / "metrics.json")
        for path in paths:
            if path.exists():
                try:
                    return json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    return None
        return None

    def inspect(self, project_id: str) -> dict[str, Any]:
        project = self.projects.require(project_id)
        artifacts = self.projects.artifacts(project_id)
        uploads = self.datasets.list(project_id)
        checks: dict[str, dict[str, Any]] = {}

        source_artifact = artifacts.get("source")
        graph_projection = artifacts.get("graph_projection")
        graph_projection_verified = bool(
            graph_projection
            and graph_projection.get("status") == "verified"
            and (graph_projection.get("metadata") or {}).get(
                "dataset_version_id"
            )
        )
        source_version = (
            str(project.get("source_version") or "")
            or str((source_artifact or {}).get("version") or "")
        )
        source_connected = bool(source_version) and (
            project["source_type"] == "neo4j"
            and (
                "connector" in artifacts
                or graph_projection_verified
            )
            or project["source_type"] == "file"
            and (bool(uploads) or project_id == "cip-dmd")
        )
        source_detail = (
            (
                f"typed graph projection {graph_projection['version']}"
                if graph_projection_verified
                else f"{project['source_type']} source {source_version}"
            )
            if source_connected
            else "검증된 파일 업로드, Neo4j connector 또는 typed graph projection이 필요합니다."
        )
        self._check(
            checks,
            "source",
            source_connected,
            source_detail,
            version=source_version or None,
        )

        schema = None
        try:
            schema = self.schemas.load(project_id)
            schema_ok = (
                str(schema["version"]) == str(project.get("schema_version"))
                and str(schema.get("source_version")) == source_version
            )
            schema_detail = (
                "프로젝트 metadata와 schema/source 버전이 일치합니다."
                if schema_ok
                else "프로젝트 metadata와 schema/source 버전이 다릅니다."
            )
        except (KeyError, ValueError) as error:
            schema_ok = False
            schema_detail = str(error)
        self._check(
            checks,
            "schema",
            schema_ok,
            schema_detail,
            version=str(schema["version"]) if schema else None,
        )

        mapping_approved = False
        if project["source_type"] == "file":
            try:
                mapping = self.mappings.get(project_id)
                upload_ids = {
                    str(upload["upload_id"]) for upload in uploads
                }
                mapping_approved = (
                    str(
                        mapping.get("schema_version")
                        or (mapping.get("manifest") or {}).get("version")
                    )
                    == str(project.get("schema_version"))
                    and str(mapping.get("status")) == "approved"
                    and str(mapping.get("upload_id")) in upload_ids
                )
            except KeyError:
                mapping_approved = project_id == "cip-dmd"
            access_detail = (
                "승인된 파일→그래프 mapping이 연결되었습니다."
                if mapping_approved
                else "mapping 승인이 필요합니다."
            )
        else:
            connector = artifacts.get("connector")
            mapping_approved = bool(
                connector and connector["status"] == "verified"
            ) or graph_projection_verified
            access_detail = (
                (
                    "typed graph projection의 Dataset Version scope와 provider receipt가 검증되었습니다."
                    if graph_projection_verified
                    else "외부 Neo4j connector가 검증되었습니다."
                )
                if mapping_approved
                else "외부 Neo4j connector 또는 typed graph projection 검증이 필요합니다."
            )
        self._check(
            checks,
            "data_access",
            mapping_approved,
            access_detail,
        )

        integrity = artifacts.get("integrity")
        integrity_ok = (
            project_id == "cip-dmd"
            or bool(integrity and integrity["status"] == "verified")
        )
        self._check(
            checks,
            "integrity",
            integrity_ok,
            (
                "그래프 적재/연결 무결성이 검증되었습니다."
                if integrity_ok
                else "그래프 적재/연결 무결성 검증이 필요합니다."
            ),
            version=(integrity or {}).get("version"),
        )

        evaluation = None
        prompt = None
        try:
            evaluation = self.evaluations.load(project_id)
            evaluation_contract_ok = (
                schema_ok
                and str(evaluation["schema_version"])
                == str(schema["version"])
                and str(evaluation["source_version"]) == source_version
            )
        except (KeyError, ValueError):
            evaluation_contract_ok = False
        self._check(
            checks,
            "gold_contract",
            evaluation_contract_ok,
            (
                "Gold/Blind 질문과 snapshot 계약이 유효합니다."
                if evaluation_contract_ok
                else "현재 데이터·스키마 버전용 Gold 계약이 필요합니다."
            ),
            version=(
                str(evaluation["evaluation_version"])
                if evaluation
                else None
            ),
        )

        try:
            prompt = self.prompts.load(project_id)
            prompt_ok = (
                evaluation_contract_ok
                and prompt.schema_version == str(schema["version"])
                and prompt.source_version == source_version
                and prompt.evaluation_version
                == str(evaluation["evaluation_version"])
            )
        except (KeyError, ValueError):
            prompt_ok = False
        self._check(
            checks,
            "prompt",
            prompt_ok,
            (
                "schema·Gold·평가와 prompt 버전이 연결되었습니다."
                if prompt_ok
                else "현재 버전과 연결된 prompt manifest가 필요합니다."
            ),
            version=prompt.prompt_version if prompt else None,
        )

        metrics = self._metrics(project_id)
        evaluation_ok = bool(
            metrics
            and metrics.get("blind_evaluation_status") == "complete"
            and evaluation
            and str(metrics.get("evaluation_version"))
            == str(evaluation["evaluation_version"])
            and str(metrics.get("schema_version")) == str(schema["version"])
            and str(metrics.get("source_version")) == source_version
            and str(metrics.get("prompt_version"))
            == str(evaluation["prompt_version"])
        )
        self._check(
            checks,
            "evaluation",
            evaluation_ok,
            (
                "현재 lineage에 대한 Blind 평가가 완료되었습니다."
                if evaluation_ok
                else "현재 lineage의 Blind 평가 실행이 필요합니다."
            ),
            version=(
                str(metrics.get("evaluation_version"))
                if metrics
                else None
            ),
        )

        read_only = artifacts.get("read_only")
        read_only_ok = (
            project_id == "cip-dmd"
            or bool(read_only and read_only["status"] == "verified")
        )
        self._check(
            checks,
            "read_only",
            read_only_ok,
            (
                "READ 전용 실행 계약이 검증되었습니다."
                if read_only_ok
                else "READ 전용 차단 검증이 필요합니다."
            ),
            version=(read_only or {}).get("version"),
        )

        counts = {"nodes": 0, "relationships": 0}
        graph_error = None
        if self.graph_counter:
            try:
                counts = self.graph_counter(project_id)
            except Exception as error:  # readiness must remain observable
                graph_error = str(error)
        projection_counts = (
            (graph_projection or {}).get("metadata") or {}
        ).get("counts") or {}
        projected_nodes = int(
            projection_counts.get("nodes_written")
            or projection_counts.get("nodes")
            or 0
        )
        projected_relationships = int(
            projection_counts.get("relationships_written")
            or projection_counts.get("relationships")
            or 0
        )
        if graph_projection_verified and projected_nodes > 0:
            counts = {
                "nodes": projected_nodes,
                "relationships": projected_relationships,
            }
            graph_error = None
        graph_available = int(counts.get("nodes", 0)) > 0
        self._check(
            checks,
            "graph_runtime",
            graph_available,
            (
                f"{counts['nodes']} nodes / {counts['relationships']} rels"
                if graph_available
                else f"그래프 조회 불가: {graph_error or '노드 0개'}"
            ),
        )

        required = (
            "source",
            "schema",
            "data_access",
            "integrity",
            "gold_contract",
            "prompt",
            "evaluation",
            "read_only",
            "graph_runtime",
        )
        eligible_for_ready = all(
            checks[name]["status"] == "PASS" for name in required
        )
        can_query = project["status"] == "ready" and eligible_for_ready
        if can_query:
            next_action = "query"
        elif eligible_for_ready:
            next_action = "activate"
        elif checks["source"]["status"] == "FAIL":
            next_action = "connect" if project["source_type"] == "neo4j" else "upload"
        elif checks["schema"]["status"] == "FAIL":
            next_action = "map"
        elif checks["integrity"]["status"] == "FAIL":
            next_action = "load"
        elif (
            checks["gold_contract"]["status"] == "FAIL"
            or checks["prompt"]["status"] == "FAIL"
            or checks["evaluation"]["status"] == "FAIL"
        ):
            next_action = "evaluate"
        else:
            next_action = "validate"

        versions = {
            "source": source_version or None,
            "schema": str(schema["version"]) if schema else None,
            "prompt": prompt.prompt_version if prompt else None,
            "gold": (
                str(evaluation["evaluation_version"])
                if evaluation
                else None
            ),
            "evaluation": (
                str(metrics.get("evaluation_version"))
                if metrics
                else None
            ),
        }
        return {
            "project_id": project_id,
            "lifecycle_status": project["status"],
            "source_type": project["source_type"],
            "upload_count": len(uploads),
            "mapping_approved": mapping_approved,
            "schema_available": schema is not None,
            "node_count": int(counts.get("nodes", 0)),
            "relationship_count": int(counts.get("relationships", 0)),
            "can_query": can_query,
            "can_load": (
                project["source_type"] == "file"
                and mapping_approved
                and project["status"] == "mapping_review"
            ),
            "eligible_for_ready": eligible_for_ready,
            "next_action": next_action,
            "checks": checks,
            "versions": versions,
            "artifacts": artifacts,
            "transitions": self.projects.transition_history(project_id),
        }

    def promote(self, project_id: str) -> dict[str, Any]:
        report = self.inspect(project_id)
        if not report["eligible_for_ready"]:
            failed = [
                name
                for name, check in report["checks"].items()
                if check["status"] != "PASS"
            ]
            raise ValueError(
                "readiness gate를 통과하지 못했습니다: " + ", ".join(failed)
            )
        project = self.projects.require(project_id)
        if project["status"] != "evaluation_required":
            raise ValueError(
                "evaluation_required 상태에서만 ready로 승격할 수 있습니다."
            )
        versions = report["versions"]
        prompt = self.prompts.load(project_id)
        evaluation = self.evaluations.load(project_id)
        metrics = self._metrics(project_id) or {}
        metrics_fingerprint = hashlib.sha256(
            json.dumps(
                metrics,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        self.projects.record_artifact(
            project_id,
            "prompt",
            version=prompt.prompt_version,
            fingerprint=prompt.fingerprint,
            metadata={
                "schema_version": prompt.schema_version,
                "source_version": prompt.source_version,
                "evaluation_version": prompt.evaluation_version,
            },
        )
        self.projects.record_artifact(
            project_id,
            "gold",
            version=str(evaluation["evaluation_version"]),
            fingerprint=str(evaluation["fingerprint"]),
            metadata={
                "schema_version": evaluation["schema_version"],
                "source_version": evaluation["source_version"],
            },
        )
        self.projects.record_artifact(
            project_id,
            "evaluation",
            version=str(evaluation["evaluation_version"]),
            fingerprint=metrics_fingerprint,
            metadata={
                "blind_evaluation_status": metrics.get(
                    "blind_evaluation_status"
                ),
                "prompt_version": metrics.get("prompt_version"),
            },
        )
        self.projects.update(
            project_id,
            prompt_version=versions["prompt"],
            gold_version=versions["gold"],
            evaluation_version=versions["evaluation"],
        )
        self.projects.transition(
            project_id, "ready", reason="readiness_gate_passed"
        )
        return self.inspect(project_id)
