"""FastAPI boundary over the existing P3 application services."""

from __future__ import annotations

from contextlib import asynccontextmanager
from inspect import signature
import os
from pathlib import Path
from threading import Lock
from typing import Callable, Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from backend.app.agent.project_router import ProjectRouter
from backend.app.services.bootstrap import ServiceBundle, build_service_bundle
from neo4j import GraphDatabase, READ_ACCESS

from backend.app.projects import (
    Neo4jConnectorService,
    ProjectReadinessService,
    ProjectRegistry,
)
from backend.app.ingestion import DatasetWorkspace
from backend.app.mapping import MappingWorkspace
from backend.app.etl.generic_loader import GenericGraphLoader
from backend.app.schema_registry import SchemaRegistry
from backend.app.services.diagnostics import (
    collect_demo_diagnostics,
    diagnostics_pass,
)
from backend.app.services.audit_service import AuditService
from backend.app.services.project_load_service import (
    ProjectGraphLoadService,
)
from backend.app.services.graph_service import node_search_contract
from backend.app.etl.cli import password_from_keychain

from .schemas import (
    AgentRunStateResponse,
    FeedbackRecord,
    FeedbackRequest,
    FeedbackSummary,
    DatasetUploadRequest,
    ErrorEnvelope,
    GraphMappingRequest,
    Neo4jConnectorRequest,
    Neo4jConnectorResponse,
    ProjectLoadRequest,
    GraphSchemaResponse,
    HealthResponse,
    NodeSearchResponse,
    ProjectCreate,
    ProjectReadinessResponse,
    ProjectResponse,
    ProjectUpdate,
    QueryRequest,
    QueryResponse,
    RuntimeResponse,
    SubgraphResponse,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
BundleFactory = Callable[..., ServiceBundle]


ERROR_BY_STATUS = {
    400: ("BAD_REQUEST", "request", False),
    401: ("UNAUTHENTICATED", "authorization", False),
    403: ("FORBIDDEN", "authorization", False),
    404: ("NOT_FOUND", "request", False),
    409: ("STATE_CONFLICT", "state", False),
    422: ("VALIDATION_ERROR", "request", False),
    429: ("RATE_LIMITED", "dependency", True),
    500: ("INTERNAL_ERROR", "internal", True),
    502: ("UPSTREAM_ERROR", "dependency", True),
    503: ("DEPENDENCY_UNAVAILABLE", "dependency", True),
    504: ("UPSTREAM_TIMEOUT", "dependency", True),
}


def _error_payload(
    request: Request,
    *,
    status_code: int,
    detail: Any,
) -> dict[str, Any]:
    code, category, retryable = ERROR_BY_STATUS.get(
        status_code,
        ("HTTP_ERROR", "internal", status_code >= 500),
    )
    message = (
        detail
        if isinstance(detail, str)
        else "요청을 처리하지 못했습니다."
    )
    return {
        "detail": jsonable_encoder(detail),
        "error": {
            "code": code,
            "category": category,
            "message": message,
            "retryable": retryable,
            "request_id": getattr(
                request.state, "request_id", "unavailable"
            ),
        },
    }


class ServiceRegistry:
    """Lazily cache service bundles without mixing project schemas."""

    def __init__(
        self,
        factory: BundleFactory,
        *,
        project_aware: bool = False,
    ):
        self.factory = factory
        self.project_aware = project_aware
        self._bundles: dict[str, ServiceBundle] = {}
        self._lock = Lock()

    def get(self, project_id: str = "cip-dmd") -> ServiceBundle:
        cache_key = project_id if self.project_aware else "__shared__"
        if cache_key in self._bundles:
            return self._bundles[cache_key]
        with self._lock:
            if cache_key not in self._bundles:
                self._bundles[cache_key] = (
                    self.factory(project_id)
                    if self.project_aware
                    else self.factory()
                )
        return self._bundles[cache_key]

    def close(self, project_id: str | None = None) -> None:
        with self._lock:
            if project_id is None:
                bundles = list(self._bundles.values())
                self._bundles.clear()
            else:
                cache_key = (
                    project_id if self.project_aware else "__shared__"
                )
                bundle = self._bundles.pop(cache_key, None)
                bundles = [bundle] if bundle is not None else []
        for bundle in bundles:
            bundle.close()


def _cors_origins() -> list[str]:
    configured = os.getenv(
        "P3_CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    )
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


def create_app(
    bundle_factory: BundleFactory | None = None,
    project_registry: ProjectRegistry | None = None,
    schema_registry: SchemaRegistry | None = None,
    dataset_workspace: DatasetWorkspace | None = None,
    project_graph_loader: ProjectGraphLoadService | None = None,
    connector_service: Neo4jConnectorService | None = None,
    readiness_service: ProjectReadinessService | None = None,
) -> FastAPI:
    projects = project_registry or ProjectRegistry(
        Path(
            os.getenv(
                "P3_PROJECT_REGISTRY_PATH",
                PROJECT_ROOT / "data" / "processed" / "projects.sqlite3",
            )
        )
    )
    projects.ensure_default()
    schemas = schema_registry or SchemaRegistry(PROJECT_ROOT / "schemas")

    connector_root = (
        PROJECT_ROOT / "data" / "processed" / "project_connectors"
    )
    connectors = connector_service or Neo4jConnectorService(
        connector_root, projects, schemas
    )

    def project_bundle_factory(project_id: str) -> ServiceBundle:
        return build_service_bundle(
            project_root=PROJECT_ROOT,
            provider=os.getenv("P3_API_PROVIDER", "auto"),
            model_name=os.getenv("P3_API_MODEL") or None,
            project_id=project_id,
            schema_context=schemas.context(project_id),
            neo4j_connection=connectors.connection(project_id),
        )

    registry = ServiceRegistry(
        bundle_factory or project_bundle_factory,
        project_aware=bundle_factory is None,
    )
    datasets = dataset_workspace or DatasetWorkspace(
        PROJECT_ROOT / "data" / "processed" / "project_uploads"
    )
    mappings = MappingWorkspace(
        PROJECT_ROOT / "data" / "processed" / "project_mappings",
        datasets,
        schemas,
    )
    generic_loader = GenericGraphLoader(
        datasets,
        mappings,
        database=os.getenv("NEO4J_DATABASE", "neo4j"),
    )
    graph_loader = (
        project_graph_loader
        or ProjectGraphLoadService(
            PROJECT_ROOT,
            generic_loader,
        )
    )

    def direct_graph_counts(project_id: str) -> dict[str, int]:
        if bundle_factory is not None:
            bundle = registry.get(project_id)
            if bundle.graph is None:
                return {"nodes": 0, "relationships": 0}
            return bundle.graph.graph_counts(project_id)
        connection = connectors.connection(project_id) or {}
        username = connection.get("username") or os.getenv(
            "NEO4J_USERNAME", "neo4j"
        )
        password = (
            connection.get("password")
            or os.getenv("NEO4J_PASSWORD")
            or password_from_keychain(username)
        )
        if not password:
            raise RuntimeError("Neo4j 인증정보를 찾을 수 없습니다.")
        driver = GraphDatabase.driver(
            connection.get("uri")
            or os.getenv("NEO4J_URI", "neo4j://localhost:7687"),
            auth=(username, password),
        )
        database = connection.get("database") or os.getenv(
            "NEO4J_DATABASE", "neo4j"
        )
        try:
            with driver.session(
                database=database,
                default_access_mode=READ_ACCESS,
            ) as session:
                if project_id == "cip-dmd" or connection:
                    row = session.run(
                        """
                        MATCH (n)
                        WITH count(n) AS nodes
                        OPTIONAL MATCH ()-[r]->()
                        RETURN nodes, count(r) AS relationships
                        """
                    ).single()
                else:
                    row = session.run(
                        """
                        MATCH (n {project_id: $project_id})
                        WITH count(n) AS nodes
                        OPTIONAL MATCH ()-[r {project_id: $project_id}]->()
                        RETURN nodes, count(r) AS relationships
                        """,
                        project_id=project_id,
                    ).single()
            return {
                "nodes": int(row["nodes"]) if row else 0,
                "relationships": int(row["relationships"]) if row else 0,
            }
        finally:
            driver.close()

    readiness = readiness_service or ProjectReadinessService(
        PROJECT_ROOT,
        projects,
        schemas,
        datasets,
        mappings,
        graph_counter=direct_graph_counts,
    )
    audit = AuditService(PROJECT_ROOT)
    project_router = ProjectRouter(
        projects,
        schemas,
        confidence_threshold=float(
            os.getenv("P3_PROJECT_ROUTER_CONFIDENCE_THRESHOLD", "0.08")
        ),
        margin_threshold=float(
            os.getenv("P3_PROJECT_ROUTER_MARGIN_THRESHOLD", "0.04")
        ),
        top_k=int(os.getenv("P3_PROJECT_ROUTER_TOP_K", "3")),
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        application.state.registry = registry
        application.state.projects = projects
        application.state.schemas = schemas
        application.state.connectors = connectors
        application.state.readiness = readiness
        yield
        registry.close()

    application = FastAPI(
        title="Factory Graph RCA API",
        version="1.0.0",
        description=(
            "CiP-DMD 제조 지식그래프의 Text-to-Cypher 질의, "
            "근거 그래프 및 운영 지표 API"
        ),
        lifespan=lifespan,
        responses={
            status_code: {
                "model": ErrorEnvelope,
                "description": description,
            }
            for status_code, description in (
                (400, "Bad request"),
                (403, "Forbidden"),
                (404, "Not found"),
                (409, "Lifecycle or readiness conflict"),
                (422, "Request validation failed"),
                (500, "Internal error"),
                (502, "Upstream dependency error"),
                (503, "Dependency unavailable"),
            )
        },
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["*"],
    )
    application.add_middleware(GZipMiddleware, minimum_size=1000)

    @application.exception_handler(HTTPException)
    async def http_error(
        request: Request,
        error: HTTPException,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content=_error_payload(
                request,
                status_code=error.status_code,
                detail=error.detail,
            ),
            headers=error.headers,
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error(
        request: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=_error_payload(
                request,
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=error.errors(),
            ),
        )

    @application.middleware("http")
    async def security_headers(request: Request, call_next):
        request.state.request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @application.get("/api/v1/health/live")
    def live() -> dict[str, str]:
        return {"status": "alive"}

    @application.get("/api/v1/health", response_model=HealthResponse)
    def health() -> dict:
        checks = collect_demo_diagnostics(PROJECT_ROOT)
        return {
            "status": "ready" if diagnostics_pass(checks) else "degraded",
            "checks": checks,
        }

    @application.get("/api/v1/audit/events")
    def audit_events(
        project_id: str | None = None,
        event_type: str | None = None,
        search: str = "",
        limit: int = 300,
    ) -> dict:
        resolved_project_id = (
            project_id or projects.active_project_id() or "cip-dmd"
        )
        try:
            projects.require(resolved_project_id)
            events = audit.events(
                resolved_project_id,
                event_type=event_type,
                search=search,
                limit=limit,
            )
            return {
                "project_id": resolved_project_id,
                "count": len(events),
                "events": events,
            }
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @application.get("/api/v1/audit/runs/{run_id}")
    def audit_run(run_id: str, project_id: str | None = None) -> dict:
        resolved_project_id = (
            project_id or projects.active_project_id() or "cip-dmd"
        )
        try:
            projects.require(resolved_project_id)
            return audit.run(resolved_project_id, run_id)
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @application.get("/api/v1/runtime", response_model=RuntimeResponse)
    def runtime(project_id: str | None = None) -> dict[str, str]:
        resolved_project_id = (
            project_id or projects.active_project_id() or "cip-dmd"
        )
        try:
            report = readiness.inspect(resolved_project_id)
            if not report["can_query"]:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "프로젝트가 질의 준비 상태가 아닙니다. "
                        f"next_action={report['next_action']}"
                    ),
                )
            bundle = registry.get(resolved_project_id)
        except HTTPException:
            raise
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except Exception as error:
            raise HTTPException(
                status_code=503,
                detail=f"서비스 의존성을 시작하지 못했습니다: {error}",
            ) from error
        return {
            "provider": bundle.provider,
            "model_name": bundle.model_name,
            "transport": "service",
            "active_project_id": resolved_project_id,
            "ui_load_enabled": (
                os.getenv("P3_ENABLE_UI_LOAD", "0") == "1"
            ),
        }

    @application.get(
        "/api/v1/projects",
        response_model=list[ProjectResponse],
    )
    def list_projects(include_archived: bool = False) -> list[dict]:
        return projects.list(include_archived=include_archived)

    @application.post(
        "/api/v1/projects",
        response_model=ProjectResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_project(payload: ProjectCreate) -> dict:
        try:
            return projects.create(**payload.model_dump())
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @application.get(
        "/api/v1/projects/active",
        response_model=ProjectResponse,
    )
    def active_project() -> dict:
        active = projects.active()
        if active is None:
            raise HTTPException(status_code=404, detail="활성 프로젝트가 없습니다.")
        return active

    @application.get(
        "/api/v1/projects/{project_id}",
        response_model=ProjectResponse,
    )
    def get_project(project_id: str) -> dict:
        try:
            return projects.require(project_id)
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @application.get(
        "/api/v1/projects/{project_id}/readiness",
        response_model=ProjectReadinessResponse,
    )
    def project_readiness(project_id: str) -> dict:
        try:
            return readiness.inspect(project_id)
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"프로젝트 준비 상태 확인 실패: {error}",
            ) from error

    @application.post(
        "/api/v1/projects/{project_id}/readiness/promote",
        response_model=ProjectReadinessResponse,
    )
    def promote_project(project_id: str) -> dict[str, Any]:
        try:
            result = readiness.promote(project_id)
            registry.close(project_id)
            return result
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @application.patch(
        "/api/v1/projects/{project_id}",
        response_model=ProjectResponse,
    )
    def update_project(project_id: str, payload: ProjectUpdate) -> dict:
        try:
            return projects.update(
                project_id,
                **payload.model_dump(exclude_none=True),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @application.post(
        "/api/v1/projects/{project_id}/activate",
        response_model=ProjectResponse,
    )
    def activate_project(project_id: str) -> dict:
        try:
            return projects.activate(project_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @application.post(
        "/api/v1/projects/{project_id}/uploads/profile",
        status_code=status.HTTP_201_CREATED,
    )
    def profile_dataset(project_id: str, payload: DatasetUploadRequest) -> dict:
        try:
            project = projects.require(project_id)
            if project["source_type"] != "file":
                raise ValueError(
                    "file 프로젝트에서만 파일을 업로드할 수 있습니다."
                )
            if project["status"] in {"loading", "validating", "archived"}:
                raise ValueError(
                    f"{project['status']} 상태에서는 새 업로드를 시작할 수 없습니다."
                )
            if project["status"] != "profiling":
                projects.transition(
                    project_id,
                    "profiling",
                    reason="dataset_profile_started",
                )
            result = datasets.profile_upload(
                project_id,
                [item.model_dump() for item in payload.files],
            )
            # MappingWorkspace uses upload_id as the default immutable
            # source_version, so the registry must link the same lineage key.
            source_version = str(result["upload_id"])
            projects.update(project_id, source_version=source_version)
            projects.record_artifact(
                project_id,
                "source",
                version=source_version,
                fingerprint=result.get("source_sha256"),
                metadata={
                    "upload_id": result["upload_id"],
                    "file_count": len(result.get("files", [])),
                },
            )
            projects.transition(
                project_id,
                "mapping_review",
                reason="dataset_profile_completed",
            )
            registry.close(project_id)
            return result
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            try:
                current = projects.get(project_id)
            except ValueError:
                current = None
            if current and current["status"] == "profiling":
                projects.transition(
                    project_id,
                    "failed",
                    reason="dataset_profile_failed",
                )
            raise HTTPException(status_code=422, detail=str(error)) from error

    @application.get("/api/v1/projects/{project_id}/uploads")
    def list_dataset_uploads(project_id: str) -> dict:
        try:
            projects.require(project_id)
            rows = datasets.list(project_id)
            return {"project_id": project_id, "uploads": rows, "count": len(rows)}
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @application.get("/api/v1/projects/{project_id}/uploads/{upload_id}")
    def get_dataset_upload(project_id: str, upload_id: str) -> dict:
        try:
            projects.require(project_id)
            return datasets.get(project_id, upload_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @application.post("/api/v1/projects/{project_id}/mappings/preview")
    def preview_mapping(project_id: str, payload: GraphMappingRequest) -> dict:
        try:
            projects.require(project_id)
            return mappings.preview(
                project_id,
                payload.upload_id,
                payload.mapping,
                schema_version=payload.schema_version,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @application.post("/api/v1/projects/{project_id}/mappings/approve")
    def approve_mapping(project_id: str, payload: GraphMappingRequest) -> dict:
        try:
            project = projects.require(project_id)
            if project["status"] != "mapping_review":
                raise ValueError(
                    "mapping_review 상태에서만 mapping을 승인할 수 있습니다."
                )
            result = mappings.approve(
                project_id,
                payload.upload_id,
                payload.mapping,
                schema_version=payload.schema_version,
            )
            projects.update(
                project_id,
                schema_version=payload.schema_version,
            )
            schema = schemas.load(project_id)
            projects.record_artifact(
                project_id,
                "mapping",
                version=payload.schema_version,
                metadata={"upload_id": payload.upload_id},
            )
            projects.record_artifact(
                project_id,
                "schema",
                version=payload.schema_version,
                metadata={
                    "source_version": schema.get("source_version")
                },
            )
            registry.close(project_id)
            return result
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @application.get("/api/v1/projects/{project_id}/mappings/approved")
    def approved_mapping(project_id: str) -> dict:
        try:
            projects.require(project_id)
            return mappings.get(project_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @application.post("/api/v1/projects/{project_id}/graph/load")
    def load_project_graph(
        project_id: str,
        payload: ProjectLoadRequest,
    ) -> dict:
        if os.getenv("P3_ENABLE_UI_LOAD", "0") != "1":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "그래프 적재 API가 비활성화되어 있습니다. "
                    "P3_ENABLE_UI_LOAD=1 설정이 필요합니다."
                ),
            )
        if payload.confirm_project_id != project_id:
            raise HTTPException(
                status_code=422,
                detail="적재 승인용 confirm_project_id가 일치하지 않습니다.",
            )
        try:
            project = projects.require(project_id)
            if project["status"] != "mapping_review":
                raise ValueError(
                    "mapping_review 상태에서만 적재를 시작할 수 있습니다."
                )
            projects.transition(
                project_id, "loading", reason="graph_load_started"
            )
            registry.close()
            result = graph_loader.load(project_id, payload.upload_id)
            projects.transition(
                project_id, "validating", reason="graph_load_completed"
            )
            integrity = result["integrity"]
            integrity_ok = (
                integrity.get("project_scope_applied") is True
                and int(integrity.get("scoped_node_count", 0)) > 0
            )
            projects.record_artifact(
                project_id,
                "load",
                version=payload.upload_id,
                metadata={"report_path": result.get("report_path")},
            )
            projects.record_artifact(
                project_id,
                "integrity",
                version=payload.upload_id,
                status="verified" if integrity_ok else "failed",
                metadata=integrity,
            )
            projects.record_artifact(
                project_id,
                "read_only",
                version="reader-v1",
                status="verified",
                metadata=result.get("access", {"reader_mode": "READ"}),
            )
            if not integrity_ok:
                projects.transition(
                    project_id, "failed", reason="integrity_gate_failed"
                )
                raise ValueError("적재 무결성 gate를 통과하지 못했습니다.")
            projects.transition(
                project_id,
                "evaluation_required",
                reason="integrity_gate_passed",
            )
            return result
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            current = projects.get(project_id)
            if current and current["status"] not in {"failed", "archived"}:
                projects.transition(
                    project_id, "failed", reason="graph_load_validation_failed"
                )
            raise HTTPException(status_code=422, detail=str(error)) from error
        except Exception as error:
            current = projects.get(project_id)
            if current and current["status"] not in {"failed", "archived"}:
                projects.transition(
                    project_id, "failed", reason="graph_load_failed"
                )
            raise HTTPException(
                status_code=502, detail=f"프로젝트 그래프 적재 실패: {error}"
            ) from error

    @application.post("/api/v1/query", response_model=QueryResponse)
    def query_graph(payload: QueryRequest, request: Request) -> dict:
        try:
            routing_decision = project_router.route(
                payload.question.strip(),
                explicit_project_id=payload.project_id,
            )
            requested_project_id = routing_decision.selected_project_id
            if requested_project_id is None:
                return {
                    "question": payload.question.strip(),
                    "answer": (
                        "질문이 여러 프로젝트와 비슷하거나 프로젝트 단서가 "
                        "부족합니다. 제품·부품·품질 또는 설비·정비 같은 "
                        "대상을 추가하거나 프로젝트를 직접 선택해 주세요."
                    ),
                    "status": "needs_clarification",
                    "cypher": "",
                    "rows": [],
                    "row_count": 0,
                    "metadata": {},
                    "evidence": {
                        "nodes": [],
                        "relationships": [],
                        "node_count": 0,
                        "relationship_count": 0,
                        "documents": [],
                    },
                    "validation": {
                        "attempts": 0,
                        "errors": ["PROJECT_ROUTING_NEEDS_CLARIFICATION"],
                        "trace": [
                            {
                                "step": "route_project",
                                "executed": False,
                                **routing_decision.as_state(),
                            }
                        ],
                        "tool_trace": [],
                        "elapsed_ms": 0,
                    },
                    "usage": {},
                    "provider": "router",
                    "routing": routing_decision.as_state(),
                    "project_id": None,
                }
            projects.require(requested_project_id)
            report = readiness.inspect(requested_project_id)
            if not report["can_query"]:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "선택한 프로젝트가 readiness gate를 통과하지 "
                        f"못했습니다. next_action={report['next_action']}"
                    ),
                )
            bundle = registry.get(requested_project_id)
            roles = tuple(
                role.strip()
                for role in request.headers.get("X-User-Roles", "").split(",")
                if role.strip()
            )
            query_parameters = signature(
                bundle.query_with_fallback
            ).parameters
            if "organization_id" in query_parameters:
                result = bundle.query_with_fallback(
                    payload.question.strip(),
                    organization_id=(
                        request.headers.get("X-Organization-ID") or "local"
                    ),
                    user_id=request.headers.get("X-User-ID") or "anonymous",
                    roles=roles,
                    routing_state=routing_decision.as_state(),
                )
            else:
                result = bundle.query_with_fallback(payload.question.strip())
            result["project_id"] = requested_project_id
            result["routing"] = routing_decision.as_state()
            return result
        except HTTPException:
            raise
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"질의 처리에 실패했습니다: {error}",
            ) from error

    @application.get(
        "/api/v1/agent/runs/{run_id}",
        response_model=AgentRunStateResponse,
    )
    def agent_run_state(
        run_id: str,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        resolved_project_id = (
            project_id or projects.active_project_id() or "cip-dmd"
        )
        try:
            projects.require(resolved_project_id)
            return registry.get(resolved_project_id).query.run_state(run_id)
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @application.post(
        "/api/v1/agent/runs/{run_id}/resume",
        response_model=QueryResponse,
    )
    def resume_agent_run(
        run_id: str,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        resolved_project_id = (
            project_id or projects.active_project_id() or "cip-dmd"
        )
        try:
            projects.require(resolved_project_id)
            return registry.get(resolved_project_id).query.resume(run_id)
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except Exception as error:
            raise HTTPException(
                status_code=502,
                detail=f"LangGraph run 재개 실패: {error}",
            ) from error

    @application.post(
        "/api/v1/projects/{project_id}/connectors/neo4j/validate",
        response_model=Neo4jConnectorResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def validate_neo4j_connector(
        project_id: str,
        payload: Neo4jConnectorRequest,
    ) -> dict[str, Any]:
        try:
            result = connectors.validate(
                project_id, **payload.model_dump()
            )
            registry.close(project_id)
            return result
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except Exception as error:
            raise HTTPException(
                status_code=502,
                detail=f"Neo4j connector 검증 실패: {error}",
            ) from error

    @application.post(
        "/api/v1/projects/{project_id}/connectors/neo4j/{connector_id}/approve",
        response_model=Neo4jConnectorResponse,
    )
    def approve_neo4j_connector(
        project_id: str,
        connector_id: str,
    ) -> dict[str, Any]:
        try:
            result = connectors.approve(project_id, connector_id)
            registry.close(project_id)
            return result
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @application.get("/api/v1/metrics")
    def metrics(
        project_id: str | None = None,
        provider: list[str] | None = None,
        query_status: list[str] | None = None,
        days: int | None = None,
    ) -> dict:
        try:
            resolved_project_id = (
                project_id or projects.active_project_id() or "cip-dmd"
            )
            projects.require(resolved_project_id)
            bundle = registry.get(resolved_project_id)
            runtime_filters = {
                "providers": provider or [],
                "statuses": query_status or [],
                "days": days,
                "project_id": resolved_project_id,
            }
            snapshot = bundle.dashboard.snapshot
            if signature(snapshot).parameters:
                return snapshot(runtime_filters)
            return snapshot()
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"운영 지표 조회에 실패했습니다: {error}",
            ) from error

    @application.post(
        "/api/v1/feedback",
        response_model=FeedbackRecord,
        status_code=status.HTTP_201_CREATED,
    )
    def record_feedback(
        payload: FeedbackRequest,
    ) -> dict:
        project_id = (
            payload.project_id
            or projects.active_project_id()
            or "cip-dmd"
        )
        try:
            projects.require(project_id)
            bundle = registry.get(project_id)
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except Exception as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        if bundle.feedback is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="전문가 검증 기록 서비스가 구성되지 않았습니다.",
            )
        try:
            review = payload.model_dump(exclude={"project_id"})
            return bundle.feedback.record_review(**review)
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(error),
            ) from error
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"전문가 검증 기록에 실패했습니다: {error}",
            ) from error

    @application.get(
        "/api/v1/feedback/summary",
        response_model=FeedbackSummary,
    )
    def feedback_summary(
        project_id: str | None = None,
    ) -> dict:
        resolved_project_id = (
            project_id or projects.active_project_id() or "cip-dmd"
        )
        try:
            projects.require(resolved_project_id)
            bundle = registry.get(resolved_project_id)
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except Exception as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        if bundle.feedback is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="전문가 검증 기록 서비스가 구성되지 않았습니다.",
            )
        try:
            return bundle.feedback.summary()
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"전문가 검증 요약 조회에 실패했습니다: {error}",
            ) from error

    @application.get(
        "/api/v1/graph/schema",
        response_model=GraphSchemaResponse,
    )
    def graph_schema(project_id: str | None = None) -> dict:
        resolved_project_id = (
            project_id or projects.active_project_id() or "cip-dmd"
        )
        try:
            projects.require(resolved_project_id)
            return schemas.contract(resolved_project_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @application.get(
        "/api/v1/projects/{project_id}/schema",
        response_model=GraphSchemaResponse,
    )
    def project_schema(project_id: str) -> dict:
        try:
            projects.require(project_id)
            return schemas.contract(project_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @application.get(
        "/api/v1/graph/search",
        response_model=NodeSearchResponse,
    )
    def graph_search(
        label: str = Query(description="노드 라벨"),
        q: str = Query(min_length=1, max_length=200),
        limit: int = Query(default=12, ge=1, le=50),
        project_id: str | None = None,
    ) -> dict:
        q = q.strip()
        if not q:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="검색어는 공백일 수 없습니다.",
            )
        try:
            resolved_project_id = (
                project_id or projects.active_project_id() or "cip-dmd"
            )
            projects.require(resolved_project_id)
            bundle = registry.get(resolved_project_id)
            if bundle.graph is None:
                raise RuntimeError(
                    "그래프 탐색 서비스가 구성되지 않았습니다."
                )
            contract = schemas.contract(resolved_project_id)
            identity_by_label = {
                row["label"]: row["identity_property"]
                for row in contract["node_identities"]
            }
            if label not in identity_by_label:
                raise ValueError(f"지원하지 않는 노드 라벨입니다: {label}")
            if resolved_project_id == "cip-dmd":
                return bundle.graph.search_nodes(label, q, limit)
            identity_property, search_properties = node_search_contract(
                contract, label
            )
            return bundle.graph.search_nodes(
                label,
                q,
                limit,
                project_id=resolved_project_id,
                identity_property=identity_property,
                search_properties=search_properties,
            )
        except KeyError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(error),
            ) from error
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(error),
            ) from error
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"노드 검색에 실패했습니다: {error}",
            ) from error

    @application.get(
        "/api/v1/graph/subgraph",
        response_model=SubgraphResponse,
    )
    def graph_subgraph(
        label: str = Query(description="노드 라벨"),
        identity: str = Query(min_length=1, max_length=200),
        depth: int = Query(default=2, ge=1, le=3),
        limit: int = Query(default=50, ge=1, le=100),
        project_id: str | None = None,
    ) -> dict:
        identity = identity.strip()
        if not identity:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="identity는 공백일 수 없습니다.",
            )
        try:
            resolved_project_id = (
                project_id or projects.active_project_id() or "cip-dmd"
            )
            projects.require(resolved_project_id)
            bundle = registry.get(resolved_project_id)
            if bundle.graph is None:
                raise RuntimeError(
                    "그래프 탐색 서비스가 구성되지 않았습니다."
                )
            contract = schemas.contract(resolved_project_id)
            identity_by_label = {
                row["label"]: row["identity_property"]
                for row in contract["node_identities"]
            }
            if label not in identity_by_label:
                raise ValueError(f"지원하지 않는 노드 라벨입니다: {label}")
            if resolved_project_id == "cip-dmd":
                return bundle.graph.subgraph(label, identity, depth, limit)
            return bundle.graph.subgraph(
                label,
                identity,
                depth,
                limit,
                project_id=resolved_project_id,
                identity_property=identity_by_label[label],
            )
        except KeyError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(error),
            ) from error
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(error),
            ) from error
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"부분 그래프 조회에 실패했습니다: {error}",
            ) from error

    return application


app = create_app()
