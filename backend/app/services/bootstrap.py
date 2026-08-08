"""Application service composition shared by Streamlit and FastAPI."""

from __future__ import annotations

from dataclasses import dataclass
from inspect import Parameter, signature
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from neo4j import Driver, GraphDatabase

from backend.app.agent.checkpoints import (
    RunCheckpointStore,
    build_checkpoint_store,
)
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
from backend.app.rag import DocumentRagService
from backend.app.schema_registry import SchemaRegistry
from backend.app.etl.cli import password_from_keychain
from backend.app.services.dashboard_service import DashboardService
from backend.app.services.feedback_service import FeedbackService
from backend.app.services.graph_service import GraphCatalogService
from backend.app.services.project_dashboard_service import (
    ProjectDashboardService,
)
from backend.app.services.query_service import QueryService
from backend.app.tools import ToolContext, ToolRegistry
from backend.app.tools.capabilities import (
    GraphQueryInput,
    SearchDocsInput,
    build_project_tool_registry,
)


_DOCUMENT_INTENT = (
    "절차",
    "매뉴얼",
    "manual",
    "sop",
    "표준서",
    "기준서",
    "작업표준",
    "점검 순서",
    "권장 방법",
)
_GRAPH_INTENT = (
    "이력",
    "기록",
    "건수",
    "비용",
    "다운타임",
    "관계",
    "구성품",
    "공정",
    "품질",
    "결과",
    "담당",
    "발생",
)


def _tool_selection(question: str) -> tuple[bool, bool]:
    normalized = question.lower()
    use_documents = any(token in normalized for token in _DOCUMENT_INTENT)
    use_graph = not use_documents or any(
        token in normalized for token in _GRAPH_INTENT
    )
    return use_graph, use_documents


def _bootstrap_rag_fixtures(
    service: DocumentRagService,
    project_root: Path,
    project_id: str,
) -> None:
    if os.getenv("P3_RAG_BOOTSTRAP_FIXTURES", "1").strip().lower() in {
        "0",
        "false",
        "off",
    }:
        return
    manifest_path = project_root / "evaluation" / "rag_fixtures.json"
    if not manifest_path.exists():
        return
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in document.get("projects", {}).get(project_id, []):
        source = project_root / str(item["source_path"])
        if not source.exists():
            continue
        service.ingest(
            document_id=str(item["document_id"]),
            title=str(item["title"]),
            version=str(item["version"]),
            document_type=str(item["document_type"]),
            source_filename=source.name,
            content_base64=None,
            content=source.read_text(encoding="utf-8"),
            effective_date=item.get("effective_date"),
            security_classification=str(
                item.get("security_classification", "internal")
            ),
            allowed_roles=item.get("allowed_roles", []),
            is_current=bool(item.get("is_current", True)),
        )


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
    checkpoint_store: RunCheckpointStore | None = None
    tools: ToolRegistry | None = None
    document_rag: DocumentRagService | None = None

    def close(self) -> None:
        self.driver.close()
        if self.checkpoint_store is not None:
            self.checkpoint_store.close()

    def query_with_fallback(
        self,
        question: str,
        *,
        organization_id: str = "local",
        user_id: str = "anonymous",
        roles: tuple[str, ...] | list[str] = (),
        routing_state: dict[str, Any] | None = None,
    ) -> dict:
        run_id = str(uuid4())

        if self.tools is not None:
            project_id = str(
                (routing_state or {}).get("selected_project_id")
                or self.query.agent.metadata.get("project_id", "cip-dmd")
            )
            context = ToolContext(
                organization_id=organization_id,
                user_id=user_id,
                project_id=project_id,
                run_id=run_id,
                roles=tuple(roles),
                routing=routing_state or {},
            )
            use_graph, use_documents = _tool_selection(question)
            document_invocation = None
            if use_documents:
                document_invocation = self.tools.invoke(
                    "search_docs_tool",
                    {
                        "query": question,
                        "top_k": 5,
                        "current_only": True,
                        "document_types": [],
                    },
                    context,
                )
            if not use_graph and document_invocation is not None:
                documents = document_invocation.output
                return {
                    "question": question,
                    "answer": documents["answer"],
                    "status": documents["status"],
                    "cypher": "",
                    "rows": [],
                    "row_count": 0,
                    "metadata": {
                        "project_id": project_id,
                        "rag_index_version": documents["index_version"],
                    },
                    "evidence": {
                        "nodes": [],
                        "relationships": [],
                        "node_count": 0,
                        "relationship_count": 0,
                        "documents": documents["matches"],
                    },
                    "validation": {
                        "attempts": 1,
                        "errors": [],
                        "trace": [
                            {
                                "step": "search_docs_tool",
                                "match_count": len(documents["matches"]),
                            }
                        ],
                        "tool_trace": [document_invocation.trace],
                        "elapsed_ms": document_invocation.trace["elapsed_ms"],
                        "execution_verified": bool(documents["matches"]),
                    },
                    "usage": {},
                    "provider": "llamaindex",
                    "run_id": run_id,
                    "thread_id": None,
                    "routing": routing_state or {},
                }

            graph_invocation = self.tools.invoke(
                "graph_query_tool",
                {
                    "question": question,
                    "routing_state": routing_state or {},
                },
                context,
            )
            result = graph_invocation.output
            validation = dict(result.get("validation", {}))
            tool_trace = [graph_invocation.trace]
            if document_invocation is not None:
                documents = document_invocation.output
                evidence = dict(result.get("evidence", {}))
                evidence["documents"] = documents["matches"]
                result["evidence"] = evidence
                tool_trace.append(document_invocation.trace)
                if documents["matches"]:
                    result["answer"] = (
                        result["answer"]
                        + "\n\n문서 근거\n"
                        + documents["answer"]
                    )
            validation["tool_trace"] = [
                *tool_trace,
                *validation.get("tool_trace", []),
            ]
            result["validation"] = validation
            return result

        def invoke(service: Any) -> dict:
            parameters = signature(service.query).parameters
            accepts_context = (
                "organization_id" in parameters
                or any(
                    parameter.kind is Parameter.VAR_KEYWORD
                    for parameter in parameters.values()
                )
            )
            if not accepts_context:
                return service.query(question)
            return service.query(
                question,
                organization_id=organization_id,
                user_id=user_id,
                roles=roles,
                run_id=run_id,
                routing_state=routing_state,
            )

        try:
            return invoke(self.query)
        except Exception as primary_error:
            if self.fallback_query is None:
                raise
            fallback = invoke(self.fallback_query)
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
    processed_root = project_root / "data" / "processed"
    try:
        checkpoint_store = build_checkpoint_store(project_root, project_id)
    except Exception:
        driver.close()
        raise
    agent_metadata = {
        **agent_metadata,
        "checkpoint_backend": checkpoint_store.backend,
    }
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
        checkpointer=checkpoint_store.saver,
        checkpoint_namespace=f"text2cypher:{resolved_provider}",
    )
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
                checkpointer=checkpoint_store.saver,
                checkpoint_namespace="text2cypher:gold-fallback",
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
    primary_query = QueryService(
        agent,
        audit_log_path=audit_log_path,
        provider=resolved_provider,
        usage_reader=(
            model.usage_summary
            if hasattr(model, "usage_summary")
            else None
        ),
    )

    def invoke_query_service(
        service: QueryService,
        payload: GraphQueryInput,
        context: ToolContext,
    ) -> dict[str, Any]:
        return service.query(
            payload.question,
            organization_id=context.organization_id,
            user_id=context.user_id,
            roles=context.roles,
            run_id=context.run_id,
            routing_state=payload.routing_state or context.routing,
        )

    def graph_query_handler(
        payload: GraphQueryInput,
        context: ToolContext,
    ) -> dict[str, Any]:
        try:
            return invoke_query_service(primary_query, payload, context)
        except Exception as primary_error:
            if fallback_query is None:
                raise
            fallback = invoke_query_service(fallback_query, payload, context)
            if fallback.get("status") == "unsupported":
                raise primary_error
            fallback["fallback_reason"] = str(primary_error)
            fallback["answer"] = (
                "실시간 생성 모델 연결이 불안정해 검증된 Gold 쿼리로 "
                "안전하게 전환했습니다. " + fallback["answer"]
            )
            return fallback

    document_rag = DocumentRagService(
        project_root,
        project_id,
        similarity_cutoff=float(os.getenv("P3_RAG_SIMILARITY_CUTOFF", "0.04")),
    )
    _bootstrap_rag_fixtures(document_rag, project_root, project_id)

    def search_docs_handler(
        payload: SearchDocsInput,
        context: ToolContext,
    ) -> dict[str, Any]:
        return document_rag.search(
            payload.query,
            roles=context.roles,
            top_k=payload.top_k,
            current_only=payload.current_only,
            document_types=payload.document_types,
        )

    tools = build_project_tool_registry(
        project_root=project_root,
        project_id=project_id,
        graph_query_handler=graph_query_handler,
        search_docs_handler=search_docs_handler,
        audit_log_path=project_processed_root / "tool_audit.jsonl",
        graph_timeout_seconds=agent_timeout_seconds + 5.0,
    )
    return ServiceBundle(
        driver=driver,
        query=primary_query,
        fallback_query=fallback_query,
        dashboard=dashboard,
        graph=GraphCatalogService(driver=driver, database=database),
        feedback=FeedbackService(
            project_processed_root / "expert_feedback.jsonl"
        ),
        provider=resolved_provider,
        model_name=resolved_model_name,
        checkpoint_store=checkpoint_store,
        tools=tools,
        document_rag=document_rag,
    )
