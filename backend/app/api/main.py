"""FastAPI boundary over the existing P3 application services."""

from __future__ import annotations

from contextlib import asynccontextmanager
import os
from pathlib import Path
from threading import Lock
from typing import Callable

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from backend.app.services.bootstrap import ServiceBundle, build_service_bundle
from backend.app.projects import ProjectRegistry
from backend.app.ingestion import DatasetWorkspace
from backend.app.mapping import MappingWorkspace
from backend.app.etl.generic_loader import GenericGraphLoader
from backend.app.schema_registry import SchemaRegistry
from backend.app.services.diagnostics import (
    collect_demo_diagnostics,
    diagnostics_pass,
)
from backend.app.services.graph_service import NODE_IDENTITIES

from .schemas import (
    FeedbackRecord,
    FeedbackRequest,
    FeedbackSummary,
    DatasetUploadRequest,
    GraphMappingRequest,
    ProjectLoadRequest,
    GraphSchemaResponse,
    HealthResponse,
    NodeSearchResponse,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    QueryRequest,
    QueryResponse,
    RuntimeResponse,
    SubgraphResponse,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
BundleFactory = Callable[[], ServiceBundle]


class ServiceRegistry:
    """Create one shared service bundle lazily and close it on shutdown."""

    def __init__(self, factory: BundleFactory):
        self.factory = factory
        self._bundle: ServiceBundle | None = None
        self._lock = Lock()

    def get(self) -> ServiceBundle:
        if self._bundle is not None:
            return self._bundle
        with self._lock:
            if self._bundle is None:
                self._bundle = self.factory()
        return self._bundle

    def close(self) -> None:
        if self._bundle is not None:
            self._bundle.close()
            self._bundle = None


def _default_bundle_factory() -> ServiceBundle:
    return build_service_bundle(
        project_root=PROJECT_ROOT,
        provider=os.getenv("P3_API_PROVIDER", "auto"),
        model_name=os.getenv("P3_API_MODEL") or None,
    )


def _cors_origins() -> list[str]:
    configured = os.getenv(
        "P3_CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    )
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


def get_bundle(request: Request) -> ServiceBundle:
    try:
        return request.app.state.registry.get()
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"서비스 의존성을 시작하지 못했습니다: {error}",
        ) from error


def create_app(
    bundle_factory: BundleFactory | None = None,
    project_registry: ProjectRegistry | None = None,
    schema_registry: SchemaRegistry | None = None,
    dataset_workspace: DatasetWorkspace | None = None,
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
    def active_bundle_factory() -> ServiceBundle:
        project_id = projects.active_project_id() or "cip-dmd"
        return build_service_bundle(
            project_root=PROJECT_ROOT,
            provider=os.getenv("P3_API_PROVIDER", "auto"),
            model_name=os.getenv("P3_API_MODEL") or None,
            project_id=project_id,
            schema_context=schemas.context(project_id),
        )

    registry = ServiceRegistry(bundle_factory or active_bundle_factory)
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

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        application.state.registry = registry
        application.state.projects = projects
        application.state.schemas = schemas
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
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    application.add_middleware(GZipMiddleware, minimum_size=1000)

    @application.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
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

    @application.get("/api/v1/runtime", response_model=RuntimeResponse)
    def runtime(
        bundle: ServiceBundle = Depends(get_bundle),
    ) -> dict[str, str]:
        return {
            "provider": bundle.provider,
            "model_name": bundle.model_name,
            "transport": "service",
            "active_project_id": projects.active_project_id() or "cip-dmd",
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
            activated = projects.activate(project_id)
            registry.close()
            return activated
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
            projects.require(project_id)
            return datasets.profile_upload(
                project_id,
                [item.model_dump() for item in payload.files],
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
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
            projects.require(project_id)
            result = mappings.approve(
                project_id,
                payload.upload_id,
                payload.mapping,
                schema_version=payload.schema_version,
            )
            projects.update(
                project_id,
                schema_version=payload.schema_version,
                status="ready",
            )
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
        bundle: ServiceBundle = Depends(get_bundle),
    ) -> dict:
        if payload.confirm_project_id != project_id:
            raise HTTPException(
                status_code=422,
                detail="적재 승인용 confirm_project_id가 일치하지 않습니다.",
            )
        try:
            projects.require(project_id)
            return generic_loader.load(
                bundle.driver, project_id, payload.upload_id
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except Exception as error:
            raise HTTPException(
                status_code=502, detail=f"프로젝트 그래프 적재 실패: {error}"
            ) from error

    @application.post("/api/v1/query", response_model=QueryResponse)
    def query_graph(
        payload: QueryRequest,
        bundle: ServiceBundle = Depends(get_bundle),
    ) -> dict:
        active_project_id = projects.active_project_id()
        requested_project_id = payload.project_id or active_project_id
        if requested_project_id != active_project_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"프로젝트 {requested_project_id}는 아직 활성 상태가 "
                    "아닙니다. 먼저 activate API를 호출하세요."
                ),
            )
        try:
            result = bundle.query_with_fallback(payload.question.strip())
            result["project_id"] = requested_project_id
            return result
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"질의 처리에 실패했습니다: {error}",
            ) from error

    @application.get("/api/v1/metrics")
    def metrics(
        bundle: ServiceBundle = Depends(get_bundle),
    ) -> dict:
        try:
            return bundle.dashboard.snapshot()
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
        bundle: ServiceBundle = Depends(get_bundle),
    ) -> dict:
        if bundle.feedback is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="전문가 검증 기록 서비스가 구성되지 않았습니다.",
            )
        try:
            return bundle.feedback.record_review(**payload.model_dump())
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
        bundle: ServiceBundle = Depends(get_bundle),
    ) -> dict:
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
        bundle: ServiceBundle = Depends(get_bundle),
    ) -> dict:
        q = q.strip()
        if not q:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="검색어는 공백일 수 없습니다.",
            )
        if bundle.graph is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="그래프 탐색 서비스가 구성되지 않았습니다.",
            )
        try:
            return bundle.graph.search_nodes(label, q, limit)
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
        bundle: ServiceBundle = Depends(get_bundle),
    ) -> dict:
        identity = identity.strip()
        if not identity:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="identity는 공백일 수 없습니다.",
            )
        if label not in NODE_IDENTITIES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"지원하지 않는 라벨입니다. "
                    f"가능한 값: {', '.join(NODE_IDENTITIES)}"
                ),
            )
        if bundle.graph is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="그래프 탐색 서비스가 구성되지 않았습니다.",
            )
        try:
            return bundle.graph.subgraph(label, identity, depth, limit)
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
