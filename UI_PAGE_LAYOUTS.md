# AADAP PAGE LAYOUTS — Specification

> Authoritative page-level layouts for the AADAP Control Plane.
> Phase 7 frontend MUST implement these layouts exactly.
> Cross-references: [DESIGN_SYSTEM.md](file:///c:/Users/parth/.gemini/antigravity/scratch/bionics/DESIGN_SYSTEM.md) · [INTERACTION_FLOWS.md](file:///c:/Users/parth/.gemini/antigravity/scratch/bionics/INTERACTION_FLOWS.md)
> Stitch project: `10373594301173479537`

---

## Global Shell

Every page shares a consistent outer shell. Page-specific content renders inside the **Main Content Area**.

```
┌─────────────────────────────────────────────────────────┐
│ TOP BAR (56px)                                          │
│  [AADAP logo]   [⌘K Search bar]   [🔔 3]  [Avatar]    │
├─────────────────────────────────────────────────────────┤
│ TAB NAV                                                 │
│  All Tasks · Pending Approval (4) · Failed · Completed  │
│  · System Health                                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  MAIN CONTENT AREA                                      │
│  (page-specific, scrollable)                            │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

| Element | Specification |
|---------|---------------|
| **Top bar** | 56px height, white, 1px `neutral-200` bottom border |
| Logo | "AADAP" · Inter SemiBold 16px · `neutral-900` |
| Search | Centered, 360px wide, `neutral-50` fill, placeholder "Search tasks, agents, artifacts…" · Cmd+K shortcut label |
| Notifications | Bell icon + count badge (`rose-600` fill if > 0) |
| User | Avatar circle (32px) + role caption below |
| **Tab nav** | Horizontal tabs directly below top bar, 44px height, `neutral-50` background |
| Active tab | `primary-500` underline (2px), `neutral-900` text |
| Inactive tab | No underline, `neutral-500` text |
| Badge on tab | Count in parentheses, amber text for "Pending Approval" |

**Layout grid**: 12-column, max-width 1440px, centered, `space-8` side margins, `space-6` gutter.

---

## Page 1 — Dashboard (Task List)

> **Stitch screen**: `3d6cd66ff8ff4647bbd6e5a295d44486`
> **Tab**: "All Tasks" active
> **Purpose**: Primary landing. See all tasks, filter by state, spot risks and pending approvals instantly.

### Layout

```
┌─────────────────────────────────────────────────────────┐
│ FILTER BAR (48px)                                       │
│  [ENV ▾] [RISK ▾] [STATUS ▾] [DATE ▾]   "Clear filters"│
│  [chip: PRODUCTION ✕] [chip: HIGH ✕]                    │
├─────────────────────────────────────────────────────────┤
│ TASK ROW  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  │
│ │ T-1847  Optimize Snowflake…  ●─●─●─○─○─○  HIGH PROD │ │
│  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  │
│ ▌T-1832  Deploy ETL pipeline…  ●─●─●─●─●─⚠  HIGH PROD │ │ ← amber border
│  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  │
│ │ T-1819  Create staging table… ●─●─✕─○─○─○  MED  SBOX │ │ ← rose border
│  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  │
│ │ ...more rows                                          │
├─────────────────────────────────────────────────────────┤
│ PAGINATION                              1 2 3 … 12  →  │
└─────────────────────────────────────────────────────────┘
```

### Sections

| Section | Grid Columns | Content |
|---------|-------------|---------|
| **Filter bar** | 12 cols | Segmented controls (Environment, Risk Level), multi-select dropdown (25 FSM states), date range picker. Active filters as dismissable chips below. |
| **Task rows** | 12 cols | One horizontal card per task. Clickable. |
| **Pagination** | 12 cols, right-aligned | Page numbers + prev/next. 25 rows per page default. |

### Task Row Anatomy (each row)

| Element | Grid Position | Font | Details |
|---------|--------------|------|---------|
| Task ID | cols 1–1.5 | JetBrains Mono 13px | e.g. "T-1847" |
| Description | cols 2–5 | Inter 14px, truncated | Single line, ellipsis |
| State stepper | cols 5.5–8 | — | 6 circles + lines, ~200px. See DESIGN_SYSTEM §6. |
| Current state label | below stepper | Inter 11px `neutral-500` | e.g. "IN_DEVELOPMENT" |
| Risk badge | col 9 | 12px pill | Color per DESIGN_SYSTEM §5.5 |
| Environment badge | col 10 | 12px pill | SANDBOX (slate) / PRODUCTION (rose outline) |
| Agent ID | col 11 | JetBrains Mono 12px | e.g. "dev-agent-07" |
| Timestamp | col 12 | Inter 12px `neutral-500` | Relative: "2h ago" |

### Left Border Accents

| Condition | Border |
|-----------|--------|
| State is `APPROVAL_PENDING` or `IN_REVIEW` | 2px amber-500 left border |
| State is `*_FAILED`, `REJECTED`, `CANCELLED` | 2px rose-500 left border |
| All other states | No left accent |

### Information Hierarchy
1. **Scan**: Left-border accents catch attention for approval/failure
2. **Identify**: Task ID + description
3. **Assess**: Stepper shows phase, risk + environment badges show stakes
4. **Act**: Click row to navigate to Task Detail

### States

| State | Behavior |
|-------|----------|
| **Loading** | 6 skeleton rows matching row anatomy. Shimmer animation. |
| **Empty (no tasks)** | Centered: "No tasks yet. Submit your first task to get started." + "Submit Task" primary button |
| **Empty (filters active)** | Centered: "No tasks match the current filters." + "Clear filters" ghost link |
| **Error** | Rose banner above list: "Unable to load tasks. [Retry]" |

---

## Page 2 — Task Submission

> **Stitch screen**: `4b00537e1c204cc7b1c7ff0c4ab009b9`
> **Route**: /tasks/new
> **Purpose**: Submit a new data engineering task in natural language.

### Layout

```
┌─────────────────────────────────────────────────────────┐
│ BREADCRUMB: All Tasks > Submit New Task                 │
├──────────────────────────────┬──────────────────────────┤
│ TASK INPUT (cols 1–7)        │ GOVERNANCE (cols 8–12)   │
│                              │                          │
│ ┌──────────────────────────┐ │ ┌────────────────────┐   │
│ │ Describe your task…      │ │ │ Governance Rules   │   │
│ │                          │ │ │                    │   │
│ │ (textarea, 200px min)    │ │ │ Autonomy matrix    │   │
│ │                          │ │ │ table (compact)    │   │
│ └──────────────────────────┘ │ │                    │   │
│                              │ │ "Your task will be │   │
│ Environment: ○SANDBOX ○PROD  │ │  parsed, planned…" │   │
│ Priority: [LOW|MED|HIGH|CRIT]│ │                    │   │
│ Tags: [ETL] [Snowflake] [+]  │ │ INV-01 notice      │   │
│                              │ └────────────────────┘   │
├──────────────────────────────┴──────────────────────────┤
│ FOOTER                                                  │
│  Est. budget: ~12,000 / 50,000   [Save Draft] [Submit]  │
├─────────────────────────────────────────────────────────┤
│ RECENT SUBMISSIONS (optional, collapsed by default)     │
│  Last 5 tasks table with status badges                  │
└─────────────────────────────────────────────────────────┘
```

### Sections

| Section | Grid Columns | Content |
|---------|-------------|---------|
| **Task input area** | cols 1–7 | Textarea + controls |
| **Governance panel** | cols 8–12 | Static info card, always visible |
| **Footer** | 12 cols | Token estimate (left), buttons (right) |
| **Recent submissions** | 12 cols | Collapsible table, last 5 tasks |

### Governance Panel Contents

| Row | Environment | Operation | Approval? |
|-----|-------------|-----------|-----------|
| 1 | SANDBOX | Read-only | Auto |
| 2 | SANDBOX | Write (non-destructive) | Auto |
| 3 | SANDBOX | Destructive | Required |
| 4 | PRODUCTION | Read-only | Auto |
| 5 | PRODUCTION | Write | Required |
| 6 | PRODUCTION | Destructive | Required |
| 7 | ANY | Schema change | Required |
| 8 | ANY | Permission change | Required |

### Information Hierarchy
1. **Focus**: Large textarea is the primary input
2. **Configure**: Environment + Priority selectors below
3. **Aware**: Governance panel is persistently visible as context
4. **Commit**: Submit button with token estimate

### States

| State | Behavior |
|-------|----------|
| **Empty form** | Textarea placeholder visible, Submit disabled, governance panel shown |
| **PRODUCTION selected** | Inline amber callout below radio: "Production tasks require approval for write and destructive operations." |
| **Submitting** | Submit button shows spinner + "Submitting…", all inputs disabled |
| **Submission error** | Rose banner above form with error message. Form data preserved. |

---

## Page 3 — Task Detail

> **Stitch screen**: `c57d1be670bb43da827e51b6c08b6927`
> **Route**: /tasks/:id
> **Purpose**: Full lifecycle transparency for a single task.

### Layout

```
┌─────────────────────────────────────────────────────────┐
│ TASK HEADER (full width card)                           │
│  T-1847  [IN_DEVELOPMENT]                               │
│  "Optimize Snowflake warehouse scaling…"                │
│  J.Chen · SANDBOX · MEDIUM · dev-agent-07 · 2h ago      │
├─────────────────────────────────────────────────────────┤
│ STATE STEPPER (full width card)                         │
│  ✓PARSE ─ ✓PLAN ─ ●DEVELOP ─ ○VALIDATE ─ ○APPROVE ─ ○DEPLOY │
├─────────────────────────────┬───────────────────────────┤
│ AGENT ACTIVITY (cols 1–7)   │ RIGHT PANEL (cols 8–12)  │
│                             │                           │
│ 🟢 Live                     │ ┌─ ARTIFACTS ──────────┐  │
│ 10:22 Analyzing warehouse…  │ │ execution_plan.json  │  │
│ 10:25 Generating policy…    │ │ scaling_policy.sql   │  │
│ 10:31 Writing queries…      │ │ validation_report.md │  │
│ 10:38 Running validation…   │ └──────────────────────┘  │
│                             │ ┌─ RESOURCES ──────────┐  │
│                             │ │ ██████░░░ 18.2k/50k  │  │
│                             │ │ Time: 24m  Retries:0 │  │
│                             │ └──────────────────────┘  │
│                             │ ┌─ SAFETY GATES ───────┐  │
│                             │ │ Gate 1 ✓  Gate 2 ✓   │  │
│                             │ │ Gate 3 ◌  Gate 4 ○   │  │
│                             │ └──────────────────────┘  │
├─────────────────────────────┴───────────────────────────┤
│ ACTION BAR (sticky)                                     │
│  [Cancel Task]              [Auto-refreshing]  [Escalate]│
└─────────────────────────────────────────────────────────┘
```

### Sections

| Section | Grid Columns | Content |
|---------|-------------|---------|
| **Task header** | 12 cols | ID, state badge, description, metadata chips |
| **State stepper** | 12 cols | 6-phase horizontal progress. See DESIGN_SYSTEM §6. |
| **Agent activity** | cols 1–7 | Live-updating timestamped log. Green "Live" indicator. |
| **Artifacts** | cols 8–12 | List with name, type badge, timestamp, "View" button |
| **Resources** | cols 8–12 | Token bar, agent time, retry count |
| **Safety gates** | cols 8–12 | 4-gate checklist with status icons |
| **Action bar** | 12 cols, sticky bottom | Cancel (rose ghost, left), Escalate (amber ghost, right) |

### Agent Activity Log Entry

| Element | Font | Color |
|---------|------|-------|
| Timestamp | JetBrains Mono 12px | `neutral-500` |
| Agent ID | JetBrains Mono 12px | `neutral-500` |
| Action text | Inter 14px | `neutral-700` |
| Token count | Inter 12px, right-aligned | `neutral-400` |

### Information Hierarchy
1. **Identity**: Header — what task, what state
2. **Progress**: Stepper — where in the lifecycle
3. **Activity**: Log — what the agent is doing right now
4. **Governance**: Gates + resources — safety compliance + budget
5. **Outputs**: Artifacts — what has been produced
6. **Action**: Cancel or escalate

### States

| State | Behavior |
|-------|----------|
| **Loading** | Skeleton: header card + stepper card + two-column skeletons |
| **Active (live)** | Green "Live" dot, log auto-appends, stepper animates on transitions |
| **Completed** | All stepper nodes emerald ✓, "Live" becomes "Completed at [time]", action bar removed |
| **Failed** | Failed stepper node rose ✕, rose banner with error summary, "Escalate" button prominent |
| **Cancelled** | All future nodes grayed, "CANCELLED" badge, read-only, action bar removed |
| **Error (page load)** | Rose banner: "Unable to load task details. [Retry]" |

---

## Page 4 — Approval Review

> **Stitch screen**: `e30f653cef5841fcb1accb055f84c5f8`
> **Route**: /tasks/:id/review
> **Tab**: "Pending Approval" active
> **Purpose**: Provide complete decision context for human approval. Reviewer should never need to navigate away.

### Layout

```
┌─────────────────────────────────────────────────────────┐
│ ALERT BANNER (amber-50, full width)                     │
│  ⚠ This task requires human approval.                   │
│  INV-01 · Production write · Waiting 23 min             │
├──────────────────────────────┬──────────────────────────┤
│ LEFT PANEL (cols 1–6)        │ RIGHT PANEL (cols 7–12)  │
│                              │                          │
│ ┌─ TASK CONTEXT ──────────┐  │ ┌─ CODE PREVIEW ───────┐ │
│ │ T-1832 [APPROVAL_PENDING]│ │ │ ALTER TABLE analytics │ │
│ │ "Deploy ETL pipeline…"  │  │ │ INSERT INTO prod.*   │ │
│ │ J.Chen · PROD · HIGH    │  │ │ (rose highlights)    │ │
│ └─────────────────────────┘  │ └──────────────────────┘ │
│                              │                          │
│ ┌─ WHY APPROVAL REQUIRED ─┐ │ ┌─ AUDIT TRAIL ────────┐ │
│ │ Trigger: Prod write      │ │ │ 10:14 SUBMITTED      │ │
│ │ Risk: 0.82 HIGH          │ │ │ 10:15 PARSED ✓       │ │
│ │ Gates: ✓ ✓ ⚠ ○           │ │ │ 10:18 PLANNED ✓      │ │
│ │ Patterns: ALTER, INSERT  │ │ │ 10:43 APPROVAL ⚠     │ │
│ └─────────────────────────┘  │ └──────────────────────┘ │
│                              │                          │
│ ┌─ EXECUTION PLAN ────────┐ │                          │
│ │ 1. Alter table…          │ │                          │
│ │ 2. Backfill 2.1M rows…  │ │                          │
│ │ 3. Update materialized…  │ │                          │
│ │ 4. Validate counts…      │ │                          │
│ └─────────────────────────┘  │                          │
├──────────────────────────────┴──────────────────────────┤
│ ACTION BAR (sticky bottom)                              │
│  [Comment textarea…]  [Escalate] [Changes] [Reject] [Approve] │
│  "Actions are final and recorded. INV-01 enforced."     │
└─────────────────────────────────────────────────────────┘
```

### Sections

| Section | Grid Columns | Content |
|---------|-------------|---------|
| **Alert banner** | 12 cols | Amber-50, 2px amber left border, ⚠ icon, INV-01 reference, wait time |
| **Task context** | cols 1–6 | ID, badge, description, metadata, environment badge |
| **Decision explanation** | cols 1–6 | Why approval triggered, risk score, gate results, detected patterns |
| **Execution plan** | cols 1–6 | Numbered steps of proposed actions |
| **Code preview** | cols 7–12 | Syntax-highlighted block, dark background (#1E1E2E), dangerous keywords rose-highlighted |
| **Audit trail** | cols 7–12 | Vertical timeline, all state transitions with timestamps |
| **Action bar** | 12 cols, sticky | Comment field + 4 buttons: Escalate (ghost), Request Changes (amber), Reject (rose), Approve (emerald) |

### Information Hierarchy
1. **Alert**: Banner — something needs your decision
2. **Context**: What task, who submitted, what environment
3. **Justification**: Why approval was triggered, risk assessment
4. **Evidence**: Execution plan + actual code to be run
5. **History**: Audit trail of everything that led here
6. **Decision**: Approve / Reject / Request Changes

### States

| State | Behavior |
|-------|----------|
| **Loading** | Skeleton for header + two-column content |
| **Waiting < 15 min** | Normal amber banner |
| **Waiting ≥ 15 min** | Time counter turns amber bold, banner intensifies |
| **Approved** | Redirect to Task Detail, toast "Task T-XXXX approved" |
| **Rejected** | Redirect to Task Detail, toast "Task T-XXXX rejected" |
| **Error (action failed)** | Rose inline banner in action bar: "[Action] failed. [Retry]" |

---

## Page 5 — Artifact Viewer

> **Route**: /tasks/:id/artifacts/:artifactId (or inline slide-over from Task Detail)
> **Purpose**: Inspect code, reports, and execution plans produced by agents.

### Layout

```
┌─────────────────────────────────────────────────────────┐
│ BREADCRUMB: All Tasks > T-1847 > scaling_policy.sql     │
├─────────────────────────────────────────────────────────┤
│ ARTIFACT HEADER                                         │
│  "scaling_policy.sql"  [Code] badge  Generated 10:31    │
│  Agent: dev-agent-07   Size: 2.4 KB                     │
│                        [Copy] [Download] [⛶ Fullscreen] │
├─────────────────────────────────────────────────────────┤
│ CONTENT AREA (12 cols, monospace, full width)            │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ 1  │ -- Scaling policy optimization                 │ │
│ │ 2  │ -- Generated by dev-agent-07                   │ │
│ │ 3  │ ALTER TABLE analytics.fact_sessions             │ │ ← rose bg
│ │ 4  │   ADD COLUMN processing_tier VARCHAR(20);       │ │ ← rose bg
│ │ 5  │                                                │ │
│ │ 6  │ INSERT INTO analytics.fact_sessions             │ │
│ │ ...│                                                │ │
│ └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ METADATA FOOTER                                         │
│  Type: SQL · Lines: 142 · Risk patterns: ALTER TABLE    │
│  Safety: Gate 1 ✓  Gate 2 ✓  Gate 3 ⚠ 0.82            │
└─────────────────────────────────────────────────────────┘
```

### Sections

| Section | Content |
|---------|---------|
| **Artifact header** | Name, type badge, generation timestamp, agent ID, size, toolbar |
| **Content area** | Line-numbered display. JetBrains Mono 13px on dark (#1E1E2E) background. Dangerous operations highlighted with rose-50 background. |
| **Metadata footer** | File type, line count, detected risk patterns, safety gate results |

### Content rendering by artifact type

| Type | Rendering |
|------|-----------|
| `.sql`, `.py` | Syntax-highlighted code, line numbers, rose highlights on dangerous ops |
| `.json` | Pretty-printed JSON with collapsible nodes |
| `.md` | Rendered markdown with heading hierarchy |
| Execution Plan | Numbered step list with target tables and impact notes |
| Validation Report | Structured pass/fail checklist with details |

### Information Hierarchy
1. **Identity**: What artifact, who generated it, when
2. **Content**: The actual code/report
3. **Risk**: Highlighted dangerous operations + gate results

### States

| State | Behavior |
|-------|----------|
| **Loading** | Shimmer placeholder matching code block height |
| **Loaded** | Full content rendered, toolbar active |
| **Empty (no content)** | "This artifact has no content." centered muted text |
| **Load error** | Rose card: "Unable to load artifact. [Retry]" |
| **Fullscreen** | Content expands to fill viewport, Escape to exit |

---

## Page 6 — System Health / Admin

> **Stitch screen**: `ca021408f98d4191811aa60cd34401a1`
> **Tab**: "System Health" active
> **Purpose**: Infrastructure monitoring, agent pool oversight, governance compliance.

### Layout

```
┌─────────────────────────────────────────────────────────┐
│ PAGE HEADER                                             │
│  "System Health"    Last updated: 10:43 UTC  [↻ Refresh]│
├────────────┬────────────┬────────────┬──────────────────┤
│ API Health │ Orchestratr│ Database   │ Redis            │
│ ✓ Healthy  │ ✓ Running  │ ✓ 23ms    │ ✓ 2ms            │
├────────────┴────────────┴────────────┴──────────────────┤
│ AGENT POOL (full width table)                           │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ ID         Type         Status  Task     Uptime    │ │
│ │ dev-07     Developer    BUSY    T-1847   4h 12m    │ │
│ │ val-03     Validation   ERROR   —        0h 02m    │ │ ← rose border
│ │ opt-01     Optimization IDLE    —        12h 30m   │ │
│ └─────────────────────────────────────────────────────┘ │
│  Summary: 4 busy · 1 idle · 1 error                    │
├─────────────────────────────────────────────────────────┤
│ GOVERNANCE — INVARIANT STATUS                           │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ INV-01  No destructive op without approval  ✓ ENFD │ │
│ │ INV-02  State persisted before ack          ✓ ENFD │ │
│ │ …                                                   │ │
│ │ INV-09  Approval requires DecisionExplanation ✓ENFD│ │
│ └─────────────────────────────────────────────────────┘ │
│  Last audit: 2 min ago · 0 violations                  │
├─────────────────────────────────────────────────────────┤
│ SYSTEM EVENTS LOG (monospace, scrollable)               │
│  10:43 [INFO] Agent dev-12 returned to pool             │
│  10:42 [WARN] val-03 health check timeout               │
│  10:41 [INFO] T-1832 approved by j.chen                 │
└─────────────────────────────────────────────────────────┘
```

### Sections

| Section | Grid Columns | Content |
|---------|-------------|---------|
| **Service status strip** | 4 × 3 cols | 4 metric cards: service name, health badge, latency |
| **Agent pool** | 12 cols | Table: ID (mono), Type, Status badge, Current Task, Uptime, Token bar |
| **Invariant status** | 12 cols | 9 rows: INV code (mono), description, ✓ ENFORCED or ⚠ WARNING badge |
| **System events** | 12 cols | Monospace log, 10 visible lines, scrollable. Color-coded by level. |

### Agent Status Badges

| Status | Badge Style |
|--------|-------------|
| IDLE | Slate outlined pill |
| BUSY | Blue outlined pill |
| ERROR | Rose filled pill, row gets 2px rose left border |

### Information Hierarchy
1. **Glance**: Service health strip — all green or not
2. **Agents**: Pool overview — who's busy, who's broken
3. **Compliance**: Invariant enforcement — any violations
4. **Detail**: Event log — recent system activity

### States

| State | Behavior |
|-------|----------|
| **Loading** | Skeleton: 4 metric cards + table skeleton + checklist skeleton |
| **Healthy** | All services emerald ✓, all invariants ENFORCED |
| **Degraded** | Affected service shows amber ⚠, event log highlights cause |
| **Agent error** | ERROR agent row has rose border, agent count summary updates |
| **Invariant violation** | Affected invariant shows ⚠ WARNING (amber), alert banner appears at page top |
| **Error (page load)** | Rose banner: "Unable to load system health. [Retry]" |
| **Stale data** | If > 60s since last update: "Data may be stale. [Refresh]" amber text near timestamp |

---

## Cross-Page Navigation Map

```
Dashboard ──click row──→ Task Detail ──"View" artifact──→ Artifact Viewer
    │                        │
    │                        ├──if APPROVAL_PENDING──→ Approval Review
    │                        │                              │
    │                        ├──"Cancel Task"──→ Confirmation Modal
    │                        │
    │                        └──"Escalate"──→ Confirmation Modal
    │
    ├──"Submit Task" (header)──→ Task Submission ──success──→ Task Detail
    │
    ├──"Pending Approval" tab──→ Dashboard (filtered)──click──→ Approval Review
    │
    └──"System Health" tab──→ System Health
```

| From | Action | To |
|------|--------|----|
| Dashboard | Click task row | Task Detail |
| Dashboard | "Pending Approval" tab | Dashboard filtered to approval states |
| Dashboard | "Submit Task" button | Task Submission |
| Task Submission | Submit success | Task Detail (new task) |
| Task Detail | Click "View" on artifact | Artifact Viewer (inline or route) |
| Task Detail | State is APPROVAL_PENDING | Shows "Review" link → Approval Review |
| Approval Review | Approve / Reject | Task Detail (updated state) |
| Any page | "System Health" tab | System Health |
