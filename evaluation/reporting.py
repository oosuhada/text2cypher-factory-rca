"""Render reproducible evaluation metrics as a concise Markdown report."""

from __future__ import annotations

from typing import Any


def render_metrics_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# {report['project_id']} Text-to-Cypher 평가",
        "",
        f"- Dataset: {report['dataset']}",
        f"- Provider / model: {report['provider']} / {report['model']}",
        f"- Evaluation version: {report['evaluation_version']}",
        f"- Schema / source: {report['schema_version']} / "
        f"{report['source_version']}",
        f"- Prompt version: {report['prompt_version']}",
        f"- Evaluation fingerprint: `{report['evaluation_fingerprint']}`",
        f"- Evaluated at: {report['evaluated_at']}",
        "",
        "## Variant 비교",
        "",
        "| Variant | 의미값 정확도 | 엄격 정확도 | 실행 성공률 | "
        "미검증 실행 | 상태 Macro F1 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in report["comparison"]:
        classification = row["status_classification"]
        lines.append(
            f"| {row['variant']} | "
            f"{_percent(row['result_accuracy'])} | "
            f"{_percent(row['strict_result_accuracy'])} | "
            f"{_percent(row['execution_success_rate'])} | "
            f"{row.get('unverified_execution_count', 0)} | "
            f"{_percent(classification['macro_f1'])} |"
        )
    final = report["variants"]["self_correction"]["metrics"]
    classification = final["status_classification"]
    labels = classification["labels"]
    lines.extend(
        [
            "",
            "## Self-correction 상태 분류",
            "",
            f"- Accuracy: {_percent(classification['accuracy'])}",
            f"- Macro precision: "
            f"{_percent(classification['macro_precision'])}",
            f"- Macro recall: {_percent(classification['macro_recall'])}",
            f"- Macro F1: {_percent(classification['macro_f1'])}",
            "",
            "### 혼동행렬",
            "",
            "| Expected \\ Actual | "
            + " | ".join(labels)
            + " |",
            "|---|" + "|".join("---:" for _ in labels) + "|",
        ]
    )
    for expected in labels:
        lines.append(
            f"| {expected} | "
            + " | ".join(
                str(classification["confusion_matrix"][expected][actual])
                for actual in labels
            )
            + " |"
        )
    lines.extend(["", "## 실패 유형", ""])
    if final["failure_counts"]:
        lines.extend(
            f"- `{name}`: {count}"
            for name, count in final["failure_counts"].items()
        )
    else:
        lines.append("- 실패 없음")
    return "\n".join(lines) + "\n"


def _percent(value: float | None) -> str:
    return "-" if value is None else f"{value * 100:.1f}%"
