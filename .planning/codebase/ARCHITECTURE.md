# Architecture

**Analysis Date:** 2026-02-22

## Pattern Overview

**Overall:** Layered Monolith with Event-Sourced Orchestration

AADAP (Autonomous AI Developer Agents Platform) is a multi-agent orchestration platform built on a 6-layer architecture with LangGraph-based workflow orchestration. The system manages AI agents that generate, validate, optimize, and deploy data engineering code to Databricks and Microsoft Fabric platforms.

**Key Characteristics:**
- **Layered Architecture:** 6 distinct layers from infrastructure to presentation
- **Event Sourcing:** Immutable state transitions with full audit trail
- **Stateless Agents:** Agents are untrusted workers with no persistent state
- **Human-in-the-Loop:** Approval gates for destructive operations
- **Platform Agnostic:** Adapters abstract Databricks and Fabric differences
- **Trust Boundaries:** UI → API → Orchestrator → Agents enforced strictly

## Layers

### L1: Infrastructure (`aadap/core/`, `aadap/db/`)

- **Purpose:** Foundation services, configuration, database access
- **Location:** `aadap/core/`, `aadap/db/`
- **Contains:** Configuration management, logging, memory store, SQLAlchemy models, Alembic migrations
- **Depends on:** External services (PostgreSQL, Azure OpenAI)
- **Used by:** All other layers

**Key Components:**
- `aadap/core/config.py` - Pydantic settings with environment variable binding
- `aadap/core/memory_store.py` - In-memory TTL-bound key-value store
- `aadap/db/models.py` - SQLAlchemy declarative models (Task, StateTransition, Artifact, ApprovalRequest, Execution, AuditEvent)
- `aadap/db/session.py` - Async session management with context managers

### L2: Operational Store (`aadap/db/`, `aadap/memory/`)

- **Purpose:** Persistent and ephemeral data storage with tiered memory
- **Location:** `aadap/db/`, `aadap/memory/`
- **Contains:** Database models, vector store, working memory, knowledge graph
- **Depends on:** L1 infrastructure
- **Used by:** L3-L5 for data persistence

**Memory Tiers:**
- Tier 1: In-memory working memory (TTL-bound, agent-scoped)
- Tier 2: PostgreSQL operational store (persistent task state)
- Tier 3: Blob storage (large artifacts - via `storage_uri`)

### L3: Integration (`aadap/integrations/`)

- **Purpose:** External service adapters and API clients
- **Location:** `aadap/integrations/`
- **Contains:** LLM client, Databricks client, Fabric client
- **Depends on:** L1 configuration
- **Used by:** L4 agents for platform operations

**Key Components:**
- `aadap/integrations/llm_client.py` - Abstract LLM client with Azure OpenAI and mock implementations
- `aadap/integrations/databricks_client.py` - Databricks SDK wrapper
- `aadap/integrations/fabric_client.py` - Microsoft Fabric REST API client

### L4: Agent Layer (`aadap/agents/`)

- **Purpose:** Stateless, governed AI agents for code generation and execution
- **Location:** `aadap/agents/`
- **Contains:** Base agent abstraction, specialized agents, tool registry, platform adapters
- **Depends on:** L3 integration clients
- **Used by:** L5 orchestrator for task execution

**Agent Types:**
- `DeveloperAgent` - Databricks Python code generation
- `FabricAgent` - Microsoft Fabric pipeline/notebook generation
- `ValidationAgent` - Code validation and safety checks
- `OptimizationAgent` - Performance optimization
- `OrchestratorAgent` - Multi-step workflow coordination
- `CatalogAgent` - Data catalog operations
- `IngestionAgent` - Data ingestion pipelines
- `ETLPipelineAgent` - ETL workflow generation
- `JobSchedulerAgent` - Job scheduling and orchestration

**Invariants:**
- No agent bypasses orchestrator
- Tool access must be explicitly granted
- Token budget enforced per task (INV-04)

### L5: Orchestration (`aadap/orchestrator/`)

- **Purpose:** Task lifecycle management via LangGraph StateGraph
- **Location:** `aadap/orchestrator/`
- **Contains:** State machine, graph definition, routing, dispatching, scheduling
- **Depends on:** L4 agents, L2 data store
- **Used by:** L6 API for task operations

**Key Components:**
- `aadap/orchestrator/state_machine.py` - 25-state deterministic task state machine
- `aadap/orchestrator/graph.py` - LangGraph StateGraph compilation and execution
- `aadap/orchestrator/dispatcher.py` - Agent dispatch and routing
- `aadap/orchestrator/guards.py` - Transition validation and loop detection

### L6: Presentation (`aadap/api/`, `frontend/`)

- **Purpose:** REST API and web UI
- **Location:** `aadap/api/`, `frontend/`
- **Contains:** FastAPI routers, Next.js pages, React components
- **Depends on:** L5 orchestrator
- **Used by:** External clients (browser, CLI, integrations)

**API Endpoints:**
- `/api/v1/tasks` - Task CRUD and lifecycle
- `/api/v1/approvals` - Approval workflow
- `/api/v1/artifacts` - Code artifact management
- `/api/v1/marketplace` - Agent catalog
- `/api/v1/executions` - Execution records
- `/api/v1/explorer/{platform}` - Platform resource exploration

## Data Flow

### Task Creation Flow:

1. User submits task via Frontend (`frontend/src/app/tasks/new/page.tsx`)
2. API client calls `POST /api/v1/tasks` (`frontend/src/api/client.ts`)
3. API route creates task via `graph.create_task()` (`aadap/api/routes/tasks.py`)
4. Task persisted to PostgreSQL in `SUBMITTED` state
5. If `auto_execute=true`, `ExecutionService.execute_task()` triggered
6. LangGraph graph invoked via `run_task_graph()` (`aadap/orchestrator/graph.py`)
7. Graph nodes execute: PARSING → PLANNING → AGENT_ASSIGNMENT → IN_DEVELOPMENT → ...
8. Each transition persisted as `StateTransition` record (event sourcing)
9. Agent generates code artifact, stored in `artifacts` table
10. Approval requested for destructive operations
11. Human approves/rejects via UI, API updates `ApprovalRequest`
12. If approved, code deployed to platform (Databricks/Fabric)
13. Task reaches `COMPLETED` or `CANCELLED` terminal state

### State Management:

- **PostgreSQL:** Authoritative task state, transitions, artifacts, approvals
- **In-Memory Store:** Working memory (agent context), token tracking, checkpoints
- **ChromaDB:** Vector embeddings for semantic search (Phase 6)
- **Event Store:** Append-only `StateTransition` records enable state replay

## Key Abstractions

### TaskState (25-State Machine)

- **Purpose:** Deterministic task lifecycle states
- **Examples:** `aadap/orchestrator/state_machine.py`, `aadap/db/models.py`
- **Pattern:** StrEnum with exhaustive transition whitelist

```python
class TaskState(StrEnum):
    SUBMITTED = "SUBMITTED"
    PARSING = "PARSING"
    PARSED = "PARSED"
    # ... 22 more states
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
```

### BaseAgent

- **Purpose:** Abstract agent contract with lifecycle management
- **Examples:** `aadap/agents/base.py`
- **Pattern:** Template method with `_do_execute()` abstract method

```python
class BaseAgent(abc.ABC):
    async def accept_task(self, context: AgentContext) -> bool
    async def execute(self, context: AgentContext) -> AgentResult
    @abc.abstractmethod
    async def _do_execute(self, context: AgentContext) -> AgentResult
```

### PlatformAdapter

- **Purpose:** Unified interface for Databricks and Fabric operations
- **Examples:** `aadap/agents/adapters/base.py`, `aadap/agents/adapters/fabric_adapter.py`
- **Pattern:** Strategy pattern with platform-specific implementations

### ApprovalEngine

- **Purpose:** Human-in-the-loop approval lifecycle
- **Examples:** `aadap/safety/approval_engine.py`
- **Pattern:** State machine with autonomy policy matrix

## Entry Points

### FastAPI Application

- **Location:** `aadap/main.py`
- **Triggers:** `uvicorn aadap.main:app --host 0.0.0.0 --port 8000`
- **Responsibilities:** Application factory, lifespan management, router registration

### LangGraph Execution

- **Location:** `aadap/orchestrator/graph.py:run_task_graph()`
- **Triggers:** API endpoint, ExecutionService
- **Responsibilities:** State graph compilation, node execution, state persistence

### Database Migrations

- **Location:** `alembic/`
- **Triggers:** `alembic upgrade head`
- **Responsibilities:** Schema migrations via SQLAlchemy models

### Frontend Development Server

- **Location:** `frontend/`
- **Triggers:** `npm run dev` (Next.js 16)
- **Responsibilities:** React UI, API client, user interactions

## Error Handling

**Strategy:** Layered error handling with typed exceptions

**Patterns:**
- **API Layer:** HTTP status codes via FastAPI `HTTPException`
- **Orchestration Layer:** `InvalidTransitionError`, `InvalidStateError` for state machine violations
- **Agent Layer:** `AgentLifecycleError` for lifecycle violations
- **Safety Layer:** `ApprovalRequiredError`, `ApprovalRejectedError`, `ApprovalExpiredError`
- **Integration Layer:** Wrappers around SDK exceptions with logging

**Error Propagation:**
1. Lower layers raise typed exceptions
2. Orchestrator catches and logs with context
3. API layer converts to appropriate HTTP status
4. Frontend displays user-friendly error messages

## Cross-Cutting Concerns

**Logging:** Structured logging via `structlog` with JSON output (`aadap/core/logging.py`)

**Correlation:** Request correlation IDs via `X-Correlation-ID` header (`aadap/core/middleware.py`)

**Validation:** Pydantic models for all API request/response schemas

**Authentication:** Placeholder via `get_current_user` dependency (returns "anonymous")

**Audit Trail:** Full audit via `AuditEvent` table (INV-06)

---

*Architecture analysis: 2026-02-22*
