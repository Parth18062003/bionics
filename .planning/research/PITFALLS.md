# Pitfalls Research

**Domain:** AADAP Enhancements — Adding UX/Control Features to AI Agent Platform
**Researched:** 2026-02-22
**Confidence:** HIGH (verified with multiple sources, official docs, and real-world case studies)

---

## Critical Pitfalls

### Pitfall 1: Chatbot-First Thinking for Technical Requirements

**What goes wrong:**
Developers assume a chatbot can replace all forms of input. Users struggle to express complex technical requirements through free-form text. The LLM extracts inconsistent structured data, omits fields, or hallucinates requirements the user never mentioned.

**Why it happens:**
LLMs excel at conversation but are unreliable at structured extraction without guardrails. A study analyzing LLM extraction workflows found that models "omit facts in random places" and "fields extracted did not align with the schema." Users expect conversational interfaces to "just understand" but technical requirements have implicit constraints that aren't verbalized.

**How to avoid:**
1. **Hybrid approach:** Combine conversation with structured form elements. Use the chatbot to clarify, not collect everything.
2. **Multi-pass validation:** After extraction, show the structured requirements back to the user for confirmation before creating the task.
3. **Schema enforcement:** Use tools like instructor or Pydantic to enforce output schemas — don't rely on prompt engineering alone.
4. **Explicit acknowledgment:** Make the bot repeat back key requirements: "You want a PySpark job that reads from table X, transforms Y, and writes to Z. Correct?"

**Warning signs:**
- Users repeat themselves multiple times in a conversation
- Tasks created have missing required fields
- High rate of task cancellations after creation
- Users say "that's not what I meant" after task execution starts

**Phase to address:** Chatbot Feature Phase

---

### Pitfall 2: Real-Time Logging via WebSocket Overkill

**What goes wrong:**
Teams default to WebSockets for all real-time features. Connection management becomes complex. Memory leaks accumulate. The system struggles with thousands of concurrent connections. Debugging is a nightmare.

**Why it happens:**
The WebSocket assumption is deeply ingrained. But research shows that "95% of real-time applications only need server → client updates." WebSockets provide bidirectional communication but come with "complexity, resource overhead, scaling challenges, debugging nightmares." For log streaming, SSE (Server-Sent Events) is sufficient and far simpler.

**How to avoid:**
1. **Use SSE for log streaming:** Logs flow server → client only. SSE handles this elegantly with automatic reconnection.
2. **Implement backpressure handling:** When the client can't keep up, don't buffer infinitely — drop older logs or pause the stream.
3. **Add pagination fallback:** If SSE fails or for historical logs, ensure the UI can fall back to paginated HTTP requests.
4. **Virtual scrolling for log viewer:** Never render all logs in DOM. Use virtualization (react-virtualized, tanstack-virtual).

**Warning signs:**
- Memory usage grows over time in the browser
- Connection drops require page refresh to recover
- Log viewer freezes with large volumes
- WebSocket connections pile up without cleanup

**Phase to address:** Logging System Phase

---

### Pitfall 3: Monaco Editor Bundle Bloat

**What goes wrong:**
Monaco Editor (5-10MB uncompressed) is added to the bundle without lazy loading. Initial page load time balloons. Users on slow connections abandon the page. The editor loads before it's needed.

**Why it happens:**
Monaco is feature-rich but heavy. CodeMirror 6 is ~300KB for comparable basic functionality. Teams don't realize the impact until they see production metrics. One Reddit comment: "My team has been struggling with Monaco for a while... it's very difficult to fit into a web application, not least because of the size."

**How to avoid:**
1. **Lazy load the editor:** Only load Monaco when the code view is opened. Use `next/dynamic` with `{ ssr: false }`.
2. **Consider CodeMirror for basic needs:** If you only need syntax highlighting and basic editing, CodeMirror 6 is much lighter.
3. **Measure bundle impact:** Set a bundle size budget and enforce it in CI.
4. **Preload on interaction hint:** When a user hovers over "View Code", preload the editor without blocking.

**Warning signs:**
- Lighthouse performance score drops significantly
- First Contentful Paint exceeds 3 seconds
- Users report "page is slow" when opening task detail
- DevTools shows Monaco as the largest bundle chunk

**Phase to address:** Code Editor Phase

---

### Pitfall 4: Agent Dashboard as a Black Box

**What goes wrong:**
The dashboard shows agent status (idle/busy) but no insight into what agents are actually doing. When an agent fails, there's no way to trace the decision path. Users trust the system less because they can't see the reasoning.

**Why it happens:**
Traditional APM tools don't work for AI agents. Agent observability requires "traces, metrics, prompts, tool calls, model outputs, evaluator scores, and human feedback in real time." Research found that "AI agents present unique diagnostic challenges due to their non-deterministic behavior." A 2026 analysis of 847 AI agent deployments found that 76% failed, often due to lack of observability.

**How to avoid:**
1. **Capture reasoning traces:** Log every agent decision, not just input/output. Include the "why" behind choices.
2. **Show tool calls in real-time:** Display when agents call Databricks SDK, what parameters were used, and what was returned.
3. **Link to conversation context:** For conversational tasks, show which part of the user's requirement triggered each agent action.
4. **Add manual intervention points:** Allow users to pause agents mid-task and inspect current state.

**Warning signs:**
- "Why did the agent do that?" is a frequent user question
- Support tickets about agent behavior can't be diagnosed
- Agents fail silently without clear error messages
- No correlation between user input and agent output

**Phase to address:** Agent Control Panel Phase

---

### Pitfall 5: Token Cost Underestimation by 40-60%

**What goes wrong:**
LLM API costs explode unexpectedly. A $500/month experiment becomes $15,000/month in production. The platform becomes economically unviable. Users have no visibility into costs until the bill arrives.

**Why it happens:**
"Most people underestimate their AI API costs by 40-60%." Hidden costs include: system prompts re-sent on every call (a 2,000-token system prompt = $180/month at scale), conversation history growing linearly, tool definitions adding 300-700 hidden tokens per request, and reasoning tokens billed as output but invisible in responses.

**How to avoid:**
1. **Track tokens per task/agent:** Every LLM call must log input tokens, output tokens, and calculated cost.
2. **Show cost estimates upfront:** Before a task runs, estimate token usage and cost based on similar historical tasks.
3. **Set per-task and daily budgets:** Hard limits that prevent runaway costs.
4. **Separate input/output tracking:** Different rates apply. Azure OpenAI charges differently for each.
5. **Implement semantic caching:** Cache similar prompt responses to avoid redundant LLM calls.

**Warning signs:**
- Monthly LLM bill surprises the team
- No correlation between usage and bill
- Users can't see cost impact of their requests
- Cost spikes correlate with specific task types but root cause is unknown

**Phase to address:** Cost Management Phase

---

### Pitfall 6: Configuration UI Leaks Secrets

**What goes wrong:**
The settings page displays API keys in plain text. Secrets are logged when connections fail. Credential rotation isn't possible without redeploying. The configuration is stored in plaintext in the database.

**Why it happens:**
The existing codebase already has hardcoded credentials in `config.py` and `.env.example`. The CONCERNS.md notes "Actual credentials embedded in code" and "Potential secret leakage if SecretStr values are logged directly." Building a UI on top of this without fixing the foundation compounds the problem.

**How to avoid:**
1. **Never display full secrets:** Show only the last 4 characters: `sk-****abcd`. Provide a "reveal" button that requires re-authentication.
2. **Use SecretStr consistently:** Ensure all secret fields use Pydantic's SecretStr type throughout the stack.
3. **Separate config from secrets:** Non-sensitive settings in database, secrets in Azure Key Vault or equivalent.
4. **Audit logging for secret access:** Log who accessed which secret, when, and from where.
5. **Rotation-first design:** Every secret should have a "rotate" action that doesn't require redeployment.

**Warning signs:**
- Full API keys visible in browser dev tools
- Secrets appear in error logs
- "Can we just hardcode this?" becomes a common request
- No audit trail for credential changes

**Phase to address:** Configuration Management Phase

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems for AADAP enhancements.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Polling instead of SSE for logs | Faster to implement, no connection management | Unnecessary API load, poor UX, scales poorly | MVP only, replace before 10 concurrent users |
| Store full conversation in memory | Simple context management | Memory leaks, lost on restart, no history | Never — use database from day 1 |
| Skip token counting for first iteration | Faster feature delivery | Invisible cost explosion, no budget enforcement | Only with hard cost caps in Azure OpenAI |
| Monaco everywhere, always loaded | Consistent editing experience | 10MB+ bundle per page, terrible performance | Never — lazy load or use CodeMirror for simple cases |
| Store secrets in database without encryption | Simpler schema, faster queries | Security breach waiting to happen | Never |
| Skip structured extraction validation | Trust LLM output | Inconsistent task data, silent failures, debugging nightmare | Never — Pydantic/instructor is non-negotiable |

---

## Integration Gotchas

Common mistakes when connecting new features to existing AADAP infrastructure.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Chatbot → Task Creation | LLM output goes directly to task model without validation | Multi-step: LLM → Pydantic validation → User confirmation → Task model |
| Log Viewer → Database | Unbounded queries for historical logs | Cursor-based pagination with enforced limits (max 1000 logs per request) |
| Code Editor → Artifact Model | Edit overwrites original artifact | Version artifacts: original (v1), edited (v2), with diff stored |
| Agent Dashboard → Orchestrator | Dashboard pulls state via polling | Push state changes via event bus; dashboard subscribes |
| Cost Tracking → LLM Client | Costs calculated after the fact from logs | Wrap LLM client with token counter that logs before/after every call |
| Config UI → Databricks/Fabric | Test connection uses production credentials | Provide "sandbox" test endpoints that don't touch real resources |

---

## Performance Traps

Patterns that work at small scale but fail as AADAP usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| In-memory log buffer | Logs lost on restart, memory grows unbounded | Write logs to database immediately, stream from DB via SSE | 1000+ logs or any restart |
| Single LLM client instance | Rate limiting, no per-task isolation | Connection pool with per-task/client tracking | 10+ concurrent tasks |
| Frontend polling for agent status | API overwhelmed, stale data | SSE/WebSocket for status push, poll only as fallback | 50+ simultaneous users |
| No pagination on log API | Frontend crashes loading large datasets | Cursor-based pagination, enforce max per request | 1000+ logs in single query |
| Synchronous credential test | UI freezes during connection test | Async test with loading state and timeout | 5+ second connection tests |
| Chatbot context in URL | Long URLs break, can't be shared | Store conversation in database, URL has conversation ID only | 10+ messages in conversation |

---

## Security Mistakes

Domain-specific security issues for AI agent platforms with UX enhancements.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Logging LLM prompts/responses with secrets | Secrets leaked to log aggregation system | Scrub SecretStr values before logging; use correlation IDs without context |
| Code editor allows arbitrary code execution | Malicious user injects code that runs in production | Sandboxed preview only; actual execution requires approval flow |
| Chatbot stores user input without sanitization | XSS, SQL injection via JSONB metadata | Validate/sanitize all chatbot input before storage |
| Config UI doesn't validate connection strings | SSRF via malicious Databricks workspace URL | Whitelist allowed domains, validate URL format |
| Cost tracking shows per-user costs to all users | Information disclosure, competitive disadvantage | Role-based access to cost data; users see their own costs only |
| Agent dashboard exposes internal agent prompts | Prompt injection attack surface, IP exposure | Show decisions/outcomes, not full prompts; sanitize any displayed prompt content |

---

## UX Pitfalls

Common user experience mistakes in AI agent platform interfaces.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Chatbot says "I didn't understand" without guidance | User stuck, doesn't know how to proceed | Offer specific clarification questions: "Which table should the job read from?" |
| Log viewer shows raw JSON | Users can't find relevant information | Parse and format logs by type; highlight errors; allow filtering by agent/level |
| Code editor requires manual refresh for updates | User edits stale code, conflicts on save | Lock editor during task execution; auto-refresh with conflict warning |
| Agent status only shows "busy" | User doesn't know what's taking so long | Show current action: "Generating PySpark code... (step 3/5)" |
| Cost dashboard shows daily totals only | User can't identify expensive tasks | Per-task cost breakdown with drill-down; alert thresholds |
| Config UI has no test connection | User saves broken configuration, tasks fail | "Test Connection" button that validates before save |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Chatbot:** Often missing confirmation step before task creation — verify user can review/modify extracted requirements
- [ ] **Chatbot:** Often missing conversation history persistence — verify reload preserves context
- [ ] **Log Viewer:** Often missing correlation ID linking — verify can trace single task's logs across all components
- [ ] **Log Viewer:** Often missing log level filtering — verify can filter by ERROR, WARN, INFO, DEBUG
- [ ] **Code Editor:** Often missing unsaved changes warning — verify navigating away prompts to save
- [ ] **Code Editor:** Often missing version history — verify can view previous artifact versions
- [ ] **Agent Dashboard:** Often missing real-time updates — verify status changes without manual refresh
- [ ] **Agent Dashboard:** Often missing pause/resume functionality — verify can pause a running agent
- [ ] **Cost Dashboard:** Often missing export functionality — verify can download CSV of cost data
- [ ] **Cost Dashboard:** Often missing budget alerts — verify email/notification when threshold exceeded
- [ ] **Config UI:** Often missing credential rotation — verify can change password/key without redeployment
- [ ] **Config UI:** Often missing connection timeout handling — verify handles slow/unreachable endpoints gracefully

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Chatbot creating invalid tasks | MEDIUM | Add validation layer; migrate existing bad tasks to "needs review" state; user re-confirms |
| Log viewer memory leak | LOW | Clear buffer on navigation away; add manual refresh; implement virtual scrolling |
| Monaco killing page performance | MEDIUM | Lazy load immediately; add loading skeleton; consider CodeMirror migration for affected pages |
| Agent dashboard not showing failures | HIGH | Add failure logging to agents; backfill historical failures; create failure alert system |
| Token costs exploding | HIGH | Implement immediate cost caps; audit all LLM calls; add semantic caching |
| Secrets leaked in logs | HIGH | Rotate all exposed credentials; scrub log storage; add secret detection to CI |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Chatbot extraction failures | Chatbot Feature | Unit tests with edge cases; user confirmation required before task creation |
| SSE/WebSocket issues | Logging System | Load test with 100+ concurrent streams; memory leak detection |
| Monaco bundle bloat | Code Editor | Bundle size budget in CI (<100KB for initial load) |
| Agent observability gaps | Agent Control Panel | Can trace full decision path for any task |
| Token cost explosion | Cost Management | Per-task cost capped; daily budget enforced; alerts working |
| Secret exposure | Configuration Management | No secrets in logs; UI masks credentials; rotation works |

---

## Existing Codebase Concerns Integration

These pitfalls compound with existing issues documented in CONCERNS.md:

| Existing Concern | Compounds Pitfall | Mitigation Priority |
|------------------|-------------------|---------------------|
| 78 bare exception handlers | Agent observability gaps (failures swallowed silently) | HIGH — fix before agent dashboard |
| Sync wrappers in async code | Real-time logging performance | HIGH — standardize on async before SSE |
| In-memory working memory | Chatbot context loss on restart | MEDIUM — use database for chat history |
| Approval engine memory cache | Cost tracking accuracy | MEDIUM — ensure cost data is persisted, not cached |
| Hardcoded database credentials | Config UI security | CRITICAL — fix before building config UI |
| Polling every 3 seconds | Real-time dashboard load | MEDIUM — migrate to push-based updates |

---

## Sources

- Botpress: "24 Chatbot Best Practices You Can't Afford to Miss in 2026" — https://botpress.com/blog/chatbot-best-practices
- DEV Community: "Server-Sent Events Beat WebSockets for 95% of Real-Time Apps" — https://dev.to/polliog/server-sent-events-beat-websockets-for-95-of-real-time-apps-heres-why-a4l
- Pranshu Raj: "Scaling Server Sent Events - 28,000+ concurrent connections" — https://blog.pranshu-raj.me/posts/exploring-sse/
- Jeffrey Hicks: "CodeMirror vs Monaco Editor: A Comprehensive Comparison" — https://agenthicks.com/research/codemirror-vs-monaco-editor-comparison
- Maxim AI: "Agent Observability: The Definitive Guide" — https://getmaxim.ai/articles/agent-observability-the-definitive-guide
- Neural Minimalist: "I Analyzed 847 AI Agent Deployments in 2026. 76% Failed." — https://medium.com/@neurominimal/i-analyzed-847-ai-agent-deployments-in-2026-76-failed-heres-why
- InsiderLLM: "Token Audit Guide: Track What AI Actually Costs You" — https://insiderllm.com/guides/token-audit-guide/
- SOO Group: "The Hidden Cost of LLM APIs: Token Economics Framework" — https://thesoogroup.com/blog/hidden-cost-of-llm-apis-token-economics
- Entro Security: "Pitfalls and Challenges in Secrets Management" — https://entro.security/blog/pitfalls-and-challenges-in-secrets-management/
- Kubernetes: "Good practices for Kubernetes Secrets" — https://kubernetes.io/docs/concepts/security/secrets-good-practices
- Forgent AI: "Beyond the Hype: Lessons Learned from Building an LLM-based Extraction MVP" — https://medium.com/@hello_26508/beyond-the-hype-lessons-learned-from-building-an-llm-based-extraction-mvp
- Smashing Magazine: "UX Strategies For Real-Time Dashboards" — https://www.smashingmagazine.com/2025/09/ux-strategies-real-time-dashboards/
- Existing codebase: `.planning/codebase/CONCERNS.md` — Known issues in AADAP platform

---

*Pitfalls research for: AADAP Enhancements (Chatbot, Logging, Code Editor, Agent Dashboard, Cost Tracking, Config UI)*
*Researched: 2026-02-22*
