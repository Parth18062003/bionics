# Architecture Research

**Domain:** AADAP Platform Enhancements
**Researched:** 2026-02-22
**Confidence:** HIGH

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                 L6: Presentation Layer                       │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐            │
│  │  Chat UI    │ │  Log Viewer │ │ Code Editor │            │
│  │  (NEW)      │ │  (NEW)      │ │ (NEW)       │            │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘            │
│         │               │               │                    │
│  ┌──────┴──────┐ ┌──────┴──────┐ ┌──────┴──────┐            │
│  │ Agent Ctrl  │ │ Cost Dash   │ │ Settings    │            │
│  │ Panel (NEW) │ │ (NEW)       │ │ (NEW)       │            │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘            │
├─────────┴───────────┴───────────┴───────────────────────────┤
│                 L5: Orchestration Layer                      │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┐    │
│  │              LangGraph Orchestrator                   │    │
│  │         (existing - aadap/orchestrator/)             │    │
│  └─────────────────────────┬───────────────────────────┘    │
├─────────────────────────────┼───────────────────────────────┤
│                 L4: Agent Layer                              │
├─────────────────────────────┼───────────────────────────────┤
│  ┌───────────┐ ┌───────────┐ ┌───────────┐                  │
│  │Developer  │ │Validation │ │Optimizer  │                  │
│  │Agent      │ │Agent      │ │Agent      │                  │
│  └─────┬─────┘ └─────┬─────┘ └─────┬─────┘                  │
├────────┴─────────────┴─────────────┴────────────────────────┤
│                 L3: Integration Layer                        │
├─────────────────────────────────────────────────────────────┤
│  ┌───────────┐ ┌───────────┐ ┌───────────┐                  │
│  │LLM Client │ │Databricks │ │Fabric     │                  │
│  │           │ │Client     │ │Client     │                  │
│  └─────┬─────┘ └─────┬─────┘ └─────┬─────┘                  │
├────────┴─────────────┴─────────────┴────────────────────────┤
│                 L2: Operational Store                        │
├─────────────────────────────────────────────────────────────┤
│  ┌───────────┐ ┌───────────┐ ┌───────────┐                  │
│  │PostgreSQL │ │Memory     │ │Vector     │                  │
│  │(Task,Logs)│ │Store      │ │Store      │                  │
│  └───────────┘ └───────────┘ └───────────┘                  │
├─────────────────────────────────────────────────────────────┤
│                 L1: Infrastructure                           │
├─────────────────────────────────────────────────────────────┤
│  ┌───────────┐ ┌───────────┐ ┌───────────┐                  │
│  │Config     │ │Logging    │ │Middleware │                  │
│  └───────────┘ └───────────┘ └───────────┘                  │
└─────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

### New Components (This Project)

| Component | Layer | Responsibility | Location |
|-----------|-------|----------------|----------|
| **Chat UI** | L6 | Conversational task creation, requirement extraction | `frontend/src/app/chat/`, `frontend/src/components/chat/` |
| **Log Viewer** | L6 | Real-time task log display, filtering, search | `frontend/src/app/logs/`, `frontend/src/components/logs/` |
| **Code Editor** | L6 | Monaco-based code viewing/editing, diff view | `frontend/src/app/artifacts/[id]/edit/` |
| **Agent Control Panel** | L6 | Agent status, pause/resume, queue management | `frontend/src/app/agents/` |
| **Cost Dashboard** | L6 | LLM + platform cost visualization, alerts | `frontend/src/app/costs/` |
| **Settings UI** | L6 | Platform connection management, credentials | `frontend/src/app/settings/` |
| **Chat API** | L5 | Streaming chat endpoint, requirement parsing | `aadap/api/routes/chat.py` |
| **Logs API** | L5 | Paginated log retrieval, SSE streaming | `aadap/api/routes/logs.py` |
| **Agents API** | L5 | Agent status, control endpoints | `aadap/api/routes/agents.py` |
| **Costs API** | L5 | Cost aggregation, reporting | `aadap/api/routes/costs.py` |
| **Settings API** | L5 | Connection config CRUD, test endpoints | `aadap/api/routes/settings.py` |
| **Token Tracker** | L3 | LLM token counting, cost calculation | `aadap/integrations/token_tracker.py` |
| **Cost Store** | L2 | Cost records, aggregation tables | `aadap/db/models.py` (add CostRecord) |
| **Log Store** | L2 | Structured task logs, correlation | `aadap/db/models.py` (add TaskLog) |

## Recommended Project Structure

```
frontend/src/
├── app/
│   ├── chat/                    # Dedicated chat page
│   │   ├── page.tsx
│   │   └── components/
│   │       ├── ChatInterface.tsx
│   │       ├── MessageList.tsx
│   │       └── RequirementPreview.tsx
│   ├── logs/                    # Dedicated log viewer
│   │   ├── page.tsx
│   │   └── components/
│   │       ├── LogViewer.tsx
│   │       ├── LogFilter.tsx
│   │       └── LogSearch.tsx
│   ├── artifacts/
│   │   └── [id]/
│   │       └── edit/
│   │           └── page.tsx     # Code editor page
│   ├── agents/                  # Agent control panel
│   │   ├── page.tsx
│   │   └── components/
│   │       ├── AgentCard.tsx
│   │       ├── AgentQueue.tsx
│   │       └── AgentControls.tsx
│   ├── costs/                   # Cost dashboard
│   │   ├── page.tsx
│   │   └── components/
│   │       ├── CostChart.tsx
│   │       ├── CostTable.tsx
│   │       └── CostAlerts.tsx
│   ├── settings/                # Platform settings
│   │   ├── page.tsx
│   │   └── components/
│   │       ├── DatabricksConfig.tsx
│   │       ├── FabricConfig.tsx
│   │       └── ConnectionTest.tsx
│   └── tasks/
│       └── [id]/
│           ├── page.tsx
│           └── components/
│               ├── TaskLogs.tsx     # Embedded logs
│               └── ArtifactEditor.tsx
├── components/
│   ├── chat/
│   │   └── ChatPanel.tsx           # Slide-out chat panel
│   └── logs/
│       └── EmbeddedLogViewer.tsx   # Embedded log component
└── lib/
    └── api/
        ├── chat.ts
        ├── logs.ts
        ├── agents.ts
        ├── costs.ts
        └── settings.ts

aadap/
├── api/
│   └── routes/
│       ├── chat.py              # POST /api/v1/chat/task (streaming)
│       ├── logs.py              # GET /api/v1/tasks/{id}/logs
│       ├── agents.py            # GET/POST /api/v1/agents
│       ├── costs.py             # GET /api/v1/costs/*
│       └── settings.py          # GET/PUT /api/v1/settings/*
├── services/
│   ├── chat_service.py          # Chat orchestration, requirement extraction
│   ├── log_service.py           # Log aggregation, correlation
│   └── cost_service.py          # Cost calculation, aggregation
├── integrations/
│   └── token_tracker.py         # Token counting wrapper for LLM client
└── db/
    └── models.py                # Add: TaskLog, CostRecord, PlatformConnection
```

## Architectural Patterns

### Pattern 1: Streaming Chat with SSE

**What:** Server-Sent Events for chat streaming (not WebSocket)
**When to use:** Chat UI where server pushes updates to client
**Trade-offs:** Simpler than WebSocket, unidirectional is sufficient for chat

```
Client                    Server
  │                         │
  │──POST /chat/task───────>│
  │                         │──LLM call (streaming)
  │<──SSE: chunk 1──────────│
  │<──SSE: chunk 2──────────│
  │<──SSE: chunk 3──────────│
  │<──SSE: [DONE]───────────│
```

### Pattern 2: Polling for Real-time Updates

**What:** TanStack Query with `refetchInterval` for status/log updates
**When to use:** Agent status, task logs (not chat)
**Trade-offs:** Simpler than WebSocket, acceptable latency for 1-5s intervals

```tsx
const { data: logs } = useQuery({
  queryKey: ['task-logs', taskId],
  queryFn: () => fetchTaskLogs(taskId),
  refetchInterval: 1000, // Poll every 1 second
});
```

### Pattern 3: Lazy-loaded Monaco Editor

**What:** Dynamic import with SSR disabled for Monaco
**When to use:** Code editor in Next.js App Router
**Trade-offs:** Prevents hydration mismatch, reduces initial bundle

```tsx
const Editor = dynamic(
  () => import('@monaco-editor/react').then(mod => mod.Editor),
  { ssr: false, loading: () => <EditorSkeleton /> }
);
```

## Data Flow

### Chat-based Task Creation Flow

```
User Input (Chat)
    ↓
ChatPanel.tsx / ChatInterface.tsx
    ↓ POST /api/v1/chat/task (SSE)
chat.py → ChatService
    ↓ Stream to LLM
Azure OpenAI (GPT-4o)
    ↓ Streamed response
ChatService extracts structured requirement
    ↓ User confirms
POST /api/v1/tasks (create task)
    ↓
Existing task flow continues...
```

### Log Streaming Flow

```
Task Execution
    ↓ (emit log events)
Orchestrator → Agent → Tool
    ↓ (structured logging)
aadap/core/logging.py
    ↓ (write to DB)
TaskLog table (task_id, timestamp, level, message, correlation_id)
    ↓ (polling)
Frontend: EmbeddedLogViewer or LogViewer page
    ↓ GET /api/v1/tasks/{id}/logs?since=timestamp
logs.py → LogService
    ↓
Return paginated logs
```

### Cost Tracking Flow

```
LLM API Call
    ↓
TokenTracker wrapper
    ↓ (count tokens)
tiktoken library
    ↓ (calculate cost)
CostService.record_llm_cost(task_id, agent, tokens, model)
    ↓ (persist)
CostRecord table (task_id, agent_type, tokens_in, tokens_out, cost_usd)
    ↓ (aggregate)
Cost Dashboard queries
    ↓ GET /api/v1/costs/summary?period=7d
costs.py → CostService
    ↓
Return aggregated costs
```

## Integration Points with Existing AADAP

### L6 Presentation Integration

| New Component | Integrates With | How |
|---------------|-----------------|-----|
| ChatPanel | Layout component | Slide-out Sheet from shadcn/ui |
| ChatInterface | API client | New `chat.ts` API module |
| LogViewer | Task detail page | Embedded + standalone page |
| Code Editor | Artifact detail | Replace read-only code display |
| Agent Control | Existing agents | New API endpoints |
| Cost Dashboard | New page | Standalone dashboard |
| Settings | Config system | Platform connection CRUD |

### L5 Orchestration Integration

| New Service | Integrates With | How |
|-------------|-----------------|-----|
| ChatService | Orchestrator | After extraction, call `graph.create_task()` |
| LogService | Logging middleware | Read from structured log sink |
| CostService | LLM client | Wrap `llm_client.py` calls |

### L2 Data Store Integration

| New Model | Extends | Migration |
|-----------|---------|-----------|
| TaskLog | Existing models | `alembic revision --autogenerate` |
| CostRecord | New table | Add to `models.py` |
| PlatformConnection | New table | For settings feature |

## Build Order (Dependencies)

```
Phase 1: Infrastructure
├── Add TaskLog model to db/models.py
├── Add CostRecord model to db/models.py
├── Add PlatformConnection model to db/models.py
└── Run Alembic migration

Phase 2: Chatbot
├── Install @assistant-ui/react
├── Create ChatService (backend)
├── Create /api/v1/chat/task endpoint (SSE)
├── Create ChatInterface page component
├── Create ChatPanel slide-out component
└── Integrate with existing task creation

Phase 3: Logging
├── Create LogService (backend)
├── Create /api/v1/tasks/{id}/logs endpoint
├── Install @melloware/react-logviewer
├── Create EmbeddedLogViewer component
├── Create LogViewer page (dedicated)
└── Add log emission to orchestrator/agents

Phase 4: Code Editor
├── Install @monaco-editor/react
├── Create lazy-loaded Editor component
├── Create DiffEditor component
├── Add edit artifact API endpoint
└── Integrate with artifact detail page

Phase 5: Agent Control Panel
├── Create /api/v1/agents endpoints (status, pause, resume)
├── Create AgentCard component
├── Create AgentQueue component
├── Create AgentControls component
└── Add agent status polling

Phase 6: Cost Management
├── Create TokenTracker wrapper
├── Wrap LLM client calls
├── Create CostService (backend)
├── Create /api/v1/costs/* endpoints
├── Install recharts
├── Create CostChart components
└── Create Cost Dashboard page

Phase 7: Settings
├── Create /api/v1/settings/* endpoints
├── Create connection test logic
├── Install react-hook-form + zod
├── Create DatabricksConfig form
├── Create FabricConfig form
└── Create Settings page
```

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 0-100 users | Current architecture sufficient, polling at 1-5s |
| 100-1000 users | Consider WebSocket for logs, add Redis for log buffer |
| 1000+ users | Separate log ingestion service, time-series DB for costs |

## Anti-Patterns

### Anti-Pattern 1: WebSocket for Everything

**What people do:** Use WebSocket for all real-time updates
**Why it's wrong:** SSE is simpler for server→client; polling is sufficient for low-frequency
**Do this instead:** SSE for chat, polling (1-5s) for logs/status, WebSocket only if needed

### Anti-Pattern 2: Log Everything to Database

**What people do:** Write every log line to PostgreSQL
**Why it's wrong:** High write volume, slow queries, storage bloat
**Do this instead:** Buffer logs in memory, batch write, archive old logs to blob storage

### Anti-Pattern 3: Cost Tracking After the Fact

**What people do:** Parse LLM API responses for token counts post-hoc
**Why it's wrong:** Misses costs from failed calls, incomplete data
**Do this instead:** Wrap LLM client, count tokens before and after every call

---

*Architecture research for: AADAP Platform Enhancements*
*Researched: 2026-02-22*
