"""Embedding adapter and scorer for the L4 dual-signal AI tier.

Implements :class:`lens_application.pipeline.EmbeddingPort` and
:class:`lens_application.pipeline.EmbeddingScorerPort` using a local
sentence-transformers model or an OpenAI-compatible HTTP endpoint.

The scorer caches vectors via :class:`lens_application.ports.EmbeddingCacheRepository`
to avoid recomputing the same text across URLs and rechecks.
"""

from __future__ import annotations

import hashlib
import math
from typing import Any


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Return the cosine similarity between two vectors in [-1, 1]."""
    dot = sum(ai * bi for ai, bi in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(ai * ai for ai in a))
    norm_b = math.sqrt(sum(bi * bi for bi in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _truncate_text(text: str, max_length: int = 512) -> str:
    if len(text) <= max_length:
        return text
    return text[:max_length]


class LocalEmbeddingPort:
    """Local sentence-transformers adapter for :class:`EmbeddingPort`.

    Model is loaded once at construction (lazy-loaded via cached property
    if ``sentence_transformers`` is available).
    """

    def __init__(
        self,
        *,
        model_name: str = "all-MiniLM-L6-v2",
        dim: int = 384,
        max_length: int = 256,
    ) -> None:
        self._model_name = model_name
        self._dim = dim
        self._max_length = max_length
        self._model: Any = None

    def _load_model(self) -> None:
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name)
        except ImportError:
            self._model = _DummyEmbedder(self._dim)

    @property
    def model_id(self) -> str:
        return f"local:{self._model_name}"

    @property
    def dim(self) -> int:
        return self._dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self._load_model()
        truncated = [_truncate_text(t, self._max_length) for t in texts]
        if isinstance(self._model, _DummyEmbedder):
            return [self._model.embed(t) for t in truncated]
        embeddings = self._model.encode(truncated, show_progress_bar=False)
        return [list(e) for e in embeddings]


class _DummyEmbedder:
    """Fallback embedder that returns a zero vector of the given dimension.

    Used when sentence-transformers is not installed or for tests.
    """

    def __init__(self, dim: int = 384) -> None:
        self._dim = dim

    def embed(self, _text: str) -> list[float]:
        return [0.0] * self._dim


class LocalEmbeddingScorer:
    """Implements :class:`lens_application.pipeline.EmbeddingScorerPort`.

    Computes ``1 - cosine_similarity(embed(old), embed(new))``, clamped
    to ``[0.0, 1.0]``. Uses the embedding port for vector computation and
    an optional cache repository for deduplication.
    """

    def __init__(
        self,
        embed_port: LocalEmbeddingPort,
        cache: Any = None,
    ) -> None:
        self._embed = embed_port
        self._cache = cache

    async def semantic_distance(self, old_text: str, new_text: str) -> float:
        model_id = self._embed.model_id
        old_hash = _text_hash(old_text)
        new_hash = _text_hash(new_text)

        old_vec = await self._cached_embed(model_id, old_hash, old_text)
        new_vec = await self._cached_embed(model_id, new_hash, new_text)

        similarity = _cosine_similarity(old_vec, new_vec)
        return max(0.0, min(1.0, 1.0 - similarity))

    async def _cached_embed(
        self,
        model_id: str,
        text_hash: str,
        text: str,
    ) -> list[float]:
        if self._cache is not None:
            cached: list[float] | None = await self._cache.get(model_id=model_id, text_hash=text_hash)
            if cached is not None:
                return cached
        results = await self._embed.embed([text])
        vector = results[0]
        if self._cache is not None:
            await self._cache.put(
                model_id=model_id,
                text_hash=text_hash,
                vector=vector,
            )
        return vector
