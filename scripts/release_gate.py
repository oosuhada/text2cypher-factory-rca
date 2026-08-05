#!/usr/bin/env python3
"""Deterministic backend release contract, traceability, and secret gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SECRET_PATTERNS = {
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "openai-key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "google-api-key": re.compile(r"\bAIza[A-Za-z0-9_-]{30,}\b"),
    "aws-access-key": re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    "github-token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
}
FORBIDDEN_TRACKED_NAMES = {
    ".env",
    ".env.local",
    "service-account.json",
    "credentials.json",
}
REQUIRED_API_PATHS = {
    "/api/v1/health/live",
    "/api/v1/projects",
    "/api/v1/projects/{project_id}/readiness",
    "/api/v1/projects/{project_id}/readiness/promote",
    "/api/v1/projects/{project_id}/uploads/profile",
    "/api/v1/projects/{project_id}/mappings/approve",
    "/api/v1/projects/{project_id}/graph/load",
    "/api/v1/projects/{project_id}/connectors/neo4j/validate",
    (
        "/api/v1/projects/{project_id}/connectors/neo4j/"
        "{connector_id}/approve"
    ),
    "/api/v1/query",
    "/api/v1/graph/schema",
}
REQUIRED_RELEASE_DOCUMENTS = {
    "docs/api-contract.md",
    "docs/backend-lineage.md",
    "docs/backend-troubleshooting.md",
    "docs/module-ownership.md",
    "docs/final-presentation-evidence-pack.md",
    "docs/p3-requirements-traceability.md",
    "docs/presentation-limitations.md",
    "release/backend-v1.yml",
}


def tracked_files(root: Path = PROJECT_ROOT) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return [
        root / item.decode("utf-8")
        for item in result.stdout.split(b"\0")
        if item
    ]


def scan_secrets(paths: Iterable[Path]) -> list[str]:
    findings: list[str] = []
    for path in paths:
        if path.name in FORBIDDEN_TRACKED_NAMES:
            findings.append(f"forbidden-file:{path.name}")
            continue
        try:
            if path.stat().st_size > 2_000_000:
                continue
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        try:
            display_path = path.relative_to(PROJECT_ROOT)
        except ValueError:
            display_path = path
        for name, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                findings.append(f"{name}:{display_path}")
    return sorted(findings)


def validate_openapi() -> dict[str, int]:
    sys.path.insert(0, str(PROJECT_ROOT))
    from backend.app.api.main import create_app
    from backend.app.projects import ProjectRegistry

    with tempfile.TemporaryDirectory() as directory:
        registry = ProjectRegistry(Path(directory) / "projects.sqlite3")
        document = create_app(project_registry=registry).openapi()
    paths = set(document.get("paths", {}))
    missing = sorted(REQUIRED_API_PATHS - paths)
    if missing:
        raise RuntimeError(f"OpenAPI 필수 endpoint 누락: {missing}")
    schemas = document.get("components", {}).get("schemas", {})
    for schema_name in ("ErrorEnvelope", "ProjectReadinessResponse"):
        if schema_name not in schemas:
            raise RuntimeError(f"OpenAPI schema 누락: {schema_name}")
    documented_errors = document["paths"]["/api/v1/query"]["post"][
        "responses"
    ]
    for status_code in ("409", "422", "502"):
        if status_code not in documented_errors:
            raise RuntimeError(
                f"query API error response 누락: HTTP {status_code}"
            )
    return {"paths": len(paths), "schemas": len(schemas)}


def validate_traceability() -> int:
    path = PROJECT_ROOT / "docs" / "p3-requirements-traceability.md"
    text = path.read_text(encoding="utf-8")
    incomplete = [
        line
        for line in text.splitlines()
        if line.startswith("| FR-") or line.startswith("| NFR-")
        if "| 완료 |" not in line
    ]
    if incomplete:
        raise RuntimeError(
            "P3 필수 요구사항이 100% 완료가 아닙니다:\n"
            + "\n".join(incomplete)
        )
    return sum(
        line.startswith("| FR-") or line.startswith("| NFR-")
        for line in text.splitlines()
    )


def validate_release_documents() -> int:
    missing = sorted(
        path
        for path in REQUIRED_RELEASE_DOCUMENTS
        if not (PROJECT_ROOT / path).is_file()
    )
    if missing:
        raise RuntimeError(f"릴리스 문서 누락: {missing}")
    return len(REQUIRED_RELEASE_DOCUMENTS)


def run_gate() -> dict[str, object]:
    findings = scan_secrets(tracked_files())
    if findings:
        raise RuntimeError(
            "추적 파일에서 비밀정보 후보를 발견했습니다:\n"
            + "\n".join(findings)
        )
    openapi = validate_openapi()
    requirement_count = validate_traceability()
    document_count = validate_release_documents()
    return {
        "status": "PASS",
        "secret_findings": 0,
        "openapi": openapi,
        "completed_requirements": requirement_count,
        "release_documents": document_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run_gate()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(
            "Backend release contract PASS · "
            f"{result['completed_requirements']} requirements · "
            f"{result['openapi']['paths']} API paths · secrets 0"
        )


if __name__ == "__main__":
    main()
