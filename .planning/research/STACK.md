# Stack Research

**Domain:** AADAP Platform Enhancements (Multi-Agent AI Platform)
**Researched:** 2026-02-22
**Confidence:** HIGH

## Recommended Stack

This research covers new technologies needed to implement 6 feature areas on top of the existing AADAP stack (Next.js 16 + React 19 + FastAPI + LangGraph).

---

## Feature 1: Task Creation Chatbot

Conversational UI for requirement gathering with back-and-forth dialogue.

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **@assistant-ui/react** | 0.12.x | AI chat component library | Purpose-built for AI chat interfaces with LangGraph integration, streaming support, auto-scrolling, and shadcn/ui compatibility. 250K+ weekly downloads, Y Combinator backed. |
| **@assistant-ui/react-langgraph** | 0.12.x | LangGraph backend adapter | First-class LangGraph integration for connecting chat UI to existing orchestrator |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| @assistant-ui/react-markdown | 0.12.x | Markdown rendering in messages | For rich text responses with code blocks |
| @streamdown/code | latest | Syntax highlighting plugin | If you need code highlighting in chat |

### Integration Notes
- Built on Radix UI primitives (same foundation as shadcn/ui)
- Has built-in LangGraph adapter — connects directly to existing backend
- Supports streaming responses via SSE or custom protocols
- Works with React 19 and Next.js 16 App Router

### What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Stream Chat React | SaaS-only, external service dependency | @assistant-ui/react (self-hosted) |
| ChatScope | Generic chat, no AI/LLM-specific features | @assistant-ui/react (AI-native) |
| Building from scratch | Chat UI has complex edge cases (auto-scroll, streaming, accessibility) | @assistant-ui/react |

---

## Feature 2: Task Logging System

Real-time logs, filtering, and search for agent actions and decisions.

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **@melloware/react-logviewer** | 5.x | Virtualized log viewer | Handles 100MB+ files without crashing, ANSI highlighting, WebSocket streaming, built on react-window |
| **@tanstack/react-query** | 5.x | Polling and cache management | Already in stack — use for polling-based log updates |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| ansiparse | bundled | ANSI escape parsing | Included with react-logviewer |
| react-window | bundled | Virtual scrolling | Handles thousands of log lines efficiently |

### Integration Notes
- Use `ScrollFollow` HOC for auto-following logs (pauses when user scrolls up)
- Supports URL, WebSocket, and static text sources
- Line highlighting for search results
- Custom styling via CSS modules or Tailwind

### What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Plain `<pre>` with scrolling | No virtualization, crashes on large logs | @melloware/react-logviewer |
| PatternFly react-log-viewer | Red Hat ecosystem lock-in, heavier | @melloware/react-logviewer |
| Custom virtualization | Reinventing complex wheel | @melloware/react-logviewer |

---

## Feature 3: Code Editor

Syntax highlighting, diff view, and code editing for generated artifacts.

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **@monaco-editor/react** | 4.7.x | Monaco Editor wrapper | VS Code editor in browser, diff view built-in, Python/PySpark syntax highlighting, React 19 support |

### Integration Notes
```tsx
import { Editor, DiffEditor } from '@monaco-editor/react';

// Single editor with Python highlighting
<Editor
  height="60vh"
  defaultLanguage="python"
  theme="vs-dark"
  options={{ minimap: { enabled: false } }}
/>

// Diff view for comparing versions
<DiffEditor
  height="60vh"
  language="python"
  original={originalCode}
  modified={modifiedCode}
/>
```

### Next.js Integration
Monaco requires dynamic import in Next.js:
```tsx
import dynamic from 'next/dynamic';

const Editor = dynamic(() => import('@monaco-editor/react').then(mod => mod.Editor), { ssr: false });
```

### What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| CodeMirror | More setup, diff requires separate package | @monaco-editor/react (diff built-in) |
| Ace Editor | Less maintained, weaker TypeScript support | @monaco-editor/react |
| Simple textarea | No syntax highlighting, no diff | @monaco-editor/react |

---

## Feature 4: Agent Control Panel

Status display, pause/resume controls, queue management.

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **@tanstack/react-query** | 5.x | Polling for real-time updates | Already likely in stack — use `refetchInterval` for status polling |
| **shadcn/ui components** | latest | UI primitives (Badge, Card, Button) | Matches existing Tailwind stack |

### Polling Pattern
```tsx
const { data: agentStatus } = useQuery({
  queryKey: ['agent-status', agentId],
  queryFn: () => fetchAgentStatus(agentId),
  refetchInterval: 2000, // Poll every 2 seconds
  refetchIntervalInBackground: false, // Pause when tab hidden
});
```

### Real-time Strategy (Recommended)
- **Phase 1:** Polling with TanStack Query (simpler, works with existing infrastructure)
- **Future:** WebSocket upgrade path available if polling becomes insufficient

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| lucide-react | latest | Icons for status indicators | Status badges, action buttons |
| framer-motion | 11.x | Animations for state transitions | If smooth UI transitions needed |

### What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| WebSocket for phase 1 | Additional infrastructure, complexity | Polling (upgrade later if needed) |
| Server-Sent Events | Unidirectional, requires FastAPI setup | Polling (simpler for control panel) |
| Global state for status | Server is source of truth | TanStack Query with polling |

---

## Feature 5: Cost Management Dashboard

LLM + platform cost tracking, charts, and alerts.

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **recharts** | 2.x | React charting library | React-native declarative API, SVG-based, good performance, most popular (3.6M+ weekly downloads) |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| lucide-react | latest | Icons for dashboard | Chart labels, UI icons |
| date-fns | 3.x | Date manipulation | For time-based filtering |

### Chart Types for Cost Dashboard
```tsx
import { LineChart, AreaChart, BarChart, PieChart, ResponsiveContainer } from 'recharts';

// Daily cost trend
<ResponsiveContainer width="100%" height={300}>
  <AreaChart data={dailyCosts}>
    <XAxis dataKey="date" />
    <YAxis />
    <Tooltip />
    <Area type="monotone" dataKey="cost" stroke="#8884d8" fill="#8884d8" fillOpacity={0.3} />
  </AreaChart>
</ResponsiveContainer>

// Cost by agent (pie)
<ResponsiveContainer width="100%" height={300}>
  <PieChart>
    <Pie data={agentCosts} dataKey="cost" nameKey="agent" cx="50%" cy="50%" outerRadius={80} />
    <Tooltip />
  </PieChart>
</ResponsiveContainer>
```

### What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Chart.js / react-chartjs-2 | Canvas-based, less React-native | recharts (SVG, declarative) |
| D3.js directly | Steep learning curve, verbose | recharts (D3 under the hood) |
| ApexCharts | Larger bundle, less React-idiomatic | recharts |

---

## Feature 6: Platform Settings

Databricks/Fabric connection management, credential handling.

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **react-hook-form** | 7.x | Form state management | Minimal re-renders, excellent TypeScript support, most popular form library |
| **zod** | 3.x | Schema validation | TypeScript-first, type inference, share schemas with backend |
| **@hookform/resolvers** | 3.x | Zod resolver for RHF | Bridges Zod schemas to react-hook-form |

### Form Pattern
```tsx
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

const databricksSchema = z.object({
  workspaceUrl: z.string().url('Invalid URL'),
  token: z.string().min(1, 'Token is required'),
  clusterId: z.string().optional(),
});

type DatabricksConfig = z.infer<typeof databricksSchema>;

function DatabricksSettingsForm() {
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<DatabricksConfig>({
    resolver: zodResolver(databricksSchema),
  });

  // ... form rendering
}
```

### What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Formik | More re-renders, larger bundle | react-hook-form |
| Controlled inputs without library | Manual state management, validation complexity | react-hook-form + zod |
| Yup | Less TypeScript-native than Zod | Zod |

---

## Shared Infrastructure

### Real-time Updates Strategy

| Scenario | Recommended Approach | Rationale |
|----------|---------------------|-----------|
| Agent status (control panel) | Polling 2-5s interval | Low frequency, simple implementation |
| Task logs | Polling 1s OR WebSocket | Higher frequency needs, start with polling |
| Chat messages | SSE streaming | Already required for LLM streaming |

### UI Component Library

**Recommendation: shadcn/ui** (matches existing Tailwind CSS)

The existing AADAP stack uses Tailwind CSS. shadcn/ui provides:
- Copy-paste components (not npm dependency)
- Radix UI primitives for accessibility
- Tailwind styling out of the box
- Full control over component code

### shadcn Components to Add

```bash
npx shadcn@latest add badge card button input label tabs dialog sheet form select
```

---

## Installation Summary

```bash
# Frontend (in /frontend directory)

# Chat UI (Feature 1)
npm install @assistant-ui/react @assistant-ui/react-langgraph

# Log Viewer (Feature 2)
npm install @melloware/react-logviewer

# Code Editor (Feature 3)
npm install @monaco-editor/react

# Charts (Feature 5)
npm install recharts

# Forms (Feature 6)
npm install react-hook-form zod @hookform/resolvers

# Query (if not already present)
npm install @tanstack/react-query

# shadcn components
npx shadcn@latest add badge card button input label tabs dialog sheet form select
```

---

## Version Compatibility Matrix

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| @assistant-ui/react 0.12.x | React 19, Next.js 16 | v4.7.0-rc.0 for React 19 |
| @monaco-editor/react 4.7.x | React 19, Next.js 16 | Requires dynamic import for SSR |
| @tanstack/react-query 5.x | React 18+ | Works with React 19 |
| recharts 2.x | React 18+ | Works with React 19 |
| react-hook-form 7.x | React 18+ | Works with React 19 |

---

## Backend Considerations

### New FastAPI Endpoints Needed

| Endpoint | Method | Purpose | Feature |
|----------|--------|---------|---------|
| `/api/chat/task` | POST | Streaming chat for task creation | Chatbot |
| `/api/tasks/{id}/logs` | GET | Paginated/filtered logs | Logging |
| `/api/tasks/{id}/logs/stream` | GET | WebSocket log streaming | Logging |
| `/api/agents` | GET | List all agents with status | Control Panel |
| `/api/agents/{id}/pause` | POST | Pause agent | Control Panel |
| `/api/agents/{id}/resume` | POST | Resume agent | Control Panel |
| `/api/costs/summary` | GET | Cost aggregation by period | Dashboard |
| `/api/costs/by-agent` | GET | Cost breakdown per agent | Dashboard |
| `/api/settings/databricks` | GET/PUT | Databricks connection config | Settings |
| `/api/settings/fabric` | GET/PUT | Fabric connection config | Settings |
| `/api/settings/databricks/test` | POST | Test Databricks connection | Settings |
| `/api/settings/fabric/test` | POST | Test Fabric connection | Settings |

---

## Sources

- **@assistant-ui/react** — npmjs.com/package/@assistant-ui/react (v0.12.10, Feb 2026)
- **@monaco-editor/react** — npmjs.com/package/@monaco-editor/react (v4.7.0)
- **@tanstack/react-query** — npmjs.com/package/@tanstack/react-query (v5.76.x, Feb 2026)
- **@melloware/react-logviewer** — github.com/melloware/react-logviewer (v5.x)
- **recharts** — recharts.org, npmjs.com/package/recharts (v2.x, 3.6M weekly downloads)
- **react-hook-form** — react-hook-form.com (v7.x)
- **zod** — zod.dev (v3.x)
- **shadcn/ui** — ui.shadcn.com

---

*Stack research for: AADAP Platform Enhancements*
*Researched: 2026-02-22*
