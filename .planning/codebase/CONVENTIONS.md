# Coding Conventions

**Analysis Date:** 2026-02-22

## Style Guide

### Python (Backend)

**Language Version:** Python 3.11+

**Formatting:**
- No explicit formatter (prettier/black) configuration detected
- 4-space indentation
- Line length follows PEP 8 conventions
- Maximum line length appears to be ~100 characters

**Import Organization:**
```python
# Standard library first
from __future__ import annotations
from contextlib import asynccontextmanager
from typing import AsyncGenerator

# Third-party next
from fastapi import FastAPI
from sqlalchemy import select

# Local imports last
from aadap.core.config import get_settings
from aadap.core.logging import get_logger
```

**Module Docstrings:**
All modules start with triple-quoted docstrings following this pattern:
```python
"""
AADAP — Module Name
=====================
Brief description of the module's purpose.

Architecture layer: L# (Layer Name).
Source of truth: DOCUMENT.md §Section.

Design decisions:
- Decision 1
- Decision 2

Usage:
    from aadap.module import function
    result = function()
"""
```

### TypeScript (Frontend)

**Language Version:** TypeScript 5.x

**Framework:** Next.js 16.x with React 19

**Formatting:**
- 2-space indentation
- No explicit ESLint/Prettier configuration detected
- ES module syntax

**Import Organization:**
```typescript
// Next.js imports first
import Link from 'next/link';

// Third-party next
import type { SomeType } from 'library';

// Local imports (relative)
import styles from './page.module.css';
```

**JSDoc Comments:**
```typescript
/**
 * AADAP — Module Name
 * ====================
 * Brief description.
 *
 * Features:
 * - Feature 1
 * - Feature 2
 */
```

## Naming Conventions

### Python

**Files:**
- Snake_case: `state_machine.py`, `token_tracker.py`
- Test files: `test_<module>.py` (e.g., `test_models.py`)

**Classes:**
- PascalCase: `Task`, `ExecutionService`, `AgentPoolManager`
- Abstract bases: `BaseAgent`, `BaseLLMClient`, `BaseDatabricksClient`
- Exceptions: `AgentLifecycleError`, `InvalidTransitionError`, `TokenBudgetExhaustedError`
- Enums: `TaskState`, `AgentState`, `Environment`

**Functions/Methods:**
- snake_case: `create_task()`, `get_allowed_transitions()`, `_do_execute()`
- Private methods: leading underscore `_reset()`, `_load_task()`
- Async functions: no special suffix, use `async def`

**Variables:**
- snake_case: `task_id`, `current_state`, `allowed_tools`
- Constants: UPPER_SNAKE_CASE: `TASK_STATES`, `VALID_TRANSITIONS`, `TERMINAL_STATES`
- Private instance attributes: leading underscore `_agent_id`, `_state`, `_client`

**Type Hints:**
```python
# Always use modern type syntax
from __future__ import annotations

def function(
    task_id: uuid.UUID,
    metadata: dict[str, Any] | None = None,
) -> TaskResponse:
    ...

# Use pipe for unions
value: str | None = None

# Use built-in generics (no typing module needed)
items: list[Task] = []
mapping: dict[str, Any] = {}
```

### TypeScript

**Files:**
- camelCase for utilities: `client.ts`, `types.ts`
- PascalCase for components: `page.tsx`, `page.module.css`

**Interfaces/Types:**
- PascalCase: `Task`, `TaskCreateRequest`, `ArtifactSummary`
- Response types: `*Response` suffix: `TaskListResponse`, `HealthResponse`
- Request types: `*Request` suffix: `TaskCreateRequest`, `TransitionRequest`

**Variables:**
- camelCase: `taskId`, `currentState`, `apiBase`

**Constants:**
- UPPER_SNAKE_CASE for mappings: `STATE_COLORS`, `STATE_LABELS`, `QUICK_ACTIONS`

## Code Patterns

### Dataclasses

Use `@dataclass` for simple data containers:
```python
from dataclasses import dataclass, field

@dataclass
class AgentContext:
    task_id: uuid.UUID
    task_data: dict[str, Any]
    token_budget: int = 50_000
    allowed_tools: set[str] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class LLMResponse:
    content: str
    tokens_used: int
    model: str
    metadata: dict[str, Any] = field(default_factory=dict)
```

### Pydantic Models

Use Pydantic for API schemas and configuration:
```python
from pydantic import BaseModel, Field

class TaskCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=512)
    description: str | None = None
    priority: int = Field(default=0, ge=0, le=10)
    environment: str = Field(
        default="SANDBOX",
        pattern=r"^(SANDBOX|PRODUCTION)$"
    )

    model_config = {"from_attributes": True}
```

### Abstract Base Classes

Define contracts with `abc.ABC`:
```python
import abc

class BaseAgent(abc.ABC):
    @abc.abstractmethod
    async def _do_execute(self, context: AgentContext) -> AgentResult:
        """Subclass implementation of task execution."""
        ...

class BaseLLMClient(abc.ABC):
    @abc.abstractmethod
    async def complete(self, prompt: str, model: str | None = None) -> LLMResponse:
        """Send a completion request to the LLM."""
        ...
```

### Factory Methods

Use class methods for construction from settings:
```python
@classmethod
def from_settings(cls) -> "AzureOpenAIClient":
    settings = get_settings()
    if not settings.azure_openai_api_key:
        raise ValueError("AADAP_AZURE_OPENAI_API_KEY is required")
    return cls(
        api_key=settings.azure_openai_api_key.get_secret_value(),
        endpoint=settings.azure_openai_endpoint,
    )
```

### Context Managers

Use for resource management:
```python
@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    await init_db()
    yield
    # Shutdown
    await close_db()

# Also used in tests:
class _async_cm:
    """Turn an async mock into an async context manager."""
    def __init__(self, value):
        self._value = value
    async def __aenter__(self):
        return self._value
    async def __aexit__(self, *args):
        pass
```

### Singleton Pattern

Use `@lru_cache` for settings:
```python
from functools import lru_cache

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
```

### TypeScript API Client Pattern

All API calls go through a centralized client:
```typescript
// frontend/src/api/client.ts
async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
    const cid = correlationId || generateCorrelationId();
    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        'X-Correlation-ID': cid,
    };
    const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
    if (!response.ok) {
        throw new ApiError(response.status, detail, cid);
    }
    return response.json();
}
```

## Error Handling

### Exception Hierarchies

Define domain-specific exceptions:
```python
class AgentLifecycleError(Exception):
    """Raised on invalid agent lifecycle transitions."""
    def __init__(self, agent_id: str, current: AgentState, attempted: str) -> None:
        self.agent_id = agent_id
        self.current_state = current
        self.attempted_action = attempted
        super().__init__(
            f"Agent '{agent_id}' cannot {attempted} in state {current.value}."
        )

class InvalidTransitionError(Exception):
    """Raised when an undefined transition is attempted (P0 bug)."""
    def __init__(self, from_state: TaskState, to_state: TaskState) -> None:
        self.from_state = from_state
        self.to_state = to_state
        allowed = VALID_TRANSITIONS.get(from_state, frozenset())
        super().__init__(
            f"Invalid transition {from_state.value} → {to_state.value}. "
            f"Allowed: {sorted(s.value for s in allowed)}."
        )
```

### HTTP API Errors

Use HTTPException with clear messages:
```python
from fastapi import HTTPException

# 404 for missing resources
if task is None:
    raise HTTPException(status_code=404, detail="Task not found.")

# 400 for invalid input
if state_upper not in TASK_STATES:
    raise HTTPException(
        status_code=400,
        detail=f"Invalid state '{state}'. Must be one of {TASK_STATES}",
    )

# 422 for validation errors (Pydantic handles automatically)
# 500 for unexpected failures
raise HTTPException(status_code=500, detail="Task creation failed.")
```

### Graceful Degradation

Services handle failures gracefully:
```python
async def execute_task(self, task_id: uuid.UUID) -> dict[str, Any]:
    try:
        # ... execution logic
    except Exception as exc:
        logger.error("execution.error", task_id=str(task_id), error=str(exc))
        # Try to transition to CANCELLED if possible
        try:
            current = await self._event_store.replay(task_id)
            if TaskState.CANCELLED in TaskStateMachine.get_allowed_transitions(current):
                await self._transition(task_id, current, TaskState.CANCELLED)
        except Exception:
            pass  # Best effort
        return {"task_id": str(task_id), "status": "FAILED", "error": str(exc)}
```

### TypeScript Error Handling

Custom error class with correlation ID:
```typescript
export class ApiError extends Error {
    constructor(
        public status: number,
        public detail: string,
        public correlationId: string
    ) {
        super(`API Error ${status}: ${detail}`);
        this.name = 'ApiError';
    }
}
```

## Logging

### Framework

**Library:** structlog with JSON output

**Configuration:**
```python
from aadap.core.logging import get_logger
logger = get_logger(__name__)
```

### Log Levels

- `DEBUG`: Detailed diagnostic information (SQL queries, LLM prompts)
- `INFO`: Normal operation events (task created, state transition)
- `WARNING`: Unexpected but recoverable (agent failed, auto-execute skipped)
- `ERROR`: Failures requiring attention (execution error, transition failed)

### Structured Logging Pattern

Use event-based logging with key-value pairs:
```python
logger.info("task.created", task_id=str(task_id), agent_type=body.agent_type)
logger.info("execution.transition", task_id=str(task_id), from_state=from_state.value, to_state=to_state.value)
logger.error("execution.error", task_id=str(task_id), error=str(exc))
```

**Format:**
- First argument: event name in `category.action` format
- Keyword arguments: structured context fields

### Correlation ID Injection

Correlation IDs are automatically added to all logs:
```python
# In aadap/core/logging.py
def _add_correlation_id(logger, method_name, event_dict):
    from aadap.core.middleware import correlation_id_ctx
    cid = correlation_id_ctx.get(None)
    if cid is not None:
        event_dict.setdefault("correlation_id", cid)
    return event_dict
```

### Invariant Comments

Document invariants directly in code:
```python
token_budget: Mapped[int] = mapped_column(
    Integer, nullable=False, default=50_000,
    comment="INV-04: Token budget per task (default 50,000)",
)
retry_count: Mapped[int] = mapped_column(
    Integer, nullable=False, default=0,
    comment="INV-03: bounded self-correction, max 3",
)
```

## Module Organization

### Package Structure

```
aadap/
├── __init__.py          # Public API exports
├── core/                 # Cross-cutting concerns
│   ├── config.py        # Settings management
│   ├── logging.py       # Structured logging
│   ├── middleware.py    # HTTP middleware
│   └── memory_store.py  # In-memory storage
├── api/                  # FastAPI routes
│   ├── deps.py          # Dependency injection
│   ├── health.py        # Health endpoint
│   └── routes/          # Route modules
├── db/                   # Database layer
│   ├── models.py        # SQLAlchemy models
│   └── session.py       # Session management
├── agents/              # Agent framework
│   ├── base.py          # Abstract agent
│   └── __init__.py      # Public exports
├── orchestrator/        # Orchestration logic
│   ├── state_machine.py # State machine
│   └── events.py        # Event store
├── integrations/        # External clients
│   ├── llm_client.py    # LLM abstraction
│   └── databricks_client.py
├── services/            # Business logic
│   └── execution.py     # Execution service
├── safety/              # Safety/analysis
│   └── approval_engine.py
└── memory/              # Memory systems
    └── vector_store.py
```

### Barrel Exports

Use `__init__.py` to expose public API:
```python
# aadap/agents/__init__.py
from aadap.agents.base import BaseAgent, AgentState, AgentContext, AgentResult
from aadap.agents.pool_manager import AgentPoolManager

__all__ = [
    "BaseAgent",
    "AgentState",
    "AgentContext",
    "AgentResult",
    "AgentPoolManager",
]
```

---

*Convention analysis: 2026-02-22*
