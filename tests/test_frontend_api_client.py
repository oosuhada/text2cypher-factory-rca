import unittest

import httpx

from frontend.api_client import ApiRequestError, ApiServiceBundle, FactoryGraphApiClient


class FrontendApiClientTest(unittest.TestCase):
    def build_client(self, handler):
        transport = httpx.MockTransport(handler)
        return FactoryGraphApiClient(
            "http://api.test",
            client=httpx.Client(
                base_url="http://api.test",
                transport=transport,
            ),
        )

    def test_service_bundle_uses_shared_runtime_and_query_contract(self):
        def handler(request):
            if request.url.path == "/api/v1/runtime":
                return httpx.Response(
                    200,
                    json={
                        "provider": "gemini",
                        "model_name": "gemini-2.5-flash",
                        "transport": "service",
                    },
                )
            if request.url.path == "/api/v1/query":
                return httpx.Response(
                    200,
                    json={
                        "question": "q",
                        "answer": "a",
                        "status": "success",
                        "rows": [],
                        "row_count": 0,
                    },
                )
            raise AssertionError(request.url.path)

        bundle = ApiServiceBundle(self.build_client(handler))
        self.assertEqual(bundle.provider, "gemini")
        self.assertEqual(bundle.transport, "api")
        self.assertEqual(
            bundle.query_with_fallback("q")["status"], "success"
        )

    def test_http_errors_are_mapped_to_actionable_exception(self):
        client = self.build_client(
            lambda request: httpx.Response(
                503, json={"detail": "Neo4j unavailable"}
            )
        )
        with self.assertRaisesRegex(ApiRequestError, "Neo4j unavailable"):
            client.metrics()

