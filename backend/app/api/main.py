"""FastAPI boundary over the existing P3 application services."""

from __future__ import annotations

from contextlib import asynccontextmanager
import os
from pathlib import Path
from threading import Lock
from typing import Callable

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware

from backend.app.services.bootstrap import ServiceBundle, build_service_bundle
from backend.app.services.diagnostics import (
    collect_demo_diagnostics,
    diagnostics_pass,
)
from backend.app.services.graph_service import (
    NODE_IDENTITIES,
    schema_contract,
)

from .schemas import (
    FeedbackRecord,
    FeedbackRequest,
    FeedbackSummary,
    GraphSchemaResponse,
    HealthResponse,
    NodeSearchResponse,
    QueryRequest,
    QueryResponse,
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


def create_app(bundle_factory: BundleFactory | None = None) -> FastAPI:
    registry = ServiceRegistry(bundle_factory or _default_bundle_factory)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        application.state.registry = registry
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

    @application.post("/api/v1/query", response_model=QueryResponse)
    def query_graph(
        payload: QueryRequest,
        bundle: ServiceBundle = Depends(get_bundle),
    ) -> dict:
        try:
            return bundle.query_with_fallback(payload.question.strip())
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
    def graph_schema() -> dict:
        return schema_contract()

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
