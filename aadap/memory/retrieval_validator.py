"""
AADAP — Retrieval Validator
=============================
Post-retrieval validation gate for memory search results.

Defence-in-depth: even though VectorStore enforces invariants internally,
this validator provides a second check before results reach agent consumers.

Invariants enforced:
- INV-08: Similarity ≥ 0.85
- Deprecated entities rejected
- Staleness < 90 days
- Provenance required

Conflict resolution order (DATA_AND_STATE.md §Vector Retrieval Rules):
  recency > confidence > frequency
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from aadap.memory.vector_store import MIN_SIMILARITY, MAX_STALENESS_DAYS, SearchResult


# ── Data Classes ────────────────────────────────────────────────────────

@dataclass
class ValidatedResult:
    """A search result annotated with validation outcome."""

    result: SearchResult
    is_valid: bool
    rejection_reason: str | None = None


# ── Validator ───────────────────────────────────────────────────────────

class RetrievalValidator:
    """
    Validates and ranks search results before they reach agent consumers.

    All checks are deterministic and produce a clear rejection reason
    when a result fails validation.
    """

    def validate(self, results: list[SearchResult]) -> list[ValidatedResult]:
        """
        Validate a batch of search results.

        Returns:
            List of ``ValidatedResult`` objects.  Invalid results remain in the
            list (for audit) but are flagged with ``is_valid=False``.
            Valid results are sorted by conflict resolution order:
            recency > confidence > frequency.
        """
        validated: list[ValidatedResult] = []
        now = datetime.now(timezone.utc)
        staleness_cutoff = now - timedelta(days=MAX_STALENESS_DAYS)

        for sr in results:
            reason = self._check(sr, staleness_cutoff)
            validated.append(
                ValidatedResult(
                    result=sr,
                    is_valid=(reason is None),
                    rejection_reason=reason,
                )
            )

        # Sort valid results by conflict resolution order
        valid = [v for v in validated if v.is_valid]
        invalid = [v for v in validated if not v.is_valid]

        valid.sort(
            key=lambda v: (
                v.result.entity.updated_at,    # recency (most recent first)
                v.result.entity.confidence,     # confidence (highest first)
                v.result.entity.use_count,      # frequency (highest first)
            ),
            reverse=True,
        )

        return valid + invalid

    # ── Checks ──────────────────────────────────────────────────────────

    @staticmethod
    def _check(sr: SearchResult, staleness_cutoff: datetime) -> str | None:
        """
        Run all validation checks on a single result.

        Returns the rejection reason or ``None`` if the result passes.
        """
        # Check 1: INV-08 — similarity threshold
        if sr.similarity < MIN_SIMILARITY:
            return (
                f"INV-08 violation: similarity {sr.similarity:.4f} "
                f"< minimum {MIN_SIMILARITY}"
            )

        # Check 2: deprecated exclusion
        if sr.entity.is_deprecated:
            return "Deprecated entity must not be returned."

        # Check 3: staleness
        if sr.entity.created_at < staleness_cutoff:
            return (
                f"Stale entity: created {sr.entity.created_at.isoformat()}, "
                f"cutoff {staleness_cutoff.isoformat()}"
            )

        # Check 4: provenance
        if not sr.entity.provenance or not sr.entity.provenance.strip():
            return "Missing provenance — required by DATA_AND_STATE.md."

        return None
