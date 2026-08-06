"""Streamlit service composition through the shared FastAPI boundary."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.app.services.bootstrap import ServiceBundle, build_service_bundle
from backend.app.schema_registry import SchemaRegistry
from backend.app.services.graph_service import node_search_contract
from frontend.api_client import (
    ApiRequestError,
    ApiServiceBundle,
    FactoryGraphApiClient,
)


@dataclass
class _DirectProjectGraph:
    """Bind direct Neo4j reads to the same project contract as the API."""

    graph: Any
    project_id: str
    contract: dict[str, Any]

    def _node_contract(self, label: str) -> dict[str, Any]:
        try:
            return next(
                node
                for node in self.contract["nodes"]
                if node["label"] == label
            )
        except StopIteration as error:
            raise ValueError(
                f"지원하지 않는 노드 라벨입니다: {label}"
            ) from error

    def search_nodes(
        self, label: str, query: str, limit: int
    ) -> dict[str, Any]:
        identity, search_properties = node_search_contract(
            self.contract, label
        )
        if self.project_id == "cip-dmd":
            return self.graph.search_nodes(label, query, limit)
        return self.graph.search_nodes(
            label,
            query,
            limit,
            project_id=self.project_id,
            identity_property=identity,
            search_properties=search_properties,
        )

    def subgraph(
        self,
        label: str,
        identity: str,
        depth: int,
        limit: int,
    ) -> dict[str, Any]:
        node = self._node_contract(label)
        if self.project_id == "cip-dmd":
            return self.graph.subgraph(
                label, identity, depth, limit
            )
        return self.graph.subgraph(
            label,
            identity,
            depth,
            limit,
            project_id=self.project_id,
            identity_property=str(node["identity"]),
        )


def build_streamlit_service_bundle(
    project_root: Path,
    provider: str = "auto",
    model_name: str | None = None,
    *,
    transport: str | None = None,
    project_id: str = "cip-dmd",
    schema_context: str | None = None,
) -> ServiceBundle | ApiServiceBundle:
    """Prefer FastAPI while preserving an explicit local-service fallback."""

    resolved_transport = (
        transport or os.getenv("P3_STREAMLIT_TRANSPORT", "auto")
    ).strip().lower()
    if resolved_transport not in {"auto", "api", "direct"}:
        raise ValueError(
            "P3_STREAMLIT_TRANSPORT는 auto, api, direct 중 하나여야 합니다."
        )
    # An explicit model choice in the Streamlit UI must not be silently
    # ignored by an already-running API configured with another provider.
    # Operators can still force centralized API mode with
    # P3_STREAMLIT_TRANSPORT=api.
    if resolved_transport == "auto" and provider != "auto":
        resolved_transport = "direct"
    if resolved_transport in {"auto", "api"}:
        api = FactoryGraphApiClient()
        if api.live():
            try:
                return ApiServiceBundle(api, project_id=project_id)
            except ApiRequestError:
                api.close()
                if resolved_transport == "api":
                    raise
        else:
            api.close()
        if resolved_transport == "api":
            raise RuntimeError(
                "FastAPI가 준비되지 않았습니다. P3_API_BASE_URL과 "
                "/api/v1/health/live를 확인하세요."
            )
    bundle = build_service_bundle(
        project_root=project_root,
        provider=provider,
        model_name=model_name,
        project_id=project_id,
        schema_context=schema_context,
    )
    if bundle.graph is not None:
        contract = SchemaRegistry(
            project_root / "schemas"
        ).contract(project_id)
        bundle.graph = _DirectProjectGraph(
            graph=bundle.graph,
            project_id=project_id,
            contract=contract,
        )
    setattr(bundle, "transport", "direct")
    return bundle


__all__: list[str] = [
    "ApiServiceBundle",
    "ServiceBundle",
    "build_service_bundle",
    "build_streamlit_service_bundle",
]
