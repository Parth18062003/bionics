# Roadmap: AADAP Platform Enhancements

## Overview

This roadmap delivers 6 user-facing features to the AADAP platform: conversational task creation chatbot, real-time logging system, code editor with diff view, agent control panel, cost management dashboard, and platform settings UI. The journey starts with foundational database models and exception handling fixes, then incrementally delivers features that enhance user interaction, observability, and control.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Infrastructure & Exception Handling** - Database models and robust error handling foundation (completed 2026-02-22)
- [ ] **Phase 2: Chatbot** - Conversational task creation with natural language
- [ ] **Phase 3: Logging** - Real-time task logging and observability
- [ ] **Phase 4: Code Editor** - View, edit, and version generated code
- [ ] **Phase 5: Agent Control** - Monitor and control agent behavior
- [ ] **Phase 6: Cost Management** - Track, analyze, and budget LLM costs
- [ ] **Phase 7: Platform Settings** - Configure and validate platform connections

## Phase Details

### Phase 1: Infrastructure & Exception Handling
**Goal**: Platform has the database foundation for new features and robust error handling in core execution paths
**Depends on**: Nothing (first phase)
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, EXCPT-01, EXCPT-02, EXCPT-03, EXCPT-04, EXCPT-05, EXCPT-06, EXCPT-07
**Success Criteria** (what must be TRUE):
  1. User can view logs and costs for any task via new database models (TaskLog, CostRecord)
  2. Admin can configure platform connections securely through database (no hardcoded credentials)
  3. Developers see meaningful error messages instead of silent failures in orchestrator and agents
  4. All core execution paths use async patterns consistently (no sync wrappers)
**Plans**: 4 plans

Plans:
- [ ] 01-01-PLAN.md — Create exception taxonomy, database models (TaskLog, CostRecord, PlatformConnection), remove hardcoded credentials, Alembic migration
- [ ] 01-02-PLAN.md — Replace bare except handlers in orchestrator (graph.py, graph_executor.py) with specific exception types
- [ ] 01-03-PLAN.md — Replace bare except in execution.py, add logging to empty pass statements in agent adapters
- [ ] 01-04-PLAN.md — Remove ThreadPoolExecutor sync wrappers from approval_engine.py, update callers to async

### Phase 2: Chatbot
**Goal**: Users can create tasks through natural language conversation
**Depends on**: Phase 1
**Requirements**: CHAT-01, CHAT-02, CHAT-03, CHAT-04, CHAT-05, CHAT-06, CHAT-07
**Success Criteria** (what must be TRUE):
  1. User can type natural language requirements and receive streaming LLM responses
  2. User sees extracted structured requirements for confirmation before task creation
  3. User can access chat from dedicated page (/chat) or slide-out panel from any page
  4. Chat conversation history persists during the session
**Plans**: 2 plans

Plans:
- [ ] 02-01-PLAN.md — Chat backend service with SSE streaming and requirement extraction
- [ ] 02-02-PLAN.md — Chat frontend (dedicated page and slide-out panel)

### Phase 3: Logging
**Goal**: Users can monitor and debug running tasks through comprehensive log visibility
**Depends on**: Phase 1
**Requirements**: LOGS-01, LOGS-02, LOGS-03, LOGS-04, LOGS-05, LOGS-06, LOGS-07, LOGS-08
**Success Criteria** (what must be TRUE):
  1. User sees real-time logs embedded in task detail page
  2. User can filter logs by level and search by text content
  3. User can access dedicated log viewer at /logs route with export capability
  4. Logs display timestamp, level, message, and correlation ID for debugging
**Plans**: 2 plans

Plans:
- [ ] 03-01: Log service with structured emissions and API endpoints
- [ ] 03-02: Log viewer frontend (embedded and dedicated page)

### Phase 4: Code Editor
**Goal**: Users can view, edit, and version generated code before deployment
**Depends on**: Phase 3 (logging for debugging context)
**Requirements**: EDIT-01, EDIT-02, EDIT-03, EDIT-04, EDIT-05, EDIT-06
**Success Criteria** (what must be TRUE):
  1. User views generated code with syntax highlighting (Python/PySpark)
  2. User edits code and sees diff compared to original
  3. User saves edited code as new artifact version
  4. Editor loads without hydration issues (lazy loading)
**Plans**: 2 plans

Plans:
- [ ] 04-01: Artifact version storage and diff API
- [ ] 04-02: Monaco editor frontend with diff view

### Phase 5: Agent Control
**Goal**: Users can monitor and control agent behavior and task assignments
**Depends on**: Phase 3 (logging for trace context)
**Requirements**: AGENT-01, AGENT-02, AGENT-03, AGENT-04, AGENT-05, AGENT-06, AGENT-07
**Success Criteria** (what must be TRUE):
  1. User sees all agents with current status (idle, busy, degraded)
  2. User can pause/resume individual agents
  3. User can view task queue and force reassignment
  4. Agent status updates reflect current state within 2 seconds (polling)
**Plans**: 2 plans

Plans:
- [ ] 05-01: Agent control API (status, pause/resume, reassignment)
- [ ] 05-02: Agent control panel frontend

### Phase 6: Cost Management
**Goal**: Users can track, analyze, and budget LLM and compute costs
**Depends on**: Phase 1 (CostRecord model, TokenTracker)
**Requirements**: COST-01, COST-02, COST-03, COST-04, COST-05, COST-06, COST-07
**Success Criteria** (what must be TRUE):
  1. User sees cost breakdown by time period, agent type, and task
  2. User can set budget alerts at threshold amounts
  3. User views cost trend chart over time
  4. User can export cost reports as CSV
**Plans**: 2 plans

Plans:
- [ ] 06-01: Cost tracking service with token counting wrapper
- [ ] 06-02: Cost dashboard frontend with charts and export

### Phase 7: Platform Settings
**Goal**: Users can configure and validate platform connections through UI
**Depends on**: Phase 1 (PlatformConnection model, SecretStr security)
**Requirements**: SETT-01, SETT-02, SETT-03, SETT-04, SETT-05, SETT-06, SETT-07, SETT-08
**Success Criteria** (what must be TRUE):
  1. User views current Databricks/Fabric connection status
  2. User configures workspace settings and credentials through forms
  3. User tests connections with one-click and sees latency/status
  4. Credentials are stored securely (never displayed in full)
**Plans**: 2 plans

Plans:
- [ ] 07-01: Settings API (connection management, testing)
- [ ] 07-02: Settings UI forms and connection status display

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Infrastructure & Exception Handling | 0/4 | Complete    | 2026-02-22 |
| 2. Chatbot | 0/2 | Not started | - |
| 3. Logging | 0/2 | Not started | - |
| 4. Code Editor | 0/2 | Not started | - |
| 5. Agent Control | 0/2 | Not started | - |
| 6. Cost Management | 0/2 | Not started | - |
| 7. Platform Settings | 0/2 | Not started | - |

---
*Roadmap created: 2026-02-22*
