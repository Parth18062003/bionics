"""
AADAP — Embedding Service Tests
=================================
Tests for the embedding service and mock provider.
"""

from __future__ import annotations

import pytest

from aadap.memory.embeddings import (
    DEFAULT_EMBEDDING_DIMENSION,
    EmbeddingService,
    MockEmbeddingProvider,
)


# ── MockEmbeddingProvider ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mock_provider_returns_correct_dimension():
    """embed() returns a vector of the configured dimension."""
    provider = MockEmbeddingProvider(dimension=128)
    vector = await provider.embed("hello world")
    assert len(vector) == 128


@pytest.mark.asyncio
async def test_mock_provider_default_dimension():
    """Default dimension matches OpenAI ada-002 (1536)."""
    provider = MockEmbeddingProvider()
    vector = await provider.embed("test")
    assert len(vector) == DEFAULT_EMBEDDING_DIMENSION


@pytest.mark.asyncio
async def test_mock_provider_deterministic():
    """Same input always produces the same output."""
    provider = MockEmbeddingProvider()
    v1 = await provider.embed("deterministic test")
    v2 = await provider.embed("deterministic test")
    assert v1 == v2


@pytest.mark.asyncio
async def test_mock_provider_different_inputs():
    """Different inputs produce different vectors."""
    provider = MockEmbeddingProvider(dimension=128)
    v1 = await provider.embed("input A")
    v2 = await provider.embed("input B")
    # Compare rounded values to handle -0.0 vs 0.0
    r1 = [round(x, 10) for x in v1]
    r2 = [round(x, 10) for x in v2]
    assert r1 != r2


@pytest.mark.asyncio
async def test_mock_provider_normalised():
    """Output vectors are normalised to approximately unit length."""
    provider = MockEmbeddingProvider(dimension=128)
    vector = await provider.embed("normalisation test")
    magnitude = sum(v * v for v in vector) ** 0.5
    assert abs(magnitude - 1.0) < 1e-6


@pytest.mark.asyncio
async def test_mock_provider_embed_batch():
    """embed_batch returns one vector per input text."""
    provider = MockEmbeddingProvider(dimension=64)
    texts = ["alpha", "beta", "gamma"]
    results = await provider.embed_batch(texts)
    assert len(results) == 3
    for vec in results:
        assert len(vec) == 64


# ── EmbeddingService ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_service_embed():
    """Service delegates to provider and returns correct vector."""
    service = EmbeddingService(dimension=64)
    vector = await service.embed("test input")
    assert len(vector) == 64


@pytest.mark.asyncio
async def test_service_embed_empty_raises():
    """embed() raises ValueError on empty input."""
    service = EmbeddingService()
    with pytest.raises(ValueError, match="empty"):
        await service.embed("")


@pytest.mark.asyncio
async def test_service_embed_whitespace_raises():
    """embed() raises ValueError on whitespace-only input."""
    service = EmbeddingService()
    with pytest.raises(ValueError, match="whitespace"):
        await service.embed("   ")


@pytest.mark.asyncio
async def test_service_embed_batch():
    """embed_batch returns correct count."""
    service = EmbeddingService(dimension=64)
    results = await service.embed_batch(["a", "b"])
    assert len(results) == 2


@pytest.mark.asyncio
async def test_service_embed_batch_empty_list_raises():
    """embed_batch raises on empty list."""
    service = EmbeddingService()
    with pytest.raises(ValueError, match="empty list"):
        await service.embed_batch([])


@pytest.mark.asyncio
async def test_service_embed_batch_empty_item_raises():
    """embed_batch raises if any text is empty."""
    service = EmbeddingService()
    with pytest.raises(ValueError, match="index 1"):
        await service.embed_batch(["valid", "", "also valid"])


@pytest.mark.asyncio
async def test_service_dimension_property():
    """dimension property reflects provider dimension."""
    service = EmbeddingService(dimension=256)
    assert service.dimension == 256
