"""
AADAP — Chat Service
====================
Service for conversational task creation with LLM-powered requirement extraction.

Architecture layer: L5 (Orchestration).

This service provides:
- In-memory session management (session scope, not persistent)
- Streaming LLM responses via Azure OpenAI
- Requirement extraction from natural language conversation

Usage:
    from aadap.services.chat_service import ChatService
    
    service = ChatService()
    session = await service.create_session()
    
    async for chunk in service.stream_response(session.session_id, "I need a pipeline"):
        # SSE-formatted chunk
        yield chunk
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, AsyncGenerator

from fastapi import HTTPException
from openai import AsyncAzureOpenAI

from aadap.core.config import get_settings
from aadap.core.logging import get_logger
from aadap.models.chat import (
    ChatMessage,
    ChatSession,
    ExtractedRequirements,
    FieldWithConfidence,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


def _utcnow() -> datetime:
    """Return current UTC datetime with timezone."""
    return datetime.now(timezone.utc)


# ── System Prompt for Requirement Extraction ─────────────────────────────────

REQUIREMENT_SYSTEM_PROMPT = """You are a conversational AI assistant helping users clarify their data engineering requirements through natural conversation.

Your goal is to extract structured task requirements step-by-step. Ask clarifying questions when information is ambiguous or incomplete.

## Fields to Extract

- task_name: The task title (short, descriptive)
- description: Detailed description of what needs to be done
- target_table: The target table or dataset name
- objective: What the task should accomplish
- success_criteria: List of success conditions (optional)
- constraints: List of constraints or limitations (optional)

## Response Format

Always respond with a JSON object containing:
1. "message": Your conversational response to the user
2. "requirements": An object with the extracted fields

Each requirement field should have:
- "value": The extracted value (string or list of strings)
- "confidence": Your confidence score (0.0-1.0)

Example:
```json
{
  "message": "I understand you want to create a daily sales pipeline. What table should this target?",
  "requirements": {
    "task_name": {"value": "Daily Sales Pipeline", "confidence": 0.8},
    "description": {"value": "A pipeline that ingests sales data daily", "confidence": 0.7},
    "target_table": {"value": null, "confidence": 0.0},
    "objective": {"value": "Load data from source to bronze table daily", "confidence": 0.6},
    "success_criteria": {"value": null, "confidence": 0.0},
    "constraints": {"value": null, "confidence": 0.0},
    "overall_confidence": 0.52,
    "is_complete": false
  }
}
```

## Guidelines

- Be helpful and natural in conversation
- Ask ONE question at a time to clarify understanding
- Don't hallucinate values - keep null if uncertain
- Mark confidence as 0.0-0.3 for uncertain, 0.4-0.6 for inferred, 0.7-1.0 for explicit
- Set is_complete=true only when task_name, description, target_table, and objective all have confidence >= 0.7
"""


# ── Chat Service ─────────────────────────────────────────────────────────────


class ChatService:
    """
    Service for chat-based task creation.
    
    Manages in-memory sessions and streams LLM responses with requirement extraction.
    """
    
    def __init__(self) -> None:
        """Initialize the chat service."""
        self._sessions: dict[str, ChatSession] = {}
        self._llm_client: AsyncAzureOpenAI | None = None
        logger.info("chat_service.initialized")
    
    def _get_llm_client(self) -> AsyncAzureOpenAI:
        """Get or create Azure OpenAI client."""
        if self._llm_client is None:
            settings = get_settings()
            if not settings.azure_openai_api_key or not settings.azure_openai_endpoint:
                raise RuntimeError(
                    "Azure OpenAI configuration missing. Set AADAP_AZURE_OPENAI_API_KEY and "
                    "AADAP_AZURE_OPENAI_ENDPOINT environment variables."
                )
            self._llm_client = AsyncAzureOpenAI(
                api_key=settings.azure_openai_api_key.get_secret_value(),
                azure_endpoint=settings.azure_openai_endpoint,
                api_version=settings.azure_openai_api_version,
            )
        return self._llm_client
    
    # ── Session Management ──────────────────────────────────────────────────
    
    async def create_session(self) -> ChatSession:
        """
        Create a new chat session.
        
        Returns:
            ChatSession with generated session_id
        """
        session_id = str(uuid.uuid4())
        session = ChatSession(
            session_id=session_id,
            messages=[],
            created_at=_utcnow(),
            updated_at=_utcnow(),
            current_requirements=None,
        )
        self._sessions[session_id] = session
        logger.info("chat_service.session_created", session_id=session_id)
        return session
    
    async def get_session(self, session_id: str) -> ChatSession:
        """
        Get a chat session by ID.
        
        Args:
            session_id: The session ID to retrieve
        
        Returns:
            ChatSession object
            
        Raises:
            HTTPException: 404 if session not found
        """
        session = self._sessions.get(session_id)
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Chat session {session_id} not found",
            )
        return session
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session from memory."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info("chat_service.session_deleted", session_id=session_id)
            return True
        return False
    
    # ── Streaming Chat ──────────────────────────────────────────────────────
    
    async def stream_response(
        self,
        session_id: str,
        user_message: str,
    ) -> AsyncGenerator[str, None]:
        """
        Stream a chat response from Azure OpenAI with requirement extraction.
        
        Args:
            session_id: Chat session ID
            user_message: User's message content
        
        Yields:
            SSE-formatted strings: "data: {...}\\n\\n"
        """
        session = await self.get_session(session_id)
        
        # Add user message to session
        session.add_message(role="user", content=user_message)
        
        # Build conversation history for LLM
        messages = [{"role": "system", "content": REQUIREMENT_SYSTEM_PROMPT}]
        for msg in session.messages:
            messages.append({"role": msg.role, "content": msg.content})
        
        client = self._get_llm_client()
        settings = get_settings()
        
        logger.debug(
            "chat_service.streaming_start",
            session_id=session_id,
            message_count=len(messages),
        )
        
        full_response = ""
        try:
            stream = await client.chat.completions.create(
                model=settings.azure_openai_deployment_name or "gpt-4o",
                messages=messages,
                max_tokens=4096,
                stream=True,
            )
            
            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    content = delta.content or ""
                    if content:
                        full_response += content
                        # Yield content chunk as SSE
                        yield self._format_sse_event("content", {"content": content})
            
            # Parse requirements from full response
            requirements = self._extract_requirements_from_response(full_response)
            
            if requirements:
                # Update session with extracted requirements
                session.current_requirements = requirements
                session.updated_at = _utcnow()
                
                # Add assistant message with requirements
                session.add_message(
                    role="assistant",
                    content=full_response,
                    extracted_requirements=requirements,
                )
                
                # Yield final requirements event
                yield self._format_sse_event(
                    "requirements",
                    {"requirements": requirements.model_dump()},
                )
                
                logger.info(
                    "chat_service.requirements_extracted",
                    session_id=session_id,
                    is_complete=requirements.is_complete,
                    confidence=requirements.overall_confidence,
                )
            else:
                # No requirements extracted, just add message
                session.add_message(role="assistant", content=full_response)
            
            # Yield done event
            yield self._format_sse_event("done", {"session_id": session_id})
            
        except Exception as e:
            logger.error(
                "chat_service.stream_error",
                session_id=session_id,
                error=str(e),
            )
            yield self._format_sse_event("error", {"message": str(e)})
    
    def _format_sse_event(self, event_type: str, data: dict[str, Any]) -> str:
        """Format a Server-Sent Event."""
        event_data = {"type": event_type, **data}
        return f"data: {json.dumps(event_data)}\n\n"
    
    def _extract_requirements_from_response(
        self, response_text: str
    ) -> ExtractedRequirements | None:
        """
        Parse requirements from LLM response text.
        
        Uses regex to extract JSON from response.
        """
        import re
        
        # Try to find JSON block in response
        json_match = re.search(r"\{[\s\S]*\}", response_text)
        if not json_match:
            logger.warning(
                "chat_service.no_json_in_response",
                response_preview=response_text[:200],
            )
            return None
        
        try:
            data = json.loads(json_match.group(0))
            
            if "requirements" not in data:
                return None
            
            req_data = data["requirements"]
            
            # Build ExtractedRequirements from parsed data
            def make_field(value: Any) -> FieldWithConfidence | None:
                if value is None:
                    return None
                if isinstance(value, dict):
                    return FieldWithConfidence(
                        value=value.get("value"),
                        confidence=value.get("confidence", 0.5),
                    )
                return FieldWithConfidence(value=value, confidence=0.5)
            
            requirements = ExtractedRequirements(
                task_name=make_field(req_data.get("task_name")),
                description=make_field(req_data.get("description")),
                target_table=make_field(req_data.get("target_table")),
                objective=make_field(req_data.get("objective")),
                success_criteria=make_field(req_data.get("success_criteria")),
                constraints=make_field(req_data.get("constraints")),
                overall_confidence=req_data.get("overall_confidence", 0.0),
                is_complete=req_data.get("is_complete", False),
            )
            
            # Recalculate completeness based on our logic
            requirements.update_is_complete()
            
            return requirements
            
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(
                "chat_service.json_parse_failed",
                error=str(e),
                response_preview=response_text[:200],
            )
            return None
    
    # ── Requirements Management ─────────────────────────────────────────────
    
    async def update_requirements(
        self,
        session_id: str,
        requirements_update: dict[str, Any],
    ) -> ChatSession:
        """
        Update requirements directly (from frontend panel edit).
        
        Args:
            session_id: Session ID
            requirements_update: Partial requirements update
        
        Returns:
            Updated ChatSession
        """
        session = await self.get_session(session_id)
        
        # Get or create requirements
        if session.current_requirements is None:
            session.current_requirements = ExtractedRequirements()
        
        # Update fields from the update dict
        for field_name, value in requirements_update.items():
            if hasattr(session.current_requirements, field_name):
                if isinstance(value, dict):
                    # It's a FieldWithConfidence-like dict
                    current_field = getattr(session.current_requirements, field_name)
                    if current_field is None:
                        current_field = FieldWithConfidence()
                    if "value" in value:
                        current_field.value = value["value"]
                    if "confidence" in value:
                        current_field.confidence = value["confidence"]
                    setattr(session.current_requirements, field_name, current_field)
                else:
                    # Direct value - set with high confidence (user confirmed)
                    setattr(
                        session.current_requirements,
                        field_name,
                        FieldWithConfidence(value=value, confidence=1.0, source="user_edit"),
                    )
        
        # Recalculate completeness
        session.current_requirements.update_is_complete()
        session.updated_at = _utcnow()
        
        logger.info(
            "chat_service.requirements_updated",
            session_id=session_id,
            is_complete=session.current_requirements.is_complete,
        )
        
        return session
    
    async def create_task_from_requirements(
        self,
        session_id: str,
        db_session: AsyncSession,
    ) -> dict[str, Any]:
        """
        Create a Task from extracted requirements.
        
        Validates that requirements are complete before creating.
        
        Args:
            session_id: Session ID
            db_session: Database session for task creation
        
        Returns:
            Dict with task_id and redirect_url
        
        Raises:
            HTTPException: 400 if requirements not complete
        """
        session = await self.get_session(session_id)
        requirements = session.current_requirements
        
        if not requirements or not requirements.is_complete:
            filled, total = requirements.calculate_completeness() if requirements else (0, 4)
            raise HTTPException(
                status_code=400,
                detail=f"Requirements not complete. {filled}/{total} required fields filled.",
            )
        
        # Extract values for task creation
        task_name = requirements.task_name.value if requirements.task_name else "Untitled Task"
        description = requirements.description.value if requirements.description else None
        metadata = requirements.to_task_metadata()
        
        # Import here to avoid circular dependency
        from aadap.orchestrator.graph import create_task
        
        task_id = await create_task(
            title=str(task_name),
            description=str(description) if description else None,
            priority=0,
            environment="SANDBOX",
            metadata=metadata,
        )
        
        logger.info(
            "chat_service.task_created",
            session_id=session_id,
            task_id=str(task_id),
        )
        
        # Clean up session
        await self.delete_session(session_id)
        
        return {
            "task_id": str(task_id),
            "redirect_url": f"/tasks/{task_id}",
        }
    
    # ── Cleanup ─────────────────────────────────────────────────────────────
    
    async def close(self) -> None:
        """Clean up resources."""
        if self._llm_client:
            await self._llm_client.close()
            self._llm_client = None
        self._sessions.clear()
        logger.info("chat_service.shutdown_complete")


# ── Singleton Instance ───────────────────────────────────────────────────────

# Global service instance
_chat_service: ChatService | None = None


def get_chat_service() -> ChatService:
    """Get the global chat service instance."""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service
