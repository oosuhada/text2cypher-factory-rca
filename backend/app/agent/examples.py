"""Load and select human-reviewed Text-to-Cypher examples."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

import yaml


@dataclass(frozen=True)
class CypherExample:
    question_id: str
    question: str
    cypher: str
    category: str


def _tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[0-9A-Za-z가-힣_]+", text)
        if len(token) > 1
    }


class GoldExampleStore:
    """Reloads the YAML on every selection so edits need no app restart."""

    def __init__(self, path: Path):
        self.path = path

    def load(self) -> list[CypherExample]:
        document = yaml.safe_load(self.path.read_text(encoding="utf-8"))
        examples = []
        for item in document.get("questions", []):
            cypher = item.get("gold_cypher")
            if not cypher:
                continue
            examples.append(
                CypherExample(
                    question_id=str(item["id"]),
                    question=str(item["question"]),
                    cypher=str(cypher).strip(),
                    category=str(item.get("category", "")),
                )
            )
        return examples

    def exact(self, question: str) -> CypherExample | None:
        normalized = question.strip()
        return next(
            (
                example
                for example in self.load()
                if example.question.strip() == normalized
            ),
            None,
        )

    def select(self, question: str, k: int = 6) -> list[CypherExample]:
        question_tokens = _tokens(question)
        examples = self.load()
        ranked = sorted(
            examples,
            key=lambda example: (
                len(question_tokens & _tokens(example.question)),
                example.question_id,
            ),
            reverse=True,
        )
        return ranked[: max(1, min(k, len(ranked)))]

    def format_for_prompt(self, question: str, k: int = 6) -> str:
        # This uses direct string joining, not str.format, so Cypher map braces
        # remain intact without template escaping.
        return "\n\n".join(
            f"Question: {example.question}\nCypher:\n{example.cypher}"
            for example in self.select(question, k=k)
        )
