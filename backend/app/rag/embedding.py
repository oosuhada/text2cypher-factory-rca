"""Deterministic local embedding for offline LlamaIndex demos and tests."""

from __future__ import annotations

import hashlib
import math
import re

from llama_index.core.embeddings import BaseEmbedding
from pydantic import Field


_TOKEN_PATTERN = re.compile(r"[0-9A-Za-z가-힣_]+")


class DeterministicHashEmbedding(BaseEmbedding):
    """Dependency-free multilingual feature hashing embedding.

    This is intentionally deterministic and offline. It keeps LAN demos and
    release tests independent from external embedding credentials while using
    the normal LlamaIndex embedding and vector-index contracts.
    """

    model_name: str = "factorygraph-hash-embedding-v1"
    dimensions: int = Field(default=768, ge=64, le=4096)

    @staticmethod
    def _tokens(text: str) -> list[str]:
        words = [
            token.lower()
            for token in _TOKEN_PATTERN.findall(text.replace("-", " "))
            if len(token) > 1
        ]
        ngrams: list[str] = []
        for word in words:
            if re.search(r"[가-힣]", word):
                ngrams.extend(
                    word[index : index + 2]
                    for index in range(max(0, len(word) - 1))
                )
            elif len(word) >= 5:
                ngrams.extend(
                    word[index : index + 3]
                    for index in range(len(word) - 2)
                )
        return words + ngrams

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in self._tokens(text):
            digest = hashlib.blake2b(
                token.encode("utf-8"),
                digest_size=16,
            ).digest()
            bucket = int.from_bytes(digest[:8], "big") % self.dimensions
            sign = 1.0 if digest[8] % 2 == 0 else -1.0
            vector[bucket] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]

    def _get_query_embedding(self, query: str) -> list[float]:
        return self._embed(query)

    async def _aget_query_embedding(self, query: str) -> list[float]:
        return self._embed(query)

    def _get_text_embedding(self, text: str) -> list[float]:
        return self._embed(text)
