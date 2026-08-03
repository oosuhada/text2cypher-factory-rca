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

    def runtime(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/runtime")

    def query(self, question: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/query",
            json={"question": question},
        )

    def metrics(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/metrics")

    def search_nodes(
        self, label: str, query: str, limit: int
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            "/api/v1/graph/search",
            params={"label": label, "q": query, "limit": limit},
        )

    def subgraph(
        self,
        label: str,
        identity: str,
        depth: int,
        limit: int,
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            "/api/v1/graph/subgraph",
            params={
                "label": label,
                "identity": identity,
                "depth": depth,
                "limit": limit,
            },
        )

    def record_feedback(self, **payload: Any) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/feedback",
            json=payload,
        )

    def feedback_summary(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/feedback/summary")


@dataclass
class _ApiDashboard:
    api: FactoryGraphApiClient

    def snapshot(self) -> dict[str, Any]:
        return self.api.metrics()


@dataclass
class _ApiGraph:
    api: FactoryGraphApiClient

    def search_nodes(
        self, label: str, query: str, limit: int
    ) -> dict[str, Any]:
        return self.api.search_nodes(label, query, limit)

    def subgraph(
        self,
        label: str,
        identity: str,
        depth: int,
        limit: int,
    ) -> dict[str, Any]:
        return self.api.subgraph(label, identity, depth, limit)


@dataclass
class _ApiFeedback:
    api: FactoryGraphApiClient

    def record_review(self, **payload: Any) -> dict[str, Any]:
        return self.api.record_feedback(**payload)

    def summary(self) -> dict[str, Any]:
        return self.api.feedback_summary()


class ApiServiceBundle:
    """ServiceBundle-compatible facade backed by FastAPI."""

    def __init__(self, api: FactoryGraphApiClient):
        self.api = api
        runtime = api.runtime()
        self.provider = str(runtime.get("provider", "api"))
        self.model_name = str(runtime.get("model_name", "server-managed"))
        self.transport = "api"
        self.dashboard = _ApiDashboard(api)
        self.graph = _ApiGraph(api)
        self.feedback = _ApiFeedback(api)

    def query_with_fallback(self, question: str) -> dict[str, Any]:
        return self.api.query(question)

    def close(self) -> None:
        self.api.close()

