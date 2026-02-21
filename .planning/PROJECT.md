# AADAP — Autonomous AI Developer Agents Platform

## What This Is

AADAP is a multi-agent AI platform that autonomously executes data engineering tasks across Azure Databricks (Python/PySpark) and Microsoft Fabric (Scala/Spark) environments. It replicates and exceeds the capabilities of a mid-level data engineer, orchestrated by a central agent that coordinates specialized sub-agents with mandatory human-in-the-loop safety controls.

The platform consists of a 6-layer architecture: Infrastructure, Operational Store, Integration, Agent Layer, Orchestration, and Presentation (Next.js frontend + FastAPI backend).

## Core Value

**Users submit natural language requirements and get validated, deployed code without writing any code themselves.**

If everything else fails, the core loop must work: requirement → parsing → planning → code generation → validation → approval → deployment.

## Requirements

### Validated

- ✓ 25-state task lifecycle machine (SUBMITTED → COMPLETED/CANCELLED) — Phase 2
- ✓ LangGraph orchestration with state persistence — Phase 2
- ✓ PostgreSQL database with Task, Artifact, ApprovalRequest, Execution models — Phase 1
- ✓ FastAPI REST API with task CRUD, approvals, artifacts endpoints — Phase 1
- ✓ Next.js frontend with task list, task detail, approval workflow pages — Phase 7
- ✓ Databricks integration (SDK client, notebook execution) — Phase 4
- ✓ Microsoft Fabric integration (REST API client) — Phase 4
- ✓ Base agent abstraction with lifecycle management — Phase 3
- ✓ DeveloperAgent, ValidationAgent, OptimizationAgent implementations — Phase 4
- ✓ Approval engine with autonomy policy matrix — Phase 5
- ✓ In-memory working memory store with TTL — Phase 6
- ✓ Structured logging with correlation IDs — Phase 1

### Active

**Exception Handling Fixes:**
- [ ] Replace bare `except Exception` handlers in core execution path with specific exception types
- [ ] Add proper logging to empty `pass` statements in exception handlers
- [ ] Standardize async/sync patterns (remove ThreadPoolExecutor sync wrappers)

**New Features - User Experience:**
- [ ] Task creation chatbot with back-and-forth conversation for requirement clarification
  - Dedicated chat page for focused task creation
  - Slide-out chat panel accessible from any page
  - LLM-powered conversation to extract structured requirements
- [ ] Detailed task logging system
  - Embedded logs in task detail page (real-time progress)
  - Dedicated log viewer with filtering, search, and export
  - Show agent actions, decisions, errors with timestamps and correlation IDs

**New Features - Control & Management:**
- [ ] Code editor for viewing and editing generated code before deployment
  - Syntax highlighting for Python/PySpark
  - Diff view comparing original vs edited code
  - Save edited code as new artifact version
- [ ] Agent control panel
  - View agent status (idle, busy, degraded)
  - Pause/resume individual agents
  - View agent task queue
  - Force task reassignment
- [ ] Cost management dashboard
  - Track LLM API costs per task, per agent, per time period
  - Track Databricks/Fabric compute costs
  - Cost alerts and budgets
  - Export cost reports
- [ ] Platform settings and configuration
  - Databricks workspace connection management
  - Microsoft Fabric workspace connection management
  - Test connections, view status
  - Credential management (create, rotate, delete)

### Out of Scope

- Phase 8 (Testing & Hardening) — deferred to future iteration
- Phase 9 (Production Readiness / CI/CD) — deferred to future iteration
- WebSocket real-time updates — will use polling optimization first, WebSocket in future
- Microsoft Fabric Scala/Spark agent — Phase 2+ scope, current work focuses on Python/Databricks

## Context

**Existing Architecture:**
- 6-layer monolithic architecture with clear separation of concerns
- Event-sourced state transitions with full audit trail
- Stateless agents coordinated by LangGraph orchestrator
- Human-in-the-loop approval gates for destructive operations

**Current State:**
- Core platform infrastructure is built and functional
- Frontend has basic task management and approval workflows
- Known tech debt: 78 bare exception handlers, 22+ empty pass statements
- Exception handling issues concentrated in orchestrator, agents, and services

**Technical Environment:**
- Backend: Python 3.11+, FastAPI, SQLAlchemy async, LangGraph
- Frontend: Next.js 16, React 19, TypeScript, Tailwind CSS
- Database: PostgreSQL 16 with pgvector
- LLM: Azure OpenAI (GPT-4o for orchestrator/developer, GPT-4o-mini for validation)
- Platforms: Azure Databricks, Microsoft Fabric

## Constraints

- **Tech Stack**: Must use existing Python backend and Next.js frontend
- **Database**: PostgreSQL with existing schema, cannot break migrations
- **LLM Provider**: Azure OpenAI (cannot switch providers)
- **Platform Support**: Databricks is primary, Fabric is secondary
- **No Destructive Bypass**: Safety gates must remain enforced
- **Backward Compatible**: Existing API contracts cannot break

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Focus on core execution path for exception fixes | Orchestrator and agents are where errors propagate to users; fixes here have highest impact | — Pending |
| Chatbot as both page and panel | Dedicated page for complex requirements; panel for quick interactions | — Pending |
| Embedded + dedicated log views | Quick glance during task monitoring; deep dive for debugging | — Pending |
| User experience features first | Foundation for user interaction before adding control features | — Pending |

---
*Last updated: 2026-02-22 after initialization*
