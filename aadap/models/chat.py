"""
AADAP — Chat Models
===================
Pydantic models for chat functionality with requirement extraction.

Architecture layer: L6 (Presentation) / L5 (Orchestration).

These models are used for in-memory session storage (session scope only),
not persisted to database. Chat history lives in memory during the active
conversation session.

Usage:
    from aadap.models.chat import ChatSession, ChatMessage, ExtractedRequirements
    
    session = ChatSession(session_id=str(uuid.uuid4()))
    session.messages.append(ChatMessage(role="user", content="Hello"))
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, Literal, Optional

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    """Return current UTC datetime with timezone."""
    return datetime.now(timezone.utc)


# ── Field with Confidence Score ───────────────────────────────────────────


class FieldWithConfidence(BaseModel):
    """
    A field value with an associated confidence score.
    
    Used to represent partially extracted requirements where the LLM
    may be uncertain about certain values.
    """
    
    value: str | list[str] | None = Field(
        default=None,
        description="The extracted field value",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence score (0.0-1.0)",
    )
    source: str | None = Field(
        default=None,
        description="Source of the value: 'explicit' | 'inferred' | 'default'",
    )


# ── Extracted Requirements ────────────────────────────────────────────────


class ExtractedRequirements(BaseModel):
    """
    Structured task requirements extracted from conversation.
    
    Each field has an associated confidence score allowing partial
    extraction display. The overall_confidence represents how complete
    and certain the extraction is.
    """
    
    task_name: Optional[FieldWithConfidence] = Field(
        default=None,
        description="Task name/title",
    )
    description: Optional[FieldWithConfidence] = Field(
        default=None,
        description="Detailed task description",
    )
    target_table: Optional[FieldWithConfidence] = Field(
        default=None,
        description="Target table or dataset",
    )
    objective: Optional[FieldWithConfidence] = Field(
        default=None,
        description="What the task should accomplish",
    )
    success_criteria: Optional[FieldWithConfidence] = Field(
        default=None,
        description="List of success criteria",
    )
    constraints: Optional[FieldWithConfidence] = Field(
        default=None,
        description="List of constraints or limitations",
    )
    
    # Metadata about extraction
    overall_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall confidence in the extraction (0.0-1.0)",
    )
    is_complete: bool = Field(
        default=False,
        description="Whether all required fields are filled with high confidence",
    )
    extraction_notes: list[str] = Field(
        default_factory=list,
        description="Notes about extraction uncertainty or assumptions",
    )
    
    def calculate_completeness(self) -> tuple[int, int]:
        """
        Calculate how many required fields are filled with sufficient confidence.
        
        Returns (filled_count, total_required) for progress display.
        """
        required_fields = [
            self.task_name,
            self.description,
            self.target_table,
            self.objective,
        ]
        
        filled = sum(
            1 for field in required_fields
            if field is not None 
            and field.value is not None 
            and field.confidence >= 0.7
        )
        
        return filled, len(required_fields)
    
    def update_is_complete(self, threshold: float = 0.7) -> bool:
        """
        Update is_complete based on field confidence.
        
        A requirement is complete when all required fields have values
        with confidence >= threshold.
        """
        filled, total = self.calculate_completeness()
        self.is_complete = filled == total
        
        # Also update overall confidence as weighted average
        all_fields = [
            self.task_name,
            self.description,
            self.target_table,
            self.objective,
            self.success_criteria,
            self.constraints,
        ]
        
        confidences = [
            f.confidence for f in all_fields 
            if f is not None
        ]
        
        if confidences:
            self.overall_confidence = sum(confidences) / len(confidences)
        
        return self.is_complete
    
    def to_task_metadata(self) -> dict[str, Any]:
        """
        Convert to a flat dictionary suitable for task metadata.
        
        Only includes fields with values.
        """
        result: dict[str, Any] = {}
        
        if self.task_name and self.task_name.value:
            result["task_name"] = self.task_name.value
        if self.description and self.description.value:
            result["description"] = self.description.value
        if self.target_table and self.target_table.value:
            result["target_table"] = self.target_table.value
        if self.objective and self.objective.value:
            result["objective"] = self.objective.value
        if self.success_criteria and self.success_criteria.value:
            result["success_criteria"] = self.success_criteria.value
        if self.constraints and self.constraints.value:
            result["constraints"] = self.constraints.value
        result["extraction_confidence"] = self.overall_confidence
        
        return result


# ── Chat Message ──────────────────────────────────────────────────────────


class ChatMessage(BaseModel):
    """
    A single message in a chat conversation.
    
    Follows the standard chat format with role, content, and timestamp.
    Assistant messages may include extracted requirements with confidence.
    """
    
    role: Literal["user", "assistant", "system"] = Field(
        ...,
        description="Who sent the message",
    )
    content: str = Field(
        ...,
        description="The message content",
    )
    timestamp: datetime = Field(
        default_factory=_utcnow,
        description="When the message was sent",
    )
    extracted_requirements: Optional[ExtractedRequirements] = Field(
        default=None,
        description="Requirements extracted by assistant (for assistant messages)",
    )
    
    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat(),
        },
    }


# ── Chat Session ──────────────────────────────────────────────────────────


class ChatSession(BaseModel):
    """
    A chat session with message history and extracted requirements.
    
    Sessions are stored in-memory (not database) for the duration of
    the conversation. Session ID is used as the key in the session store.
    """
    
    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique session identifier (UUID)",
    )
    messages: list[ChatMessage] = Field(
        default_factory=list,
        description="Conversation history",
    )
    created_at: datetime = Field(
        default_factory=_utcnow,
        description="When the session was created",
    )
    updated_at: datetime = Field(
        default_factory=_utcnow,
        description="When the session was last updated",
    )
    current_requirements: Optional[ExtractedRequirements] = Field(
        default=None,
        description="Current extracted requirements (updated during conversation)",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional session metadata",
    )
    
    def add_message(
        self,
        role: Literal["user", "assistant", "system"],
        content: str,
        extracted_requirements: Optional[ExtractedRequirements] = None,
    ) -> ChatMessage:
        """
        Add a message to the session and update timestamp.
        
        Returns the created message.
        """
        message = ChatMessage(
            role=role,
            content=content,
            timestamp=_utcnow(),
            extracted_requirements=extracted_requirements,
        )
        self.messages.append(message)
        self.updated_at = _utcnow()
        
        # Update current requirements if assistant provided new ones
        if role == "assistant" and extracted_requirements:
            self.current_requirements = extracted_requirements
        
        return message
    
    def to_api_response(self) -> dict[str, Any]:
        """
        Convert to API response format.
        
        Includes session metadata, messages, and current requirements.
        """
        return {
            "session_id": self.session_id,
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                    "extracted_requirements": (
                        msg.extracted_requirements.model_dump()
                        if msg.extracted_requirements else None
                    ),
                }
                for msg in self.messages
            ],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "current_requirements": (
                self.current_requirements.model_dump()
                if self.current_requirements else None
            ),
            "completeness": (
                self.current_requirements.calculate_completeness()
                if self.current_requirements else (0, 4)
            ),
        }
    
    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat(),
        },
    }
