"""Application service composition shared by Streamlit and FastAPI."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from neo4j import Driver, GraphDatabase

from backend.app.agent.examples import GoldExampleStore
from backend.app.agent.graph import Neo4jReadGraph
from backend.app.agent.model import (
    GeminiCypherModel,
    GoldCypherModel,
    OpenAICypherModel,
    has_vertex_credentials,
)
from backend.app.agent.workflow import TextToCypherAgent
from backend.app.etl.cli import password_from_keychain
from backend.app.services.dashboard_service import DashboardService
from backend.app.services.feedback_service import FeedbackService
from backend.app.services.graph_service import GraphCatalogService
from backend.app.services.query_service import QueryService


@dataclass
class ServiceBundle:
    driver: Driver
    query: QueryService
    fallback_query: QueryService | None
    dashboard: DashboardService
    provider: str
    model_name: str
    graph: GraphCatalogService | None = None
    feedback: FeedbackService | None = None

    def close(self) -> None:
        self.driver.close()

    def query_with_fallback(self, question: str) -> dict:
        try:
            return self.query.query(question)
        except Exception as primary_error:
            if self.fallback_query is None:
                raise
            fallback = self.fallback_query.query(question)
            if fallback.get("status") == "unsupported":
                raise primary_error
            fallback["fallback_reason"] = str(primary_error)
            fallback["answer"] = (
                "실시간 생성 모델 연결이 불안정해 검증된 Gold 쿼리로 "
                "안전하게 전환했습니다. " + fallback["answer"]
            )
            return fallback


def build_service_bundle(
    project_root: Path,
    provider: str = "auto",
    model_name: str | None = None,
) -> ServiceBundle:
    username = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD") or password_from_keychain(username)
    if not password:
        raise RuntimeError(
            "Neo4j 비밀번호가 없습니다. NEO4J_PASSWORD 또는 macOS Keychain을 설정하세요."
        )
    resolved_provider = provider
    if provider == "auto":
        if os.getenv("OPENAI_API_KEY"):
            resolved_provider = "openai"
        elif has_vertex_credentials():
            resolved_provider = "gemini"
        else:
            resolved_provider = "gold"
    if resolved_provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY가 없습니다. Gold 데모 모드를 사용하거나 API 키를 설정하세요."
        )
    if resolved_provider == "gemini" and not has_vertex_credentials():
        raise RuntimeError(
            "Vertex AI 인증정보가 없습니다. Gold 데모 모드를 사용하거나 "
            "GOOGLE_APPLICATION_CREDENTIALS를 설정하세요."
        )

    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI", "neo4j://localhost:7687"),
        auth=(username, password),
    )
    driver.verify_connectivity()
    examples_path = project_root / "evaluation" / "gold_questions.yml"
    examples = GoldExampleStore(examples_path)
    try:
        if resolved_provider == "openai":
            resolved_model_name = model_name or os.getenv(
                "OPENAI_MODEL", "gpt-4.1-mini"
            )
            model = OpenAICypherModel(model=resolved_model_name)
        elif resolved_provider == "gemini":
            resolved_model_name = model_name or os.getenv(
                "GOOGLE_VERTEX_MODEL", "gemini-2.5-flash"
            )
            model = GeminiCypherModel(
                model=resolved_model_name,
                location=os.getenv(
                    "GOOGLE_VERTEX_LOCATION", "us-central1"
                ),
            )
        else:
            resolved_model_name = "gold-lookup"
            model = GoldCypherModel(examples)
    except Exception:
        if provider != "auto":
            driver.close()
            raise
        resolved_provider = "gold"
        resolved_model_name = "gold-lookup"
        model = GoldCypherModel(examples)

    database = os.getenv("NEO4J_DATABASE", "neo4j")
    primary_graph = Neo4jReadGraph(driver, database=database)
    agent = TextToCypherAgent(
        model=model,
        graph=primary_graph,
        examples_path=examples_path,
    )
    audit_log_path = (
        project_root / "data" / "processed" / "query_audit.jsonl"
    )
    fallback_query = None
    if resolved_provider != "gold":
        fallback_query = QueryService(
            TextToCypherAgent(
                model=GoldCypherModel(examples),
                graph=Neo4jReadGraph(driver, database=database),
                examples_path=examples_path,
            ),
            audit_log_path=audit_log_path,
            provider="gold-fallback",
        )
    return ServiceBundle(
        driver=driver,
        query=QueryService(
            agent,
            audit_log_path=audit_log_path,
            provider=resolved_provider,
            usage_reader=(
                model.usage_summary
                if hasattr(model, "usage_summary")
                else None
            ),
        ),
        fallback_query=fallback_query,
        dashboard=DashboardService(
            driver=driver,
            database=database,
            metrics_path=project_root / "evaluation" / "metrics.json",
            audit_log_path=audit_log_path,
            processed_root=project_root / "data" / "processed",
        ),
        graph=GraphCatalogService(driver=driver, database=database),
        feedback=FeedbackService(
            project_root
            / "data"
            / "processed"
            / "expert_feedback.jsonl"
        ),
        provider=resolved_provider,
        model_name=resolved_model_name,
    )
