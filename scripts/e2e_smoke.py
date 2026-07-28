#!/usr/bin/env python3
"""Black-box smoke test for the packaged FactoryGraph RCA services."""

from __future__ import annotations

import argparse
import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEMO_QUESTION = (
    "완제품 300002의 구성품, 각 구성품의 공정과 품질검사 결과를 보여줘."
)


def request(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: float = 5,
) -> tuple[int, dict[str, str], bytes]:
    body = (
        json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if payload is not None
        else None
    )
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    with urlopen(
        Request(url, data=body, headers=headers, method=method),
        timeout=timeout,
    ) as response:
        return (
            response.status,
            {key.lower(): value for key, value in response.headers.items()},
            response.read(),
        )


def wait_until_ready(url: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            status, _, _ = request(url, timeout=2)
            if status == 200:
                return
        except (HTTPError, URLError, TimeoutError) as error:
            last_error = error
        time.sleep(0.5)
    raise RuntimeError(f"서비스 준비 시간 초과: {url} ({last_error})")


def expect_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    status, headers, body = request(url, method=method, payload=payload)
    if status not in {200, 201}:
        raise RuntimeError(f"예상하지 못한 HTTP {status}: {url}")
    return json.loads(body), headers


def expect_error(
    url: str,
    *,
    expected_status: int,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    try:
        request(url, method=method, payload=payload)
    except HTTPError as error:
        headers = {
            key.lower(): value for key, value in error.headers.items()
        }
        body = json.loads(error.read())
        if error.code != expected_status:
            raise RuntimeError(
                f"HTTP {expected_status} 대신 {error.code}: {url}"
            ) from error
        return body, headers
    raise RuntimeError(f"예상한 HTTP {expected_status} 오류가 없습니다: {url}")


def check_api(api_url: str) -> None:
    live, headers = expect_json(f"{api_url}/api/v1/health/live")
    if live != {"status": "alive"}:
        raise RuntimeError(f"잘못된 liveness 응답: {live}")
    if headers.get("x-content-type-options") != "nosniff":
        raise RuntimeError("API 보안 헤더 X-Content-Type-Options가 없습니다.")

    schema, _ = expect_json(f"{api_url}/api/v1/graph/schema")
    labels = {row["label"] for row in schema["node_identities"]}
    if "Part" not in labels or "ASSEMBLED_FROM" not in schema[
        "relationship_types"
    ]:
        raise RuntimeError("그래프 스키마 계약이 불완전합니다.")

    readiness, _ = expect_json(
        f"{api_url}/api/v1/projects/cip-dmd/readiness"
    )
    if (
        not readiness["can_query"]
        or readiness["node_count"] < 1
        or readiness["next_action"] != "query"
    ):
        raise RuntimeError(
            f"기본 프로젝트 준비 상태가 올바르지 않습니다: {readiness}"
        )

    query_string = urlencode(
        {"label": "Cylinder", "q": "3000", "limit": 5}
    )
    search, _ = expect_json(
        f"{api_url}/api/v1/graph/search?{query_string}"
    )
    if search["count"] < 1:
        raise RuntimeError("실제 그래프 노드 검색 결과가 없습니다.")

    result, _ = expect_json(
        f"{api_url}/api/v1/query",
        method="POST",
        payload={"question": DEMO_QUESTION},
    )
    if result["status"] != "success" or result["row_count"] < 1:
        raise RuntimeError(f"Gold E2E 질의 실패: {result}")
    if not result.get("cypher"):
        raise RuntimeError("E2E 질의에 실행 Cypher가 없습니다.")

    feedback, _ = expect_json(f"{api_url}/api/v1/feedback/summary")
    if "decision_counts" not in feedback:
        raise RuntimeError("전문가 검증 요약 계약이 없습니다.")

    draft_id = f"release-gate-{int(time.time())}"
    draft, _ = expect_json(
        f"{api_url}/api/v1/projects",
        method="POST",
        payload={
            "project_id": draft_id,
            "name": "Release Gate Draft",
            "domain_type": "release-validation",
            "dataset_name": "empty",
        },
    )
    if draft["status"] != "draft":
        raise RuntimeError(f"새 프로젝트 상태가 draft가 아닙니다: {draft}")
    blocked, blocked_headers = expect_error(
        f"{api_url}/api/v1/query",
        expected_status=409,
        method="POST",
        payload={
            "project_id": draft_id,
            "question": "준비되지 않은 프로젝트를 조회해줘.",
        },
    )
    if blocked.get("error", {}).get("code") != "STATE_CONFLICT":
        raise RuntimeError(f"구조화된 readiness 오류가 없습니다: {blocked}")
    if (
        blocked.get("error", {}).get("request_id")
        != blocked_headers.get("x-request-id")
    ):
        raise RuntimeError("오류 body와 X-Request-ID가 일치하지 않습니다.")
    print(
        "API PASS · schema/search/query/feedback/error-contract · "
        f"{result['row_count']} rows"
    )


def check_html(url: str, markers: tuple[str, ...], label: str) -> None:
    status, headers, body = request(url)
    text = body.decode("utf-8", errors="replace")
    if status != 200 or not all(marker in text for marker in markers):
        raise RuntimeError(f"{label} 콘텐츠 검증 실패: {url}")
    if headers.get("x-content-type-options") != "nosniff":
        raise RuntimeError(f"{label} 보안 헤더가 없습니다.")
    print(f"{label} PASS · {url}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api-url", default="http://127.0.0.1:8000"
    )
    parser.add_argument(
        "--web-url", default="http://127.0.0.1:3000"
    )
    parser.add_argument(
        "--streamlit-url", default="http://127.0.0.1:8501"
    )
    parser.add_argument("--timeout", type=float, default=90)
    parser.add_argument("--skip-web", action="store_true")
    parser.add_argument("--skip-streamlit", action="store_true")
    args = parser.parse_args()

    wait_until_ready(f"{args.api_url}/api/v1/health/live", args.timeout)
    check_api(args.api_url)
    if not args.skip_web:
        wait_until_ready(args.web_url, args.timeout)
        check_html(
            args.web_url,
            ("FactoryGraph", "RCA"),
            "Next.js landing",
        )
        check_html(
            f"{args.web_url}/graph",
            ("Graph Explorer",),
            "Next.js graph",
        )
    if not args.skip_streamlit:
        health_url = f"{args.streamlit_url}/_stcore/health"
        wait_until_ready(health_url, args.timeout)
        status, _, body = request(health_url)
        if status != 200 or b"ok" not in body.lower():
            raise RuntimeError("Streamlit health check 실패")
        print("Streamlit PASS · health")
    print("FactoryGraph RCA E2E PASS")


if __name__ == "__main__":
    main()
