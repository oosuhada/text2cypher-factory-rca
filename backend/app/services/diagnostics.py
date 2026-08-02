"""Read-only environment and demo readiness checks."""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import socket
from typing import Any
from urllib.parse import urlparse

from backend.app.agent.model import has_vertex_credentials
from backend.app.etl.extract import QUALITY_CSV_SPECS, SOURCE_SPECS


def latest_successful_etl(processed_root: Path) -> dict[str, Any] | None:
    runs_root = processed_root / "etl_runs"
    candidates = []
    for path in sorted(runs_root.glob("etl_*.json"), reverse=True):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if report.get("mode") == "load" and report.get("status") == "PASS":
            report["_report_path"] = str(path)
            candidates.append(report)
    return candidates[0] if candidates else None


def format_timestamp(value: str | None) -> str:
    if not value:
        return "기록 없음"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return parsed.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def _neo4j_endpoint() -> tuple[str, int]:
    uri = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
    parsed = urlparse(uri)
    return parsed.hostname or "localhost", parsed.port or 7687


def _neo4j_port_ready(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def collect_demo_diagnostics(project_root: Path) -> list[dict[str, Any]]:
    raw_root = project_root / "data" / "raw" / "cip_dmd"
    processed_root = project_root / "data" / "processed"
    required_sources = [
        raw_root / spec[0] for spec in SOURCE_SPECS
    ] + [raw_root / relative for relative in QUALITY_CSV_SPECS]
    missing_sources = [path for path in required_sources if not path.is_file()]
    etl = latest_successful_etl(processed_root)
    metrics_path = project_root / "evaluation" / "metrics.json"
    blind_path = project_root / "evaluation" / "results" / "latest.json"
    llm_ready = bool(os.getenv("OPENAI_API_KEY")) or has_vertex_credentials()
    neo4j_host, neo4j_port = _neo4j_endpoint()
    neo4j_ready = _neo4j_port_ready(neo4j_host, neo4j_port)
    return [
        {
            "check": "CiP-DMD 원본",
            "status": "PASS" if not missing_sources else "FAIL",
            "detail": (
                f"필수 파일 {len(required_sources)}개 확인"
                if not missing_sources
                else f"누락 {len(missing_sources)}개"
            ),
            "required": True,
        },
        {
            "check": "최근 ETL",
            "status": "PASS" if etl else "FAIL",
            "detail": (
                format_timestamp((etl or {}).get("finished_at"))
                if etl
                else "성공한 load 기록 없음"
            ),
            "required": True,
        },
        {
            "check": "Neo4j",
            "status": "PASS" if neo4j_ready else "FAIL",
            "detail": (
                f"{neo4j_host}:{neo4j_port} 연결"
                if neo4j_ready
                else f"{neo4j_host}:{neo4j_port} 연결 불가"
            ),
            "required": True,
        },
        {
            "check": "생성 모델",
            "status": "PASS" if llm_ready else "FALLBACK",
            "detail": (
                "OpenAI 또는 Vertex 인증 확인"
                if llm_ready
                else "Gold 고정 데모만 사용 가능"
            ),
            "required": False,
        },
        {
            "check": "평가 결과",
            "status": (
                "PASS"
                if metrics_path.is_file() and blind_path.is_file()
                else "FAIL"
            ),
            "detail": "Blind·회귀 지표 확인",
            "required": True,
        },
    ]


def diagnostics_pass(checks: list[dict[str, Any]]) -> bool:
    return all(
        check["status"] == "PASS"
        for check in checks
        if check.get("required")
    )
