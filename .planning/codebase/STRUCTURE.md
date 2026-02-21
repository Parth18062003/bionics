# Codebase Structure

**Analysis Date:** 2026-02-22

## Directory Layout

```
D:\bionics/
├── aadap/                    # Main Python package (backend)
│   ├── agents/               # L4: Agent layer - AI agents and tools
│   ├── api/                  # L6: Presentation - FastAPI routes
│   ├── core/                 # L1: Infrastructure - config, logging, middleware
│   ├── db/                   # L2: Operational store - SQLAlchemy models
│   ├── integrations/         # L3: Integration - external service clients
│   ├── memory/               # L2: Memory tier - working memory, vectors
│   ├── orchestrator/         # L5: Orchestration - state machine, graph
│   ├── safety/               # L5: Safety - approval engine, analysis
│   ├── services/             # Domain services - execution, notifications
│   └── main.py               # FastAPI application entry point
├── frontend/                 # Next.js 16 frontend
│   ├── src/
│   │   ├── api/              # Type-safe API client
│   │   ├── app/              # Next.js App Router pages
│   │   ├── components/       # React components
│   │   └── lib/              # Utilities
│   └── package.json
├── alembic/                  # Database migrations
├── tests/                    # Pytest test suite
├── scripts/                  # Utility scripts
├── .planning/                # Planning documents (GSD output)
├── pyproject.toml            # Python project config
├── requirements.txt          # Python dependencies
└── docker-compose.yml        # Container orchestration
```

## Directory Purposes

### `aadap/` - Main Python Package

**`aadap/core/`** - Infrastructure Layer
- Purpose: Foundation services used by all layers
- Contains: Configuration, logging, middleware, memory store
- Key files:
  - `aadap/core/config.py` - Pydantic settings with environment binding
  - `aadap/core/logging.py` - Structured logging with structlog
  - `aadap/core/middleware.py` - Correlation ID middleware
  - `aadap/core/memory_store.py` - In-memory TTL-bound key-value store
  - `aadap/core/task_types.py` - Task mode and operation type enums

**`aadap/db/`** - Database Layer
- Purpose: SQLAlchemy models and session management
- Contains: ORM models, async session factory
- Key files:
  - `aadap/db/models.py` - Task, StateTransition, Artifact, ApprovalRequest, Execution, AuditEvent, PlatformResource
  - `aadap/db/session.py` - AsyncSession context manager

**`aadap/integrations/`** - Integration Layer
- Purpose: External service adapters
- Contains: LLM, Databricks, and Fabric clients
- Key files:
  - `aadap/integrations/llm_client.py` - Azure OpenAI and mock LLM clients
  - `aadap/integrations/databricks_client.py` - Databricks SDK wrapper
  - `aadap/integrations/fabric_client.py` - Microsoft Fabric REST client

**`aadap/agents/`** - Agent Layer
- Purpose: Stateless AI agents for code generation and execution
- Contains: Base agent, specialized agents, tools, adapters, factory
- Key files:
  - `aadap/agents/base.py` - Abstract BaseAgent with lifecycle management
  - `aadap/agents/factory.py` - Agent instantiation and pool wiring
  - `aadap/agents/pool_manager.py` - Agent pool lifecycle
  - `aadap/agents/developer_agent.py` - Databricks Python developer
  - `aadap/agents/fabric_agent.py` - Microsoft Fabric developer
  - `aadap/agents/validation_agent.py` - Code validation
  - `aadap/agents/optimization_agent.py` - Performance optimization
  - `aadap/agents/tools/` - Platform-specific tool implementations
  - `aadap/agents/adapters/` - Platform adapter abstractions
  - `aadap/agents/prompts/` - LLM prompt templates

**`aadap/orchestrator/`** - Orchestration Layer
- Purpose: Task lifecycle management via LangGraph
- Contains: State machine, graph, routing, dispatching, guards
- Key files:
  - `aadap/orchestrator/state_machine.py` - 25-state TaskState enum and transition map
  - `aadap/orchestrator/graph.py` - LangGraph StateGraph definition and execution
  - `aadap/orchestrator/dispatcher.py` - Agent dispatch routing
  - `aadap/orchestrator/routing.py` - Task routing decisions
  - `aadap/orchestrator/guards.py` - Transition validation and loop detection
  - `aadap/orchestrator/events.py` - Event store for state transitions
  - `aadap/orchestrator/scheduler.py` - Task scheduling
  - `aadap/orchestrator/checkpoints.py` - Checkpoint persistence

**`aadap/safety/`** - Safety Layer
- Purpose: Approval workflow and code analysis
- Contains: Approval engine, static/semantic analysis, pattern matching
- Key files:
  - `aadap/safety/approval_engine.py` - Human-in-the-loop approval lifecycle
  - `aadap/safety/static_analysis.py` - Code static analysis
  - `aadap/safety/semantic_analysis.py` - Semantic code analysis
  - `aadap/safety/pattern_matcher.py` - Dangerous pattern detection

**`aadap/memory/`** - Memory Layer
- Purpose: Tiered memory for agent context
- Contains: Working memory, vector store, knowledge graph
- Key files:
  - `aadap/memory/working_memory.py` - Agent-scoped TTL-bound working memory
  - `aadap/memory/vector_store.py` - ChromaDB vector store wrapper
  - `aadap/memory/knowledge_graph.py` - Knowledge graph storage
  - `aadap/memory/embeddings.py` - Embedding generation

**`aadap/services/`** - Domain Services
- Purpose: Cross-cutting business logic
- Contains: Execution service, notifications, platform explorers
- Key files:
  - `aadap/services/execution.py` - Task execution orchestration
  - `aadap/services/notifications.py` - Notification service
  - `aadap/services/databricks_explorer.py` - Databricks resource exploration
  - `aadap/services/fabric_explorer.py` - Fabric resource exploration
  - `aadap/services/marketplace.py` - Agent catalog service

**`aadap/api/`** - Presentation Layer
- Purpose: REST API endpoints
- Contains: FastAPI routers, dependencies, health checks
- Key files:
  - `aadap/api/routes/tasks.py` - Task CRUD and lifecycle endpoints
  - `aadap/api/routes/approvals.py` - Approval workflow endpoints
  - `aadap/api/routes/artifacts.py` - Artifact endpoints
  - `aadap/api/routes/marketplace.py` - Agent marketplace
  - `aadap/api/routes/execution.py` - Execution endpoints
  - `aadap/api/routes/explorer.py` - Platform resource explorer
  - `aadap/api/deps.py` - Request dependencies (session, correlation ID)
  - `aadap/api/health.py` - Health check endpoint

### `frontend/` - Next.js Frontend

**`frontend/src/app/`** - Next.js App Router Pages
- Purpose: Page components and routing
- Key files:
  - `frontend/src/app/layout.tsx` - Root layout with navigation
  - `frontend/src/app/page.tsx` - Home page
  - `frontend/src/app/dashboard/page.tsx` - Dashboard view
  - `frontend/src/app/tasks/page.tsx` - Task list
  - `frontend/src/app/tasks/new/page.tsx` - Task creation wizard
  - `frontend/src/app/tasks/[id]/page.tsx` - Task detail
  - `frontend/src/app/approvals/page.tsx` - Approval queue
  - `frontend/src/app/marketplace/page.tsx` - Agent marketplace

**`frontend/src/api/`** - API Client
- Purpose: Type-safe backend API access
- Key files:
  - `frontend/src/api/client.ts` - REST client with correlation IDs
  - `frontend/src/api/types.ts` - TypeScript type definitions

**`frontend/src/components/`** - React Components
- Purpose: Reusable UI components
- Key files:
  - `frontend/src/components/ui/TaskCreationWizard.tsx` - Task creation form
  - `frontend/src/components/ui/CodeViewer.tsx` - Code display
  - `frontend/src/components/ui/PhaseVisualization.tsx` - State visualization
  - `frontend/src/components/ui/ErrorDiagnostics.tsx` - Error display

### `tests/` - Test Suite

- Purpose: Pytest tests for all layers
- Contains: Unit tests, integration tests
- Key files:
  - `tests/test_state_machine.py` - State machine validation

### `alembic/` - Database Migrations

- Purpose: SQLAlchemy schema migrations
- Key files:
  - `alembic/env.py` - Alembic configuration
  - `alembic/versions/` - Migration scripts

## Key File Locations

### Entry Points

| Entry Point | Location | Purpose |
|-------------|----------|---------|
| Backend Server | `aadap/main.py` | FastAPI application factory |
| LangGraph Execution | `aadap/orchestrator/graph.py:run_task_graph()` | Task orchestration |
| Database Migrations | `alembic/` | Schema versioning |
| Frontend Server | `frontend/src/app/` | Next.js pages |

### Configuration

| Config | Location | Purpose |
|--------|----------|---------|
| Python Project | `pyproject.toml` | Package metadata, dependencies |
| Python Dependencies | `requirements.txt` | Pinned dependencies |
| Frontend Package | `frontend/package.json` | NPM dependencies |
| Environment | `.env.example` | Environment variable template |
| App Settings | `aadap/core/config.py` | Pydantic settings class |

### Core Logic

| Component | Location | Purpose |
|-----------|----------|---------|
| State Machine | `aadap/orchestrator/state_machine.py` | 25-state task lifecycle |
| Graph Definition | `aadap/orchestrator/graph.py` | LangGraph StateGraph |
| Agent Base | `aadap/agents/base.py` | Abstract agent contract |
| Approval Engine | `aadap/safety/approval_engine.py` | Human-in-the-loop |
| Database Models | `aadap/db/models.py` | SQLAlchemy ORM |

### Testing

| Test Type | Location |
|-----------|----------|
| Unit Tests | `tests/` |
| State Machine Tests | `tests/test_state_machine.py` |

## Naming Conventions

### Files

- **Python modules:** `snake_case.py` (e.g., `state_machine.py`, `approval_engine.py`)
- **Test files:** `test_{module}.py` (e.g., `test_state_machine.py`)
- **React components:** `PascalCase.tsx` (e.g., `TaskCreationWizard.tsx`)
- **TypeScript modules:** `camelCase.ts` (e.g., `client.ts`)

### Directories

- **Python packages:** `snake_case/` (e.g., `orchestrator/`, `integrations/`)
- **React pages:** App Router conventions (`page.tsx`, `layout.tsx`)
- **Component directories:** `snake_case/` (e.g., `components/ui/`)

### Code Elements

- **Classes:** `PascalCase` (e.g., `TaskStateMachine`, `BaseAgent`)
- **Functions:** `snake_case` (e.g., `run_task_graph`, `create_task`)
- **Constants:** `UPPER_SNAKE_CASE` (e.g., `VALID_TRANSITIONS`, `TERMINAL_STATES`)
- **Enums:** `PascalCase` for enum name, `UPPER_CASE` for values

## Where to Add New Code

### New Feature (Backend)

| Component | Location |
|-----------|----------|
| API endpoint | `aadap/api/routes/{domain}.py` |
| Business logic | `aadap/services/{domain}.py` or `aadap/orchestrator/` |
| Database model | `aadap/db/models.py` |
| Integration client | `aadap/integrations/{service}_client.py` |
| Agent | `aadap/agents/{domain}_agent.py` |

### New Feature (Frontend)

| Component | Location |
|-----------|----------|
| New page | `frontend/src/app/{route}/page.tsx` |
| API integration | `frontend/src/api/client.ts` + `frontend/src/api/types.ts` |
| UI component | `frontend/src/components/ui/{Component}.tsx` |

### New Agent

1. Create agent class in `aadap/agents/{name}_agent.py` extending `BaseAgent`
2. Create prompts in `aadap/agents/prompts/{name}.py`
3. Register tools in `aadap/agents/tools/{platform}_tools.py` if needed
4. Add to factory in `aadap/agents/factory.py`

### New Platform Integration

1. Create client in `aadap/integrations/{platform}_client.py`
2. Create adapter in `aadap/agents/adapters/{platform}_adapter.py`
3. Add tools in `aadap/agents/tools/{platform}_tools.py`
4. Register in factory `aadap/agents/factory.py`

### New Database Model

1. Add model class to `aadap/db/models.py`
2. Create migration: `alembic revision --autogenerate -m "Add {model}"`
3. Apply migration: `alembic upgrade head`

### New API Endpoint

1. Add route handler in `aadap/api/routes/{domain}.py`
2. Add request/response schemas (Pydantic) in same file
3. Register router in `aadap/main.py` if new file
4. Add frontend client method in `frontend/src/api/client.ts`
5. Add types in `frontend/src/api/types.ts`

## Special Directories

### `.planning/`
- Purpose: GSD-generated planning documents
- Generated: Yes (by `/gsd-map-codebase` and `/gsd-plan-phase`)
- Committed: Yes

### `alembic/versions/`
- Purpose: Database migration scripts
- Generated: Yes (by `alembic revision`)
- Committed: Yes

### `frontend/.next/`
- Purpose: Next.js build output
- Generated: Yes (by `npm run build` or `npm run dev`)
- Committed: No (in `.gitignore`)

### `__pycache__/`
- Purpose: Python bytecode cache
- Generated: Yes (by Python interpreter)
- Committed: No (in `.gitignore`)

---

*Structure analysis: 2026-02-22*
