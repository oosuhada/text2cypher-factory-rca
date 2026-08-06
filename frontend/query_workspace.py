"""Query Studio presentation contracts independent from Streamlit."""

from __future__ import annotations

from typing import Any


DEFAULT_EXAMPLE_QUESTIONS = (
    (
        "제품 Genealogy",
        "완제품 300002의 구성품, 각 구성품의 공정과 품질검사 결과를 보여줘.",
    ),
    (
        "품질 실패 × 이상",
        "표면거칠기 검사에 실패한 cylinder bottom들의 밀링 anomaly 분포를 보여줘.",
    ),
    (
        "역방향 영향분석",
        "밀링 anomaly class 2가 발생한 cylinder bottom과 조립된 완제품의 최종 QC 결과를 보여줘.",
    ),
    (
        "없는 엔티티 검증",
        "완제품 399999의 구성품과 품질검사 결과를 보여줘.",
    ),
)
PROJECT_EXAMPLE_QUESTIONS = {
    "equipment-history": (
        ("설비 정비 이력", "EQ-PRESS-01의 정비 이력을 보여줘."),
        ("장비 중단시간", "누적 중단 시간이 가장 긴 장비를 보여줘."),
        ("미해결 이벤트", "아직 해결되지 않은 정비 이벤트를 보여줘."),
        ("없는 설비 검증", "EQ-UNKNOWN 설비의 정비 이력을 보여줘."),
    ),
}


def example_questions(project_id: str) -> tuple[tuple[str, str], ...]:
    """Return domain-safe examples instead of leaking another schema's terms."""
    return PROJECT_EXAMPLE_QUESTIONS.get(
        project_id,
        DEFAULT_EXAMPLE_QUESTIONS,
    )


def query_placeholder(project_id: str) -> str:
    if project_id == "equipment-history":
        return "예: EQ-PRESS-01의 정비 이력을 보여줘."
    return "예: 완제품 300002의 구성품과 공정 이력을 보여줘."


QUERY_STATUS = {
    "success": {
        "label": "조회 완료",
        "tone": "success",
        "description": "검증한 Cypher를 실행해 근거를 조회했습니다.",
    },
    "empty": {
        "label": "결과 없음",
        "tone": "info",
        "description": "정상 실행됐지만 조건과 일치하는 근거가 없습니다.",
    },
    "blocked": {
        "label": "요청 차단",
        "tone": "warning",
        "description": "읽기 전용 정책에 따라 실행 전에 차단했습니다.",
    },
    "failed": {
        "label": "처리 실패",
        "tone": "error",
        "description": "검증 또는 실행 실패로 답변을 보류했습니다.",
    },
    "needs_clarification": {
        "label": "조건 확인 필요",
        "tone": "info",
        "description": "실행 전에 질문 조건을 더 구체화해야 합니다.",
    },
    "unsupported": {
        "label": "지원 범위 밖",
        "tone": "info",
        "description": "현재 선택한 생성 모드가 이 질문을 지원하지 않습니다.",
    },
}


def query_status_presentation(status: str) -> dict[str, str]:
    return QUERY_STATUS.get(
        status,
        {
            "label": status,
            "tone": "neutral",
            "description": "알 수 없는 처리 상태입니다.",
        },
    )


def query_context_versions(
    project: dict[str, Any],
    response: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    metadata = (response or {}).get("metadata", {})
    return [
        {
            "label": "프로젝트",
            "value": str(project["project_id"]),
        },
        {
            "label": "데이터",
            "value": str(
                metadata.get("source_version")
                or project.get("source_version")
                or "미정"
            ),
        },
        {
            "label": "Schema",
            "value": str(
                metadata.get("schema_version")
                or project.get("schema_version")
                or "미정"
            ),
        },
        {
            "label": "Prompt",
            "value": str(
                metadata.get("prompt_version")
                or project.get("prompt_version")
                or "미정"
            ),
        },
        {
            "label": "Evaluation",
            "value": str(
                metadata.get("evaluation_version")
                or project.get("evaluation_version")
                or "미정"
            ),
        },
    ]


def statement_history(response: dict[str, Any]) -> list[dict[str, Any]]:
    history = response.get("validation", {}).get("statement_history", [])
    if history:
        return history
    statement = response.get("cypher")
    return (
        [{"kind": "final", "attempt": 1, "statement": statement}]
        if statement
        else []
    )
