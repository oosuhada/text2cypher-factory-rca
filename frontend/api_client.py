"""HTTP adapters that let Streamlit use the same FastAPI boundary as Next.js."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any

import httpx


class ApiRequestError(RuntimeError):
    """Raised when the shared application API cannot complete a request."""


class FactoryGraphApiClient:
    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout: float = 30.0,
        client: httpx.Client | None = None,
    ):
        self.base_url = (
            base_url
            or os.getenv("P3_API_BASE_URL")
            or "http://127.0.0.1:8000"
        ).rstrip("/")
        self._owns_client = client is None
        self.client = client or httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers={"Accept": "application/json"},
        )

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            response = self.client.request(
                method,
                path,
                params=params,
                json=json,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            detail = error.response.text
            try:
                detail = error.response.json().get("detail", detail)
            except (ValueError, AttributeError):
                pass
            raise ApiRequestError(
                f"API {method} {path} 실패 "
                f"({error.response.status_code}): {detail}"
            ) from error
        except httpx.HTTPError as error:
            raise ApiRequestError(
                f"API {method} {path} 연결 실패: {error}"
            ) from error
        payload = response.json()
        if not isinstance(payload, dict):
            raise ApiRequestError(f"API {path} 응답이 JSON 객체가 아닙니다.")
        return payload

    def live(self) -> bool:
        try:
            return self._request("GET", "/api/v1/health/live").get(
                "status"
            ) == "alive"
        except ApiRequestError:
            return False

    def runtime(
        self, project_id: str | None = None
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            "/api/v1/runtime",
            params={"project_id": project_id} if project_id else None,
        )

    def query(
        self, question: str, project_id: str | None = None
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/query",
            json={"question": question, "project_id": project_id},
        )

    def projects(self) -> list[dict[str, Any]]:
        response = self.client.get("/api/v1/projects")
        response.raise_for_status()
        return response.json()

    def activate_project(self, project_id: str) -> dict[str, Any]:
        return self._request(
            "POST", f"/api/v1/projects/{project_id}/activate"
        )

    def load_project_graph(
        self, project_id: str, upload_id: str
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/projects/{project_id}/graph/load",
            json={
                "upload_id": upload_id,
                "confirm_project_id": project_id,
            },
        )

    def metrics(
        self, project_id: str | None = None
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            "/api/v1/metrics",
            params={"project_id": project_id} if project_id else None,
        )

    def search_nodes(
        self,
        label: str,
        query: str,
        limit: int,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            "/api/v1/graph/search",
            params={
                "label": label,
                "q": query,
                "limit": limit,
                **(
                    {"project_id": project_id}
                    if project_id
                    else {}
                ),
            },
        )

    def subgraph(
        self,
        label: str,
        identity: str,
        depth: int,
        limit: int,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            "/api/v1/graph/subgraph",
            params={
                "label": label,
                "identity": identity,
                "depth": depth,
                "limit": limit,
                **(
                    {"project_id": project_id}
                    if project_id
                    else {}
                ),
            },
        )

    def record_feedback(self, **payload: Any) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/feedback",
            json=payload,
        )

    def feedback_summary(
        self, project_id: str | None = None
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            "/api/v1/feedback/summary",
            params={"project_id": project_id} if project_id else None,
        )


@dataclass
class _ApiDashboard:
    api: FactoryGraphApiClient
    project_id: str

    def snapshot(self) -> dict[str, Any]:
        return self.api.metrics(self.project_id)


@dataclass
class _ApiGraph:
    api: FactoryGraphApiClient
    project_id: str

    def search_nodes(
        self, label: str, query: str, limit: int
    ) -> dict[str, Any]:
        return self.api.search_nodes(
            label, query, limit, self.project_id
        )

    def subgraph(
        self,
        label: str,
        identity: str,
        depth: int,
        limit: int,
    ) -> dict[str, Any]:
        return self.api.subgraph(
            label, identity, depth, limit, self.project_id
        )


@dataclass
class _ApiFeedback:
    api: FactoryGraphApiClient
    project_id: str

    def record_review(self, **payload: Any) -> dict[str, Any]:
        return self.api.record_feedback(
            project_id=self.project_id, **payload
        )

    def summary(self) -> dict[str, Any]:
        return self.api.feedback_summary(self.project_id)


class ApiServiceBundle:
    """ServiceBundle-compatible facade backed by FastAPI."""

    def __init__(
        self, api: FactoryGraphApiClient, project_id: str | None = None
    ):
        self.api = api
        runtime = api.runtime(project_id)
        self.provider = str(runtime.get("provider", "api"))
        self.model_name = str(runtime.get("model_name", "server-managed"))
        self.transport = "api"
        self.project_id = str(
            runtime.get("active_project_id", project_id or "cip-dmd")
        )
        self.dashboard = _ApiDashboard(api, self.project_id)
        self.graph = _ApiGraph(api, self.project_id)
        self.feedback = _ApiFeedback(api, self.project_id)

    def query_with_fallback(self, question: str) -> dict[str, Any]:
        return self.api.query(question, self.project_id)

    def close(self) -> None:
        self.api.close()
