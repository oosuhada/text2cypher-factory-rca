"""LLM adapters used by the workflow."""

from __future__ import annotations

from collections.abc import Iterable
import json
import os
from pathlib import Path
import re
from time import perf_counter
from typing import Any, Protocol

from google import genai
from google.genai import types
from google.oauth2 import service_account
from langchain_openai import ChatOpenAI

from .examples import GoldExampleStore
from .prompts import correction_prompt, generation_prompt


class CypherModel(Protocol):
    def generate(
        self, question: str, schema: str, few_shot_examples: str
    ) -> str: ...

    def correct(
        self,
        question: str,
        schema: str,
        statement: str,
        errors: list[str],
    ) -> str: ...


def normalize_model_cypher(output: str) -> str:
    text = output.strip()
    fenced = re.search(
        r"```(?:cypher)?\s*(.*?)```",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if fenced:
        text = fenced.group(1).strip()
    starts = [
        position
        for keyword in ("MATCH", "OPTIONAL MATCH", "WITH", "UNWIND", "RETURN")
        if (position := text.upper().find(keyword)) >= 0
    ]
    if starts and min(starts) > 0:
        text = text[min(starts) :]
    return text.strip()


class OpenAICypherModel:
    def __init__(
        self,
        model: str = "gpt-4.1-mini",
        chat: Any | None = None,
    ):
        self.chat = chat or ChatOpenAI(model=model, temperature=0)

    def generate(
        self, question: str, schema: str, few_shot_examples: str
    ) -> str:
        response = self.chat.invoke(
            generation_prompt(question, schema, few_shot_examples)
        )
        return normalize_model_cypher(str(response.content))

    def correct(
        self,
        question: str,
        schema: str,
        statement: str,
        errors: list[str],
    ) -> str:
        response = self.chat.invoke(
            correction_prompt(question, schema, statement, errors)
        )
        return normalize_model_cypher(str(response.content))


DEFAULT_VERTEX_CREDENTIALS = (
    Path.home()
    / ".config"
    / "p3-cip-dmd"
    / "vertex-service-account.json"
)


def vertex_credentials_path() -> Path | None:
    configured = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    path = Path(configured).expanduser() if configured else DEFAULT_VERTEX_CREDENTIALS
    return path if path.is_file() else None


def has_vertex_credentials() -> bool:
    return vertex_credentials_path() is not None


def vertex_project_id(path: Path) -> str:
    configured = (
        os.getenv("GOOGLE_VERTEX_PROJECT")
        or os.getenv("GOOGLE_CLOUD_PROJECT")
    )
    if configured:
        return configured
    payload = json.loads(path.read_text(encoding="utf-8"))
    project_id = payload.get("project_id")
    if not project_id:
        raise RuntimeError("Vertex credential file has no project_id")
    return str(project_id)


class GeminiCypherModel:
    """Vertex AI Gemini adapter with token, latency, and cost accounting."""

    INPUT_USD_PER_MILLION = 0.15
    OUTPUT_USD_PER_MILLION = 0.60

    def __init__(
        self,
        model: str = "gemini-2.5-flash",
        project: str | None = None,
        location: str = "us-central1",
        client: Any | None = None,
    ):
        self.model = model
        self.location = location
        self.calls: list[dict[str, Any]] = []
        if client is not None:
            self.client = client
            self.project = project or "test-project"
            return
        credentials_path = vertex_credentials_path()
        if credentials_path is None:
            raise RuntimeError(
                "Vertex AI credentials are unavailable. Set "
                "GOOGLE_APPLICATION_CREDENTIALS or install the local "
                "credential file."
            )
        self.project = project or vertex_project_id(credentials_path)
        credentials = service_account.Credentials.from_service_account_file(
            str(credentials_path),
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        self.client = genai.Client(
            vertexai=True,
            project=self.project,
            location=location,
            credentials=credentials,
            http_options=types.HttpOptions(api_version="v1"),
        )

    def _invoke(self, prompt: str, purpose: str) -> str:
        started = perf_counter()
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0,
                seed=42,
                max_output_tokens=2048,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        elapsed_ms = int((perf_counter() - started) * 1000)
        usage = getattr(response, "usage_metadata", None)
        input_tokens = int(
            getattr(usage, "prompt_token_count", 0) or 0
        )
        output_tokens = int(
            getattr(usage, "candidates_token_count", 0) or 0
        )
        estimated_cost = (
            input_tokens * self.INPUT_USD_PER_MILLION
            + output_tokens * self.OUTPUT_USD_PER_MILLION
        ) / 1_000_000
        self.calls.append(
            {
                "purpose": purpose,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "elapsed_ms": elapsed_ms,
                "estimated_cost_usd": estimated_cost,
            }
        )
        text = getattr(response, "text", None)
        if not text:
            raise RuntimeError("Gemini returned no text response")
        return normalize_model_cypher(str(text))

    def generate(
        self, question: str, schema: str, few_shot_examples: str
    ) -> str:
        return self._invoke(
            generation_prompt(question, schema, few_shot_examples),
            purpose="generate",
        )

    def correct(
        self,
        question: str,
        schema: str,
        statement: str,
        errors: list[str],
    ) -> str:
        return self._invoke(
            correction_prompt(question, schema, statement, errors),
            purpose="correct",
        )

    def usage_summary(self) -> dict[str, Any]:
        return {
            "call_count": len(self.calls),
            "input_tokens": sum(
                call["input_tokens"] for call in self.calls
            ),
            "output_tokens": sum(
                call["output_tokens"] for call in self.calls
            ),
            "total_tokens": sum(
                call["total_tokens"] for call in self.calls
            ),
            "model_elapsed_ms": sum(
                call["elapsed_ms"] for call in self.calls
            ),
            "estimated_cost_usd": round(
                sum(call["estimated_cost_usd"] for call in self.calls),
                8,
            ),
            "pricing_basis": {
                "currency": "USD",
                "input_usd_per_million_tokens": self.INPUT_USD_PER_MILLION,
                "output_usd_per_million_tokens": self.OUTPUT_USD_PER_MILLION,
                "thinking_budget": 0,
                "seed": 42,
                "source": (
                    "https://cloud.google.com/vertex-ai/"
                    "generative-ai/pricing"
                ),
            },
        }


class GoldCypherModel:
    """Development model for exact Gold questions; it is not a general LLM."""

    def __init__(self, examples: GoldExampleStore):
        self.examples = examples

    def generate(
        self, question: str, schema: str, few_shot_examples: str
    ) -> str:
        del schema, few_shot_examples
        example = self.examples.exact(question)
        return example.cypher if example else ""

    def supports(self, question: str) -> bool:
        return self.examples.exact(question) is not None

    def correct(
        self,
        question: str,
        schema: str,
        statement: str,
        errors: list[str],
    ) -> str:
        del schema, statement, errors
        example = self.examples.exact(question)
        return example.cypher if example else ""


class SequenceCypherModel:
    """Deterministic test double returning a configured output sequence."""

    def __init__(self, outputs: Iterable[str]):
        self.outputs = iter(outputs)

    def _next(self) -> str:
        return normalize_model_cypher(next(self.outputs))

    def generate(
        self, question: str, schema: str, few_shot_examples: str
    ) -> str:
        del question, schema, few_shot_examples
        return self._next()

    def correct(
        self,
        question: str,
        schema: str,
        statement: str,
        errors: list[str],
    ) -> str:
        del question, schema, statement, errors
        return self._next()
