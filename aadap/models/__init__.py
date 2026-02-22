"""
AADAP — Pydantic Models
=======================
Request/response schemas and domain models for API and service layers.

Architecture layer: L6 (Presentation) / L5 (Orchestration).

These models are distinct from SQLAlchemy ORM models in aadap.db.models.
"""

from aadap.models.chat import (
    ChatMessage,
    ChatSession,
    ExtractedRequirements,
    FieldWithConfidence,
)

__all__ = [
    "ChatMessage",
    "ChatSession",
    "ExtractedRequirements",
    "FieldWithConfidence",
]
