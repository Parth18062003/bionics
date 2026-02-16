"""
AADAP — Embedding Service
===========================
Converts text into vector representations for Tier 2 similarity search.

Design:
- Protocol-based ``EmbeddingProvider`` for backend flexibility.
- Default ``MockEmbeddingProvider`` uses deterministic hashing (test-safe).
- Real provider (Azure OpenAI ada-002) deferred to integration phase.

Usage:
    from aadap.memory.embeddings import EmbeddingService, MockEmbeddingProvider

    service = EmbeddingService(provider=MockEmbeddingProvider())
    vector = await service.embed("some text")
"""

from __future__ import annotations

import hashlib
from typing import Protocol, runtime_checkable


# ── Constants ───────────────────────────────────────────────────────────

DEFAULT_EMBEDDING_DIMENSION = 1536  # OpenAI text-embedding-ada-002


# ── Provider Protocol ───────────────────────────────────────────────────

@runtime_checkable
class EmbeddingProvider(Protocol):
    """Backend that produces embedding vectors from text."""

    @property
    def dimension(self) -> int:
        """Dimensionality of the output vectors."""
        ...

    async def embed(self, text: str) -> list[float]:
        """Embed a single text string."""
        ...

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts in a single call."""
        ...


# ── Mock Provider (deterministic, for tests) ───────────────────────────

class MockEmbeddingProvider:
    """
    Deterministic embedding provider using SHA-256 hashing.

    Produces normalised vectors with consistent output for identical input.
    Suitable for unit tests and offline development.
    """

    def __init__(self, dimension: int = DEFAULT_EMBEDDING_DIMENSION) -> None:
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, text: str) -> list[float]:
        """Deterministic hash-based embedding."""
        return self._hash_to_vector(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed each text independently (no batching optimisation needed)."""
        return [self._hash_to_vector(t) for t in texts]

    def _hash_to_vector(self, text: str) -> list[float]:
        """
        Convert text → SHA-256 → repeating float vector of ``dimension`` length.

        The output is normalised to unit length so cosine similarity is meaningful.
        Each hash byte is mapped to [-1.0, 1.0] for well-distributed vectors.
        """
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        # Map each byte to [-1.0, 1.0] for well-distributed base values
        base_floats = [(b / 127.5) - 1.0 for b in digest]
        # Tile to required dimension
        vector: list[float] = []
        while len(vector) < self._dimension:
            vector.extend(base_floats)
        vector = vector[: self._dimension]
        # Normalise to unit length
        magnitude = sum(v * v for v in vector) ** 0.5
        if magnitude > 0:
            vector = [v / magnitude for v in vector]
        return vector


# ── Service ─────────────────────────────────────────────────────────────

class EmbeddingService:
    """
    High-level embedding interface consumed by other memory modules.

    Wraps an ``EmbeddingProvider`` and exposes ``embed`` / ``embed_batch``.
    """

    def __init__(
        self,
        provider: EmbeddingProvider | None = None,
        dimension: int = DEFAULT_EMBEDDING_DIMENSION,
    ) -> None:
        self._provider = provider or MockEmbeddingProvider(dimension=dimension)
        self._dimension = self._provider.dimension

    @property
    def dimension(self) -> int:
        """Dimensionality of output vectors."""
        return self._dimension

    async def embed(self, text: str) -> list[float]:
        """Embed a single text string.  Raises on empty input."""
        if not text or not text.strip():
            raise ValueError("Cannot embed empty or whitespace-only text.")
        return await self._provider.embed(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts.  Raises if any text is empty."""
        if not texts:
            raise ValueError("Cannot embed an empty list of texts.")
        for i, t in enumerate(texts):
            if not t or not t.strip():
                raise ValueError(f"Text at index {i} is empty or whitespace-only.")
        return await self._provider.embed_batch(texts)
