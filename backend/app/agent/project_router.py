"""Deterministic project router for questions without an explicit project."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import re
from typing import Any, Iterable

from backend.app.projects import ProjectRegistry
from backend.app.schema_registry import SchemaRegistry


_TOKEN_PATTERN = re.compile(r"[0-9A-Za-z가-힣_]+")
_DEFAULT_DIMENSIONS = 384


@dataclass(frozen=True)
class ProjectCandidate:
    project_id: str
    name: str
    domain_type: str
    summary: str
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class RoutingDecision:
    status: str
    selected_project_id: str | None
    confidence: float | None
    candidates: tuple[dict[str, Any], ...]
    reason: str
    mode: str

    def as_state(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "selected_project_id": self.selected_project_id,
            "confidence": self.confidence,
            "candidates": [dict(candidate) for candidate in self.candidates],
            "reason": self.reason,
            "mode": self.mode,
        }


def _tokens(text: str) -> list[str]:
    normalized = text.lower().replace("-", " ")
    words = [token for token in _TOKEN_PATTERN.findall(normalized) if len(token) > 1]
    korean_ngrams: list[str] = []
    for word in words:
        if re.search(r"[가-힣]", word):
            korean_ngrams.extend(
                word[index : index + 2]
                for index in range(max(0, len(word) - 1))
            )
    return words + korean_ngrams


def _hashed_embedding(text: str, dimensions: int = _DEFAULT_DIMENSIONS) -> list[float]:
    vector = [0.0] * dimensions
    for token in _tokens(text):
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[bucket] += sign
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def _cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def _schema_terms(manifest: dict[str, Any]) -> list[str]:
    terms: list[str] = [
        str(manifest.get("title", "")),
        str(manifest.get("project_id", "")),
    ]
    for node in manifest.get("nodes", []):
        terms.append(str(node.get("label", "")))
        terms.extend(str(item) for item in (node.get("properties") or {}))
    for relationship in manifest.get("relationships", []):
        terms.append(str(relationship.get("type", "")))
    for values in (manifest.get("domain_values") or {}).values():
        terms.extend(str(value) for value in values)
    for scenario in manifest.get("query_scenarios", []):
        terms.append(str(scenario.get("question", "")))
    return terms


def _project_aliases(project_id: str, domain_type: str) -> tuple[str, ...]:
    aliases: dict[str, tuple[str, ...]] = {
        "cip-dmd": (
            "완제품",
            "구성품",
            "부품",
            "genealogy",
            "품질검사",
            "압력검사",
            "표면거칠기",
            "공정",
            "조립",
            "anomaly",
            "cylinder",
            "piston rod",
            "cylinder bottom",
        ),
        "equipment-history": (
            "정비",
            "유지보수",
            "보전",
            "수리",
            "교체",
            "점검",
            "다운타임",
            "정비비용",
            "기술자",
            "technician",
            "maintenance",
            "repair",
            "replacement",
            "eq-press",
        ),
    }
    return aliases.get(project_id, (domain_type, project_id))


class ProjectRouter:
    """Route only when the caller has not explicitly selected a project."""

    def __init__(
        self,
        projects: ProjectRegistry,
        schemas: SchemaRegistry,
        *,
        confidence_threshold: float = 0.08,
        margin_threshold: float = 0.04,
        top_k: int = 3,
    ):
        if not 0 < confidence_threshold <= 1:
            raise ValueError("confidence_threshold must be within (0, 1].")
        if not 0 <= margin_threshold <= 1:
            raise ValueError("margin_threshold must be within [0, 1].")
        if top_k < 1:
            raise ValueError("top_k must be positive.")
        self.projects = projects
        self.schemas = schemas
        self.confidence_threshold = confidence_threshold
        self.margin_threshold = margin_threshold
        self.top_k = top_k

    def candidates(self) -> list[ProjectCandidate]:
        candidates: list[ProjectCandidate] = []
        for project in self.projects.list():
            if project.get("status") != "ready":
                continue
            project_id = str(project["project_id"])
            try:
                manifest = self.schemas.load(project_id)
            except (KeyError, ValueError):
                continue
            aliases = _project_aliases(project_id, str(project["domain_type"]))
            summary_parts = [
                str(project.get("name", "")),
                str(project.get("description", "")),
                str(project.get("domain_type", "")),
                str(project.get("dataset_name", "")),
                *aliases,
                *_schema_terms(manifest),
            ]
            candidates.append(
                ProjectCandidate(
                    project_id=project_id,
                    name=str(project["name"]),
                    domain_type=str(project["domain_type"]),
                    summary=" ".join(part for part in summary_parts if part),
                    keywords=tuple(alias.lower() for alias in aliases),
                )
            )
        return candidates

    @staticmethod
    def _keyword_score(question: str, candidate: ProjectCandidate) -> float:
        normalized = question.lower()
        matched = sum(keyword in normalized for keyword in candidate.keywords)
        return min(1.0, matched / 2.0)

    def route(
        self,
        question: str,
        *,
        explicit_project_id: str | None = None,
    ) -> RoutingDecision:
        if explicit_project_id:
            self.projects.require(explicit_project_id)
            return RoutingDecision(
                status="explicit_project",
                selected_project_id=explicit_project_id,
                confidence=1.0,
                candidates=(),
                reason="project_id was explicitly supplied by the caller",
                mode="bypass",
            )

        available = self.candidates()
        if not available:
            return RoutingDecision(
                status="needs_clarification",
                selected_project_id=None,
                confidence=None,
                candidates=(),
                reason="no ready project with a valid schema is available",
                mode="automatic",
            )

        query_vector = _hashed_embedding(question)
        scored: list[dict[str, Any]] = []
        for candidate in available:
            semantic = max(0.0, _cosine(query_vector, _hashed_embedding(candidate.summary)))
            keyword = self._keyword_score(question, candidate)
            score = min(1.0, 0.68 * semantic + 0.32 * keyword)
            scored.append(
                {
                    "project_id": candidate.project_id,
                    "name": candidate.name,
                    "domain_type": candidate.domain_type,
                    "score": round(score, 6),
                    "semantic_score": round(semantic, 6),
                    "keyword_score": round(keyword, 6),
                }
            )
        scored.sort(key=lambda item: (-item["score"], item["project_id"]))
        ranked = tuple(scored[: self.top_k])
        winner = scored[0]
        runner_up = scored[1]["score"] if len(scored) > 1 else 0.0
        margin = winner["score"] - runner_up

        if (
            winner["score"] < self.confidence_threshold
            or margin < self.margin_threshold
        ):
            return RoutingDecision(
                status="needs_clarification",
                selected_project_id=None,
                confidence=winner["score"],
                candidates=ranked,
                reason=(
                    "automatic routing confidence or winner margin is below "
                    f"threshold; confidence={winner['score']:.3f}, margin={margin:.3f}"
                ),
                mode="automatic",
            )

        return RoutingDecision(
            status="routed",
            selected_project_id=str(winner["project_id"]),
            confidence=float(winner["score"]),
            candidates=ranked,
            reason=(
                "selected by hashed semantic similarity and domain keyword evidence; "
                f"margin={margin:.3f}"
            ),
            mode="automatic",
        )


def route_accuracy(
    router: ProjectRouter,
    cases: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    top1_correct = 0
    topk_correct = 0
    clarification_correct = 0
    clarification_expected = 0
    for case in cases:
        decision = router.route(str(case["question"]))
        expected = case.get("expected_project_id")
        expected_status = case.get("expected_status", "routed")
        ranked_ids = [item["project_id"] for item in decision.candidates]
        top1 = decision.selected_project_id == expected
        topk = expected in ranked_ids if expected else decision.selected_project_id is None
        if expected_status == "needs_clarification":
            clarification_expected += 1
            clarification_correct += decision.status == "needs_clarification"
        else:
            top1_correct += top1
            topk_correct += topk
        rows.append(
            {
                "id": case.get("id"),
                "question": case["question"],
                "expected_project_id": expected,
                "expected_status": expected_status,
                "actual_project_id": decision.selected_project_id,
                "actual_status": decision.status,
                "confidence": decision.confidence,
                "ranked_project_ids": ranked_ids,
                "top1_correct": top1,
                "topk_correct": topk,
            }
        )
    routed_count = len(rows) - clarification_expected
    return {
        "case_count": len(rows),
        "routed_case_count": routed_count,
        "clarification_case_count": clarification_expected,
        "top1_accuracy": top1_correct / routed_count if routed_count else 1.0,
        "topk_accuracy": topk_correct / routed_count if routed_count else 1.0,
        "clarification_accuracy": (
            clarification_correct / clarification_expected
            if clarification_expected
            else 1.0
        ),
        "rows": rows,
    }
