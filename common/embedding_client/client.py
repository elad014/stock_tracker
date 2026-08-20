"""LiteLLM embedding client for doc-agent RAG.

Environment variables:
- ``EMBEDDING_MODEL`` — LiteLLM embedding model id
  (default: ``gemini/gemini-embedding-001``)
- ``GEMINI_API_KEY`` — required for the default Gemini embedding model
"""

from __future__ import annotations

import logging
import os
from typing import Any

from dotenv import load_dotenv
from litellm import aembedding

from constant import (
    DEFAULT_EMBEDDING_MODEL,
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
)

load_dotenv()

logger = logging.getLogger(__name__)


class EmbeddingClient:
    """Async embedding wrapper that batches inputs and checks vector width."""

    def __init__(
        self,
        model: str | None = None,
        dimensions: int | None = None,
        batch_size: int | None = None,
    ) -> None:
        configured = (model or os.getenv("EMBEDDING_MODEL", "") or EMBEDDING_MODEL).strip()
        self.model: str = configured or DEFAULT_EMBEDDING_MODEL
        self.dimensions: int = dimensions if dimensions is not None else EMBEDDING_DIMENSIONS
        self.batch_size: int = batch_size if batch_size is not None else EMBEDDING_BATCH_SIZE
        if self.dimensions <= 0:
            raise ValueError("embedding dimensions must be a positive integer")
        if self.batch_size <= 0:
            raise ValueError("embedding batch size must be a positive integer")

    @staticmethod
    def _item_index(item: Any) -> int:
        value = getattr(item, "index", None)
        if value is None and isinstance(item, dict):
            value = item.get("index")
        return int(value) if value is not None else 0

    @staticmethod
    def _item_embedding(item: Any) -> list[float]:
        raw = getattr(item, "embedding", None)
        if raw is None and isinstance(item, dict):
            raw = item.get("embedding")
        if not isinstance(raw, list) or not raw:
            raise RuntimeError("Embedding vendor returned an unexpected vector shape")
        return [float(value) for value in raw]

    def _extract_vectors(self, response: Any, expected: int) -> list[list[float]]:
        data = getattr(response, "data", None)
        if data is None and isinstance(response, dict):
            data = response.get("data")
        if not data:
            raise RuntimeError("Embedding vendor returned no vectors")

        ordered = sorted(list(data), key=self._item_index)
        vectors = [self._item_embedding(item) for item in ordered]
        if len(vectors) != expected:
            raise RuntimeError(
                f"Embedding vendor returned {len(vectors)} vectors for {expected} inputs"
            )
        for vector in vectors:
            if len(vector) != self.dimensions:
                raise RuntimeError(
                    f"Embedding dimension mismatch: expected {self.dimensions}, "
                    f"got {len(vector)}. Check EMBEDDING_MODEL."
                )
        return vectors

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        out: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            try:
                response = await aembedding(
                    model=self.model,
                    input=batch,
                    dimensions=self.dimensions,
                )
            except Exception as exc:
                logger.exception("LiteLLM embedding failed")
                raise RuntimeError(f"Embedding vendor request failed: {exc}") from exc
            out.extend(self._extract_vectors(response, len(batch)))
        return out

    async def embed_query(self, text: str) -> list[float]:
        cleaned = text.strip()
        if not cleaned:
            raise ValueError("query must not be empty")
        vectors = await self.embed_texts([cleaned])
        return vectors[0]


embedding_client = EmbeddingClient()
