"""
AADAP — Retrieval Validator Tests
====================================
Tests for post-retrieval validation: INV-08, deprecation, staleness,
provenance, and conflict resolution ordering.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from aadap.memory.retrieval_validator import RetrievalValidator, ValidatedResult
from aadap.memory.vector_store import MAX_STALENESS_DAYS, MIN_SIMILARITY, MemoryEntity, SearchResult


# ── Helpers ─────────────────────────────────────────────────────────────

def _make_result(
    similarity: float = 0.95,
    is_deprecated: bool = False,
    provenance: str = "test-system",
    created_at: datetime | None = None,
    confidence: float = 0.9,
    use_count: int = 5,
    updated_at: datetime | None = None,
) -> SearchResult:
    """Create a test SearchResult."""
    now = datetime.now(timezone.utc)
    entity = MemoryEntity(
        content="test",
        embedding=[1.0, 0.0],
        entity_type="test",
        provenance=provenance,
        is_deprecated=is_deprecated,
        created_at=created_at or now,
        updated_at=updated_at or now,
        confidence=confidence,
        use_count=use_count,
    )
    return SearchResult(entity=entity, similarity=similarity)


# ── Low Similarity Rejection ───────────────────────────────────────────

def test_low_similarity_rejected():
    """Results below MIN_SIMILARITY (0.85) are rejected."""
    validator = RetrievalValidator()
    result = _make_result(similarity=0.80)
    validated = validator.validate([result])
    assert len(validated) == 1
    assert validated[0].is_valid is False
    assert "INV-08" in validated[0].rejection_reason


def test_exact_threshold_accepted():
    """Results at exactly MIN_SIMILARITY are accepted."""
    validator = RetrievalValidator()
    result = _make_result(similarity=MIN_SIMILARITY)
    validated = validator.validate([result])
    assert validated[0].is_valid is True


# ── Deprecated Rejection ───────────────────────────────────────────────

def test_deprecated_rejected():
    """Deprecated entities are rejected."""
    validator = RetrievalValidator()
    result = _make_result(is_deprecated=True)
    validated = validator.validate([result])
    assert validated[0].is_valid is False
    assert "Deprecated" in validated[0].rejection_reason


# ── Staleness Rejection ────────────────────────────────────────────────

def test_stale_rejected():
    """Entities older than 90 days are rejected."""
    validator = RetrievalValidator()
    old = datetime.now(timezone.utc) - timedelta(days=MAX_STALENESS_DAYS + 1)
    result = _make_result(created_at=old)
    validated = validator.validate([result])
    assert validated[0].is_valid is False
    assert "Stale" in validated[0].rejection_reason


def test_fresh_accepted():
    """Entities within 90 days pass staleness check."""
    validator = RetrievalValidator()
    recent = datetime.now(timezone.utc) - timedelta(days=10)
    result = _make_result(created_at=recent)
    validated = validator.validate([result])
    assert validated[0].is_valid is True


# ── Provenance Enforcement ──────────────────────────────────────────────

def test_missing_provenance_rejected():
    """Results without provenance are rejected."""
    validator = RetrievalValidator()
    result = _make_result(provenance="")
    validated = validator.validate([result])
    assert validated[0].is_valid is False
    assert "provenance" in validated[0].rejection_reason.lower()


def test_whitespace_provenance_rejected():
    """Results with whitespace-only provenance are rejected."""
    validator = RetrievalValidator()
    result = _make_result(provenance="   ")
    validated = validator.validate([result])
    assert validated[0].is_valid is False


# ── Conflict Resolution Ordering ───────────────────────────────────────

def test_conflict_resolution_recency_first():
    """Valid results are sorted by recency > confidence > frequency."""
    validator = RetrievalValidator()
    now = datetime.now(timezone.utc)

    # Older but higher confidence
    older = _make_result(
        updated_at=now - timedelta(hours=2),
        confidence=0.99,
        use_count=100,
    )
    # More recent but lower confidence
    newer = _make_result(
        updated_at=now,
        confidence=0.85,
        use_count=1,
    )

    validated = validator.validate([older, newer])
    valid_items = [v for v in validated if v.is_valid]
    assert len(valid_items) == 2
    # Newer should come first (recency wins)
    assert valid_items[0].result.entity.updated_at >= valid_items[1].result.entity.updated_at


# ── Mixed Batch ─────────────────────────────────────────────────────────

def test_mixed_valid_and_invalid():
    """Validate correctly partitions a mixed batch."""
    validator = RetrievalValidator()
    good = _make_result(similarity=0.95)
    bad_sim = _make_result(similarity=0.50)
    bad_depr = _make_result(is_deprecated=True)

    validated = validator.validate([good, bad_sim, bad_depr])
    valid_count = sum(1 for v in validated if v.is_valid)
    invalid_count = sum(1 for v in validated if not v.is_valid)
    assert valid_count == 1
    assert invalid_count == 2


def test_empty_input_returns_empty():
    """Validating an empty list returns an empty list."""
    validator = RetrievalValidator()
    assert validator.validate([]) == []
