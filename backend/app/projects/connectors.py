"""Secret-safe external Neo4j connector and schema introspection."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Protocol
from urllib.parse import urlparse
from uuid import uuid4

from neo4j import GraphDatabase, READ_ACCESS

from backend.app.projects.registry import ProjectRegistry
from backend.app.schema_registry import SchemaRegistry


ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]{2,127}$")
SUPPORTED_SCHEMES = {"neo4j", "neo4j+s", "bolt", "bolt+s"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SchemaIntrospector(Protocol):
    def inspect(
        self,
        *,
        uri: str,
        database: str,
        username: str,
        password: str,
        project_id: str,
    ) -> dict[str, Any]: ...


def _neo4j_type(value: Any) -> str:
    if isinstance(value, bool):
        return "BOOLEAN"
    if isinstance(value, int):
        return "INTEGER"
    if isinstance(value, float):
        return "FLOAT"
    return "STRING"


class Neo4jSchemaIntrospector:
    """Inspect labels/properties/relationships through READ transactions."""

    def inspect(
        self,
        *,
        uri: str,
        database: str,
        username: str,
        password: str,
        project_id: str,
    ) -> dict[str, Any]:
        driver = GraphDatabase.driver(uri, auth=(username, password))
        try:
            driver.verify_connectivity()
            with driver.session(
                database=database,
                default_access_mode=READ_ACCESS,
            ) as session:
                node_rows = [
                    row.data()
                    for row in session.run(
                        """
                        MATCH (n)
                        UNWIND labels(n) AS label
                        UNWIND keys(n) AS property
                        WITH label, property, collect(n[property])[0] AS sample
                        RETURN label, property, sample
                        ORDER BY label, property
                        """
                    )
                ]
                relationship_rows = [
                    row.data()
                    for row in session.run(
                        """
                        MATCH (source)-[rel]->(target)
                        RETURN labels(source)[0] AS source,
                               type(rel) AS type,
                               labels(target)[0] AS target,
                               collect(keys(rel))[0] AS property_keys
                        ORDER BY source, type, target
                        """
                    )
                ]
                counts = session.run(
                    """
                    MATCH (n)
                    WITH count(n) AS nodes
                    OPTIONAL MATCH ()-[r]->()
                    RETURN nodes, count(r) AS relationships
                    """
                ).single()
        finally:
            driver.close()

        node_properties: dict[str, dict[str, str]] = {}
        for row in node_rows:
            node_properties.setdefault(str(row["label"]), {})[
                str(row["property"])
            ] = _neo4j_type(row.get("sample"))
        if not node_properties:
            raise ValueError("연결된 Neo4j에 노드가 없습니다.")

        nodes = []
        for label, properties in sorted(node_properties.items()):
            if not properties:
                raise ValueError(
                    f"{label} 노드에 identity로 사용할 속성이 없습니다."
                )
            identity = next(
                (
                    name
                    for name in properties
                    if name == "id" or name.endswith("_id")
                ),
                "name" if "name" in properties else next(iter(properties)),
            )
            nodes.append(
                {
                    "label": label,
                    "identity": identity,
                    "properties": properties,
                    "required_properties": [identity],
                }
            )

        relationships_by_type: dict[str, dict[str, Any]] = {}
        for row in relationship_rows:
            rel_type = str(row["type"])
            source = str(row["source"])
            target = str(row["target"])
            if rel_type in relationships_by_type:
                relationship = relationships_by_type[rel_type]
                if source != relationship["source"]:
                    raise ValueError(
                        f"{rel_type} 관계의 source 라벨이 둘 이상입니다."
                    )
                if target not in relationship["targets"]:
                    relationship["targets"].append(target)
                continue
            relationships_by_type[rel_type] = {
                "type": rel_type,
                "source": source,
                "targets": [target],
                "cardinality": "MANY_TO_MANY",
                "properties": {
                    str(name): "STRING"
                    for name in (row.get("property_keys") or [])
                },
            }
        stable = json.dumps(
            {
                "nodes": nodes,
                "relationships": list(relationships_by_type.values()),
                "counts": dict(counts) if counts else {},
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        fingerprint = hashlib.sha256(stable.encode("utf-8")).hexdigest()
        return {
            "schema": {
                "project_id": project_id,
                "version": f"introspected-{fingerprint[:12]}",
                "source_version": fingerprint,
                "isolation_mode": "database",
                "title": f"{project_id} introspected graph",
                "nodes": nodes,
                "relationships": list(relationships_by_type.values()),
                "query_scenarios": [],
            },
            "fingerprint": fingerprint,
            "counts": {
                "nodes": int(counts["nodes"]) if counts else 0,
                "relationships": (
                    int(counts["relationships"]) if counts else 0
                ),
            },
        }


class Neo4jConnectorService:
    """Persist connector metadata while keeping passwords in environment."""

    def __init__(
        self,
        root: Path,
        projects: ProjectRegistry,
        schemas: SchemaRegistry,
        *,
        introspector: SchemaIntrospector | None = None,
    ):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.projects = projects
        self.schemas = schemas
        self.introspector = introspector or Neo4jSchemaIntrospector()

    def _path(self, connector_id: str) -> Path:
        if not re.fullmatch(r"[a-f0-9-]{36}", connector_id):
            raise ValueError("유효하지 않은 connector_id입니다.")
        return self.root / f"{connector_id}.json"

    @staticmethod
    def _validate_uri(uri: str) -> str:
        parsed = urlparse(uri.strip())
        if parsed.scheme not in SUPPORTED_SCHEMES or not parsed.hostname:
            raise ValueError("지원하지 않는 Neo4j URI입니다.")
        if parsed.username or parsed.password:
            raise ValueError("URI에 인증정보를 포함하지 마세요.")
        return uri.strip()

    def validate(
        self,
        project_id: str,
        *,
        uri: str,
        database: str,
        username: str,
        password_env: str,
    ) -> dict[str, Any]:
        project = self.projects.require(project_id)
        if project["status"] in {"ready", "archived"}:
            raise ValueError(
                "ready 또는 archived 프로젝트의 데이터 연결은 변경할 수 없습니다."
            )
        if project["source_type"] != "neo4j":
            raise ValueError("source_type이 neo4j인 프로젝트만 연결할 수 있습니다.")
        uri = self._validate_uri(uri)
        database = database.strip()
        username = username.strip()
        if not database or not username:
            raise ValueError("database와 username이 필요합니다.")
        if not ENV_NAME.fullmatch(password_env):
            raise ValueError("password_env 이름이 유효하지 않습니다.")
        password = os.getenv(password_env)
        if not password:
            raise ValueError(f"{password_env} 환경변수가 설정되지 않았습니다.")

        if project["status"] in {"draft", "failed"}:
            self.projects.transition(
                project_id, "profiling", reason="neo4j_connector_validation"
            )
        try:
            inspected = self.introspector.inspect(
                uri=uri,
                database=database,
                username=username,
                password=password,
                project_id=project_id,
            )
        except Exception:
            self.projects.transition(
                project_id, "failed", reason="neo4j_connector_validation_failed"
            )
            raise
        connector_id = str(uuid4())
        profile = {
            "connector_id": connector_id,
            "project_id": project_id,
            "kind": "neo4j",
            "uri": uri,
            "database": database,
            "username": username,
            "password_env": password_env,
            "status": "validated",
            "schema": inspected["schema"],
            "schema_fingerprint": inspected["fingerprint"],
            "counts": inspected["counts"],
            "validated_at": _now(),
        }
        path = self._path(connector_id)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(profile, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)
        self.projects.update(
            project_id,
            connector_id=connector_id,
            source_version=inspected["fingerprint"],
        )
        self.projects.record_artifact(
            project_id,
            "source",
            version=inspected["fingerprint"],
            fingerprint=inspected["fingerprint"],
            metadata={"connector_id": connector_id, **inspected["counts"]},
        )
        self.projects.record_artifact(
            project_id,
            "connector",
            version=connector_id,
            status="validated",
            fingerprint=inspected["fingerprint"],
            metadata={
                "uri": uri,
                "database": database,
                "password_env": password_env,
            },
        )
        self.projects.transition(
            project_id, "mapping_review", reason="neo4j_schema_introspected"
        )
        return self.get(connector_id)

    def approve(self, project_id: str, connector_id: str) -> dict[str, Any]:
        profile = self.get(connector_id)
        if profile["project_id"] != project_id:
            raise ValueError("connector가 요청 프로젝트에 속하지 않습니다.")
        if self.projects.require(project_id)["status"] != "mapping_review":
            raise ValueError("mapping_review 상태에서만 승인할 수 있습니다.")
        schema = self.schemas.save(project_id, profile["schema"])
        self.projects.update(
            project_id,
            schema_version=str(schema["version"]),
            source_version=str(schema["source_version"]),
            connector_id=connector_id,
        )
        self.projects.record_artifact(
            project_id,
            "schema",
            version=str(schema["version"]),
            fingerprint=profile["schema_fingerprint"],
        )
        self.projects.record_artifact(
            project_id,
            "connector",
            version=connector_id,
            status="verified",
            fingerprint=profile["schema_fingerprint"],
            metadata={
                "uri": profile["uri"],
                "database": profile["database"],
                "password_env": profile["password_env"],
            },
        )
        self.projects.transition(
            project_id, "loading", reason="external_graph_attach_started"
        )
        self.projects.transition(
            project_id, "validating", reason="external_graph_attached"
        )
        count_status = (
            "verified" if int(profile["counts"]["nodes"]) > 0 else "failed"
        )
        self.projects.record_artifact(
            project_id,
            "integrity",
            version=profile["schema_fingerprint"],
            status=count_status,
            fingerprint=profile["schema_fingerprint"],
            metadata=profile["counts"],
        )
        self.projects.record_artifact(
            project_id,
            "read_only",
            version="connector-read-v1",
            status="verified",
            metadata={"default_access_mode": "READ"},
        )
        if count_status != "verified":
            self.projects.transition(
                project_id, "failed", reason="external_graph_empty"
            )
            raise ValueError("노드가 없는 외부 그래프는 승인할 수 없습니다.")
        self.projects.transition(
            project_id,
            "evaluation_required",
            reason="external_graph_integrity_verified",
        )
        profile["status"] = "approved"
        profile["approved_at"] = _now()
        self._save(profile)
        return profile

    def _save(self, profile: dict[str, Any]) -> None:
        path = self._path(profile["connector_id"])
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(profile, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)

    def get(self, connector_id: str) -> dict[str, Any]:
        path = self._path(connector_id)
        if not path.exists():
            raise KeyError(f"connector를 찾을 수 없습니다: {connector_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def connection(self, project_id: str) -> dict[str, str] | None:
        project = self.projects.require(project_id)
        connector_id = project.get("connector_id")
        if not connector_id:
            return None
        profile = self.get(str(connector_id))
        password = os.getenv(profile["password_env"])
        if not password:
            raise RuntimeError(
                f"{profile['password_env']} 환경변수가 설정되지 않았습니다."
            )
        return {
            "uri": profile["uri"],
            "database": profile["database"],
            "username": profile["username"],
            "password": password,
        }
