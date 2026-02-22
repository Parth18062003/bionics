"""
AADAP — Chat API Routes
=========================
REST endpoints for chat-based task creation.

Architecture layer: L6 (Presentation).
Phase 2 contract: Natural language task creation with streaming responses.

Endpoints:
    POST   /api/chat/sessions                     — Create new chat session
    GET    /api/chat/sessions/{session_id}        — Get session with history
    POST   /api/chat/sessions/{session_id}/messages — Send message, stream response
    PATCH  /api/chat/sessions/{session_id}/requirements — Update requirements directly
    POST   /api/chat/sessions/{session_id}/create-task — Create task from requirements
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from aadap.api.deps import get_session
from aadap.core.logging import get_logger
from aadap.services.chat_service import get_chat_service

logger = get_logger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


# ── Request / Response Schemas ──────────────────────────────────────────────


class SessionCreateResponse(BaseModel):
    """Response for session creation."""
    session_id: str
    created_at: str


class MessageRequest(BaseModel):
    """Request body for sending a message."""
    message: str = Field(..., min_length=1, max_length=10000)


class RequirementsUpdateRequest(BaseModel):
    """Request body for updating requirements directly."""
    task_name: dict[str, Any] | None = None
    description: dict[str, Any] | None = None
    target_table: dict[str, Any] | None = None
    objective: dict[str, Any] | None = None
    success_criteria: dict[str, Any] | None = None
    constraints: dict[str, Any] | None = None


class TaskCreateResponse(BaseModel):
    """Response for task creation."""
    task_id: str
    redirect_url: str


# ── Endpoints ───────────────────────────────────────────────────────────────


@router.post("/sessions", response_model=SessionCreateResponse, status_code=201)
async def create_session() -> SessionCreateResponse:
    """
    Create a new chat session.
    
    Returns a session_id that should be used for subsequent messages.
    Sessions are stored in-memory and expire when the server restarts.
    """
    service = get_chat_service()
    session = await service.create_session()
    
    return SessionCreateResponse(
        session_id=session.session_id,
        created_at=session.created_at.isoformat(),
    )


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> dict[str, Any]:
    """
    Get a chat session with message history and current requirements.
    
    Returns the full session state including all messages and the
    currently extracted requirements.
    """
    service = get_chat_service()
    session = await service.get_session(session_id)
    return session.to_api_response()


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: str,
    request: MessageRequest,
) -> StreamingResponse:
    """
    Send a message and stream the LLM response.
    
    Returns a Server-Sent Events (SSE) stream with:
    - "content" events for each chunk of the response
    - "requirements" event with updated extracted requirements
    - "done" event when stream completes
    
    The frontend should use EventSource or fetch with a ReadableStream
    to consume this endpoint.
    """
    service = get_chat_service()
    
    async def event_generator():
        async for chunk in service.stream_response(session_id, request.message):
            yield chunk
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.patch("/sessions/{session_id}/requirements")
async def update_requirements(
    session_id: str,
    request: RequirementsUpdateRequest,
) -> dict[str, Any]:
    """
    Update requirements directly from the frontend panel.
    
    This allows users to edit extracted requirements in the side panel
    without going through the chat. Direct edits set confidence to 1.0
    (user-confirmed).
    
    Accepts partial updates - only provided fields are updated.
    """
    service = get_chat_service()
    
    # Convert request to dict, excluding None values
    update_dict = request.model_dump(exclude_none=True)
    
    session = await service.update_requirements(session_id, update_dict)
    return session.to_api_response()


@router.post("/sessions/{session_id}/create-task", response_model=TaskCreateResponse)
async def create_task(
    session_id: str,
    db_session: AsyncSession = Depends(get_session),
) -> TaskCreateResponse:
    """
    Create a task from the extracted requirements.
    
    Validates that all required fields are complete before creating.
    Returns the task_id and a redirect URL to the task detail page.
    
    Raises:
        400: Requirements not complete - missing required fields
        404: Session not found
    """
    service = get_chat_service()
    
    result = await service.create_task_from_requirements(session_id, db_session)
    
    return TaskCreateResponse(
        task_id=result["task_id"],
        redirect_url=result["redirect_url"],
    )


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str) -> dict[str, bool]:
    """
    Delete a chat session.
    
    Removes the session from memory. This is optional - sessions
    can be left to expire naturally when the server restarts.
    """
    service = get_chat_service()
    deleted = await service.delete_session(session_id)
    
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {"deleted": True}
