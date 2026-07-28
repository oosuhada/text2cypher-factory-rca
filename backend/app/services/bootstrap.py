"""Application service composition shared by Streamlit and FastAPI."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

from neo4j import Driver, GraphDatabase

from backend.app.agent.examples import GoldExampleStore
from backend.app.agent.graph import Neo4jReadGraph
from backend.app.agent.model import (
    GeminiCypherModel,
    GoldCypherModel,
    OpenAICypherModel,
    has_vertex_credentials,
)
from backend.app.agent.prompt_registry import PromptRegistry
from backend.app.agent.workflow import TextToCypherAgent
from backend.app.agent.schema import SCHEMA_CONTEXT
from backend.app.agent.semantic_validation import (
    build_domain_validator,
    validate_domain_semantics,
)
from backend.app.schema_registry import SchemaRegistry
from backend.app.etl.cli import password_from_keychain
from backend.app.services.dashboard_service import DashboardService
from backend.app.services.feedback_service import FeedbackService
from backend.app.services.graph_service import GraphCatalogService
from backend.app.services.project_dashboard_service import (
    ProjectDashboardService,
)
from backend.app.services.query_service import QueryService


@dataclass
class ServiceBundle:
    driver: Driver
    query: QueryService
    fallback_query: QueryService | None
    dashboard: Any
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
    project_id: str = "cip-dmd",
    schema_context: str | None = None,
    neo4j_connection: dict[str, str] | None = None,
) -> ServiceBundle:
    connection = neo4j_connection or {}
    username = connection.get("username") or os.getenv(
        "NEO4J_USERNAME", "neo4j"
    )
    password = (
        connection.get("password")
        or os.getenv("NEO4J_PASSWORD")
        or password_from_keychain(username)
    )
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
        connection.get("uri")
        or os.getenv("NEO4J_URI", "neo4j://localhost:7687"),
        auth=(username, password),
    )
    driver.verify_connectivity()
    prompt_contract = None
    try:
        prompt_contract = PromptRegistry(project_root).load(project_id)
    except KeyError:
        # Projects created through the onboarding flow receive their prompt
        # manifest in stage 1-7. Keep the current schema path usable until then.
        pass
    project_examples = project_root / "evaluation" / f"{project_id}_gold.yml"
    examples_path = (
        prompt_contract.examples_path
        if prompt_contract
        else project_examples
        if project_examples.exists()
        else project_root / "evaluation" / "gold_questions.yml"
    )
    examples = GoldExampleStore(examples_path)
    request_timeout_seconds = (
        prompt_contract.timeout_seconds if prompt_contract else 30.0
    )
    try:
        if resolved_provider == "openai":
            resolved_model_name = model_name or os.getenv(
                "OPENAI_MODEL", "gpt-4.1-mini"
            )
            model = OpenAICypherModel(
                model=resolved_model_name,
                timeout_seconds=request_timeout_seconds,
            )
        elif resolved_provider == "gemini":
            resolved_model_name = model_name or os.getenv(
                "GOOGLE_VERTEX_MODEL", "gemini-2.5-flash"
            )
            model = GeminiCypherModel(
                model=resolved_model_name,
                location=os.getenv(
                    "GOOGLE_VERTEX_LOCATION", "us-central1"
                ),
                timeout_seconds=request_timeout_seconds,
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

    database = connection.get("database") or os.getenv(
        "NEO4J_DATABASE", "neo4j"
    )
    primary_graph = Neo4jReadGraph(driver, database=database)
    if prompt_contract:
        schema_manifest = SchemaRegistry(project_root / "schemas").load(
            project_id
        )
        resolved_schema_context = prompt_contract.schema_context
        semantic_validator = build_domain_validator(
            schema_manifest,
            include_cip_rules=(
                prompt_contract.domain_validator == "cip-dmd"
            ),
        )
        agent_metadata = prompt_contract.metadata()
        agent_max_attempts = prompt_contract.max_attempts
        agent_timeout_seconds = prompt_contract.timeout_seconds
        few_shot_count = prompt_contract.few_shot_count
    else:
        resolved_schema_context = (
            schema_context or SCHEMA_CONTEXT
        ) + (
            ""
            if project_id == "cip-dmd"
            else (
                "\n\nProject isolation:\n"
                f"- Every MATCH must restrict project_id to '{project_id}'."
            )
        )
        semantic_validator = (
            validate_domain_semantics
            if project_id == "cip-dmd"
            else (lambda _question, _statement: [])
        )
        agent_metadata = {"project_id": project_id}
        agent_max_attempts = 3
        agent_timeout_seconds = 30.0
        few_shot_count = 6
    agent = TextToCypherAgent(
        model=model,
        graph=primary_graph,
        examples_path=examples_path,
        max_attempts=agent_max_attempts,
        schema_context=resolved_schema_context,
        semantic_validator=semantic_validator,
        project_id=project_id,
        few_shot_count=few_shot_count,
        timeout_seconds=agent_timeout_seconds,
        metadata=agent_metadata,
    )
    processed_root = project_root / "data" / "processed"
    project_processed_root = (
        processed_root
        if project_id == "cip-dmd"
        else processed_root / "projects" / project_id
    )
    audit_log_path = project_processed_root / "query_audit.jsonl"
    fallback_query = None
    if resolved_provider != "gold":
        fallback_query = QueryService(
            TextToCypherAgent(
                model=GoldCypherModel(examples),
                graph=Neo4jReadGraph(driver, database=database),
                examples_path=examples_path,
                max_attempts=agent_max_attempts,
                schema_context=resolved_schema_context,
                semantic_validator=semantic_validator,
                project_id=project_id,
                few_shot_count=few_shot_count,
                timeout_seconds=agent_timeout_seconds,
                metadata=agent_metadata,
            ),
            audit_log_path=audit_log_path,
            provider="gold-fallback",
        )
    dashboard = (
        DashboardService(
            driver=driver,
            database=database,
            metrics_path=project_root / "evaluation" / "metrics.json",
            audit_log_path=audit_log_path,
            processed_root=processed_root,
        )
        if project_id == "cip-dmd"
        else ProjectDashboardService(
            driver=driver,
            database=database,
            project_id=project_id,
            audit_log_path=audit_log_path,
        )
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
        dashboard=dashboard,
        graph=GraphCatalogService(driver=driver, database=database),
        feedback=FeedbackService(
            project_processed_root / "expert_feedback.jsonl"
        ),
        provider=resolved_provider,
        model_name=resolved_model_name,
    )
