"""
AADAP — Embedding Service
===========================
Converts text into vector representations for Tier 2 similarity search.

Design:
- Protocol-based ``EmbeddingProvider`` for backend flexibility.
- Default ``MockEmbeddingProvider`` uses deterministic hashing (test-safe).
- ``AzureOpenAIEmbeddingProvider`` for real Azure OpenAI embeddings.

Usage:
    from aadap.memory.embeddings import EmbeddingService, MockEmbeddingProvider

    service = EmbeddingService(provider=MockEmbeddingProvider())
    vector = await service.embed("some text")

    # Real provider:
    from aadap.memory.embeddings import AzureOpenAIEmbeddingProvider
    provider = AzureOpenAIEmbeddingProvider.from_settings()
    service = EmbeddingService(provider=provider)
"""

from __future__ import annotations

import hashlib
from typing import Protocol, runtime_checkable

from aadap.core.config import get_settings
from aadap.core.logging import get_logger

logger = get_logger(__name__)


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


# ── Azure OpenAI Embedding Provider ───────────────────────────────────────


class AzureOpenAIEmbeddingProvider:
    """
    Real Azure OpenAI embedding provider.

    Uses Azure OpenAI embedding models (e.g., text-embedding-ada-002,
    text-embedding-3-small, text-embedding-3-large).

    Requires the following environment variables:
        - AADAP_AZURE_OPENAI_API_KEY
        - AADAP_AZURE_OPENAI_ENDPOINT
        - AADAP_AZURE_OPENAI_EMBEDDING_DEPLOYMENT
    """

    EMBEDDING_DIMENSIONS = {
        "text-embedding-ada-002": 1536,
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
    }

    def __init__(
        self,
        api_key: str,
        endpoint: str,
        api_version: str,
        deployment_name: str,
        dimension: int | None = None,
    ) -> None:
        self._api_key = api_key
        self._endpoint = endpoint
        self._api_version = api_version
        self._deployment_name = deployment_name
        self._dimension = dimension or self._get_default_dimension(deployment_name)
        self._client = None

    @classmethod
    def from_settings(cls) -> "AzureOpenAIEmbeddingProvider":
        """Create an AzureOpenAIEmbeddingProvider from application settings."""
        settings = get_settings()
        if not settings.azure_openai_api_key:
            raise ValueError(
                "AADAP_AZURE_OPENAI_API_KEY is required for AzureOpenAIEmbeddingProvider"
            )
        if not settings.azure_openai_endpoint:
            raise ValueError(
                "AADAP_AZURE_OPENAI_ENDPOINT is required for AzureOpenAIEmbeddingProvider"
            )
        if not settings.azure_openai_embedding_deployment:
            raise ValueError(
                "AADAP_AZURE_OPENAI_EMBEDDING_DEPLOYMENT is required for AzureOpenAIEmbeddingProvider"
            )
        return cls(
            api_key=settings.azure_openai_api_key.get_secret_value(),
            endpoint=settings.azure_openai_endpoint,
            api_version=settings.azure_openai_api_version,
            deployment_name=settings.azure_openai_embedding_deployment,
        )

    def _get_default_dimension(self, deployment_name: str) -> int:
        """Get the default dimension for a known embedding model."""
        for model_name, dim in self.EMBEDDING_DIMENSIONS.items():
            if model_name in deployment_name.lower():
                return dim
        return DEFAULT_EMBEDDING_DIMENSION

    def _get_client(self):
        """Lazily initialize the OpenAI client."""
        if self._client is None:
            from openai import AsyncAzureOpenAI
            self._client = AsyncAzureOpenAI(
                api_key=self._api_key,
                azure_endpoint=self._endpoint,
                api_version=self._api_version,
            )
        return self._client

    @property
    def dimension(self) -> int:
        """Dimensionality of output vectors."""
        return self._dimension

    async def embed(self, text: str) -> list[float]:
        """Embed a single text string using Azure OpenAI."""
        client = self._get_client()

        logger.debug(
            "embedding.embed.start",
            deployment=self._deployment_name,
            text_length=len(text),
        )

        try:
            response = await client.embeddings.create(
                model=self._deployment_name,
                input=text,
            )

            embedding = response.data[0].embedding

            logger.debug(
                "embedding.embed.success",
                deployment=self._deployment_name,
                embedding_dim=len(embedding),
            )

            return list(embedding)
        except Exception as exc:
            logger.error(
                "embedding.embed.error",
                deployment=self._deployment_name,
                error=str(exc),
            )
            raise

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts in a single API call."""
        client = self._get_client()

        logger.debug(
            "embedding.embed_batch.start",
            deployment=self._deployment_name,
            batch_size=len(texts),
        )

        try:
            response = await client.embeddings.create(
                model=self._deployment_name,
                input=texts,
            )

            results = [list(d.embedding) for d in response.data]

            logger.debug(
                "embedding.embed_batch.success",
                deployment=self._deployment_name,
                batch_size=len(results),
            )

            return results
        except Exception as exc:
            logger.error(
                "embedding.embed_batch.error",
                deployment=self._deployment_name,
                batch_size=len(texts),
                error=str(exc),
            )
            raise
