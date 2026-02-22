# Project Research Summary

**Project:** AADAP Platform Enhancements
**Domain:** Multi-Agent AI Platform (UX/Control Features)
**Researched:** 2026-02-22
**Confidence:** HIGH

## Executive Summary

This project adds 6 user-facing features to an existing AI agent platform (AADAP): a conversational task creation chatbot, real-time logging system, code editor with diff view, agent control panel, cost management dashboard, and platform settings UI. Research across stack, features, architecture, and pitfalls shows a clear path forward with established libraries and well-documented patterns.

The recommended approach is incremental enhancement of the existing Next.js 16 + FastAPI + LangGraph stack, using specialized libraries for each feature (@assistant-ui/react for chat, @melloware/react-logviewer for logs, Monaco for code editing, recharts for cost visualization). Avoid WebSocket over-engineering—SSE for chat streaming and polling (1-5s intervals) for logs/status are sufficient and simpler.

Key risks center on LLM cost explosion (users underestimate by 40-60%), chatbot extraction reliability (models omit fields randomly without schema enforcement), and security (existing codebase has hardcoded credentials that must be addressed before building config UI). Each phase must include specific safeguards: Pydantic/instructor for extraction validation, token tracking wrappers for cost control, and SecretStr + credential rotation for security.

## Key Findings

### Recommended Stack

Six feature areas each have targeted libraries that integrate with the existing Tailwind + shadcn/ui stack. All choices prioritize React 19/Next.js 16 compatibility and avoid SaaS lock-in.

**Core technologies:**
- **@assistant-ui/react 0.12.x** — AI chat component library with built-in LangGraph adapter, streaming support, and Radix UI primitives
- **@melloware/react-logviewer 5.x** — Virtualized log viewer handling 100MB+ files with ANSI highlighting and WebSocket/SSE streaming
- **@monaco-editor/react 4.7.x** — VS Code editor in browser with built-in diff view; requires dynamic import in Next.js
- **recharts 2.x** — Declarative React charting (3.6M weekly downloads) for cost dashboards
- **react-hook-form 7.x + zod 3.x** — Form state management with TypeScript-first schema validation
- **@tanstack/react-query 5.x** — Polling-based real-time updates with `refetchInterval` for agent status and logs

### Expected Features

Research identified 10 table stakes features (users assume these exist), 12 differentiators (competitive advantage), and 6 anti-features (commonly requested but problematic).

**Must have (table stakes):**
- Natural language input — basic text interaction with submit button
- Real-time log streaming — sub-second latency via SSE or polling
- Syntax highlighting — Python/PySpark focus using Monaco
- Timestamped log entries with correlation IDs — debugging traceability
- Agent status indicators — Idle/Busy/Error states
- Cost per request display — token count × price calculation
- Connection test buttons — validate Databricks/Fabric connectivity
- Filter/search in logs — essential for large log volumes
- Diff view for code changes — side-by-side comparison
- Task list with status — basic task management

**Should have (differentiators):**
- Structured requirement extraction — LLM parses natural language into formal specs
- Multi-turn requirement clarification — guides users to complete specifications
- Cost attribution by task/agent — connects spend to business outcomes
- Agent trace visualization — tree/graph view of agent reasoning chains
- Connection health dashboard — proactive monitoring of platform connectivity

**Defer (v2+):**
- Agent health scoring — requires historical data collection
- Cost forecasting — needs baseline usage data
- Semantic code diffs — tree-sitter integration, nice-to-have
- Custom agent creation UI — increases scope dramatically

### Architecture Approach

The architecture extends the existing 6-layer AADAP stack (L1 Infrastructure → L6 Presentation) with new components in the presentation and orchestration layers. New database models (TaskLog, CostRecord, PlatformConnection) integrate with existing PostgreSQL.

**Major components:**
1. **ChatService (L5)** — Streaming chat endpoint with SSE, requirement extraction, integration with existing orchestrator
2. **LogService (L5)** — Paginated log retrieval, SSE streaming, correlation by task ID
3. **TokenTracker (L3)** — Wraps LLM client to count tokens before/after every call, persists costs
4. **Frontend pages (L6)** — Dedicated pages for chat, logs, agents, costs, settings plus embedded components

### Critical Pitfalls

1. **Chatbot extraction failures** — LLMs omit fields randomly without schema enforcement. Use Pydantic/instructor for output validation, show extracted requirements for user confirmation before task creation.

2. **WebSocket overkill** — 95% of real-time apps only need server→client updates. Use SSE for logs, polling for agent status. WebSocket complexity only if SSE proves insufficient.

3. **Monaco bundle bloat** — Monaco is 5-10MB uncompressed. Lazy load with `next/dynamic` + `{ ssr: false }`. Consider CodeMirror for simple cases.

4. **Token cost explosion** — Costs underestimated by 40-60%. Wrap LLM client with token counter, set per-task and daily budgets, implement semantic caching.

5. **Configuration UI leaks secrets** — Existing codebase has hardcoded credentials. Fix foundation before building UI. Use SecretStr throughout, never display full secrets (show last 4 chars only), implement rotation workflow.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Infrastructure Foundation
**Rationale:** Database models and migrations must exist before frontend can consume data. Existing hardcoded credentials must be addressed before settings UI.
**Delivers:** TaskLog, CostRecord, PlatformConnection models; Alembic migration; SecretStr migration for existing credentials
**Addresses:** Table stakes data requirements
**Avoids:** Configuration UI leaks secrets (pitfall #6)

### Phase 2: Chatbot Feature
**Rationale:** Core interaction model for task creation. Depends on Phase 1 models. Sets the tone for user experience.
**Delivers:** Conversational task creation with structured extraction, requirement preview, confirmation flow
**Uses:** @assistant-ui/react, @assistant-ui/react-langgraph, SSE streaming
**Implements:** ChatService, ChatInterface, ChatPanel components
**Avoids:** Chatbot extraction failures (pitfall #1) via Pydantic validation + user confirmation

### Phase 3: Logging System
**Rationale:** Essential for debugging running agents. Depends on TaskLog model from Phase 1. Enables observability for later phases.
**Delivers:** Real-time log streaming, filtering, search, correlation by task ID
**Uses:** @melloware/react-logviewer, @tanstack/react-query (polling or SSE)
**Implements:** LogService, EmbeddedLogViewer, LogViewer page
**Avoids:** WebSocket overkill (pitfall #2), log everything to database (anti-pattern)

### Phase 4: Code Editor
**Rationale:** Enables viewing and editing generated artifacts. Depends on logging for debugging. Independent of other features.
**Delivers:** Monaco-based code viewing/editing, diff view between versions
**Uses:** @monaco-editor/react (lazy loaded)
**Implements:** Editor component, DiffEditor component, artifact version storage
**Avoids:** Monaco bundle bloat (pitfall #3) via dynamic import + SSR: false

### Phase 5: Agent Control Panel
**Rationale:** Users need visibility into agent status and control. Depends on logging for trace context. Enables trust in agent behavior.
**Delivers:** Agent status display, pause/resume controls, queue view, reasoning trace preview
**Uses:** @tanstack/react-query (polling), shadcn/ui components
**Implements:** Agents API, AgentCard, AgentQueue, AgentControls components
**Avoids:** Agent dashboard as black box (pitfall #4) via reasoning trace capture

### Phase 6: Cost Management
**Rationale:** Cost visibility is table stakes. Depends on TokenTracker from Phase 1. Must track from day 1 to prevent surprise bills.
**Delivers:** Per-task and per-agent cost tracking, dashboards, budget alerts, export
**Uses:** recharts, TokenTracker wrapper (Phase 1)
**Implements:** CostService, Costs API, CostChart components
**Avoids:** Token cost explosion (pitfall #5) via upfront tracking + budgets

### Phase 7: Platform Settings
**Rationale:** Configuration management for Databricks/Fabric. Depends on PlatformConnection model and security fixes from Phase 1.
**Delivers:** Connection config forms, test buttons, credential management, health monitoring
**Uses:** react-hook-form, zod, @hookform/resolvers
**Implements:** Settings API, DatabricksConfig, FabricConfig forms
**Avoids:** Configuration UI leaks secrets (pitfall #6) via SecretStr + rotation workflow

### Phase Ordering Rationale

- **Phase 1 first:** Database models and security foundation required by all other phases. Existing hardcoded credentials must be fixed before building settings UI.
- **Phase 2 second:** Chatbot is the primary interaction model; sets user experience tone. Depends on Phase 1 models.
- **Phase 3 third:** Logging enables debugging for all subsequent phases. Independent feature with high user value.
- **Phase 4 fourth:** Code editor is independent but benefits from logging for debugging.
- **Phase 5 fifth:** Agent control depends on logging for trace context. Enables trust and debugging.
- **Phase 6 sixth:** Cost tracking depends on TokenTracker from Phase 1. Must be implemented before usage scales.
- **Phase 7 last:** Settings UI requires security foundation from Phase 1. Users can survive with existing config until other features are ready.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2 (Chatbot):** Complex LLM integration, requirement extraction prompts need iteration, conversation history persistence strategy
- **Phase 5 (Agent Control):** LangGraph state introspection, agent pause/resume mechanics need investigation
- **Phase 7 (Settings):** Azure Key Vault or equivalent integration for production secrets management

Phases with standard patterns (skip research-phase):
- **Phase 1 (Infrastructure):** Standard Alembic patterns, well-documented SQLAlchemy models
- **Phase 3 (Logging):** SSE patterns well-documented, react-logviewer has clear API
- **Phase 4 (Code Editor):** Monaco integration patterns are standard, dynamic import is documented
- **Phase 6 (Cost Management):** Standard recharts usage, token tracking is straightforward

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All libraries verified via npm, official docs, and 2026 sources. Version compatibility confirmed with React 19/Next.js 16. |
| Features | HIGH | Verified with multiple 2026 sources including Cursor, Claude Code, Windsurf competitor analysis. Priorities validated against user expectations. |
| Architecture | HIGH | Integrates cleanly with existing AADAP 6-layer architecture. Patterns (SSE, polling, lazy loading) are well-documented best practices. |
| Pitfalls | HIGH | Each pitfall backed by multiple sources including real-world case studies. Prevention strategies are concrete and actionable. |

**Overall confidence:** HIGH

### Gaps to Address

- **LangGraph state introspection:** Agent pause/resume and queue management may require deeper investigation into LangGraph Platform APIs. Flag for Phase 5 research.
- **Conversation history persistence:** Chatbot needs database storage for multi-session context. Exact schema and retrieval strategy TBD during Phase 2 planning.
- **Secrets management backend:** Phase 1 fixes hardcoded credentials in code, but production secrets rotation may need Azure Key Vault integration. Flag for Phase 7 research if enterprise requirements emerge.

## Sources

### Primary (HIGH confidence)

- **@assistant-ui/react** — npmjs.com/package/@assistant-ui/react (v0.12.10, Feb 2026)
- **@monaco-editor/react** — npmjs.com/package/@monaco-editor/react (v4.7.0)
- **@tanstack/react-query** — npmjs.com/package/@tanstack/react-query (v5.76.x, Feb 2026)
- **recharts** — recharts.org, npmjs.com/package/recharts (v2.x, 3.6M weekly downloads)
- **react-hook-form** — react-hook-form.com (v7.x)
- **Microsoft Foundry: Agent Monitoring Dashboard** — learn.microsoft.com (official docs)
- **LangSmith Observability Platform** — langchain.com/langsmith/observability (official docs)

### Secondary (MEDIUM confidence)

- **Cursor vs Claude Code vs Windsurf: 2026 Guide** — ybuild.ai — Competitor feature analysis
- **5 Best AI Agent Observability Tools for 2026** — braintrust.dev — Observability patterns
- **Botpress: 24 Chatbot Best Practices 2026** — botpress.com/blog — Chatbot UX patterns
- **Server-Sent Events Beat WebSockets for 95% of Real-Time Apps** — dev.to — Real-time architecture decision
- **Token Audit Guide** — insiderllm.com — Cost tracking methodology
- **Hidden Cost of LLM APIs** — thesoogroup.com — Token economics

### Tertiary (LOW confidence)

- **I Analyzed 847 AI Agent Deployments in 2026. 76% Failed.** — medium.com/@neurominimal — Failure statistics
- **LLM-based Extraction MVP Lessons** — medium.com/@hello_26508 — Extraction validation challenges

---
*Research completed: 2026-02-22*
*Ready for roadmap: yes*
