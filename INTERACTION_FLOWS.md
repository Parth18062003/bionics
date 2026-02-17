# AADAP INTERACTION FLOWS — Specification

> Authoritative interaction flow definitions for the AADAP Control Plane.
> Every screen state must answer three questions:
> **What is happening? · Why is it happening? · What can I do next?**

---

## 1. Task Submission Flow

### Flow: IDLE → INPUT → CONFIRM → SUBMITTED

```
User opens Submit page
  → Empty form state
  → User types NL description
  → User selects Environment (SANDBOX default)
  → User selects Priority (MEDIUM default)
  → User clicks "Submit Task"
    → Confirmation modal appears
    → User confirms
      → Optimistic transition: button becomes spinner + "Submitting..."
      → On success: redirect to Task Detail, state = SUBMITTED
      → On failure: inline error banner, form preserved
```

#### States

| State | What the user sees | Why | What they can do |
|-------|-------------------|-----|------------------|
| **Empty form** | Blank textarea, default selectors, governance panel visible | No task started | Type description, adjust settings |
| **Filled form** | Populated fields, "Submit Task" button active | Ready to submit | Submit or Save as Draft |
| **Confirmation modal** | Modal: "Submit to [ENVIRONMENT]?", shows environment badge, token estimate | Preventing accidental submission | Confirm or Cancel |
| **Submitting** | Button shows spinner + "Submitting...", form inputs disabled | API call in flight | Wait (no action available) |
| **Submitted success** | Redirect to Task Detail page, toast: "Task T-XXXX submitted" | Task accepted by orchestrator | View task progress |
| **Submission error** | Red error banner above form: "[error message]", form fields preserved | API or validation failure | Fix and retry, or copy task text |

#### Rules
- PRODUCTION environment selection shows an inline warning: "Production tasks require human approval for write and destructive operations."
- Empty description disables the Submit button (no error until blur/submit attempt)
- Token budget estimate updates reactively as description length changes
- Confirmation modal for PRODUCTION tasks includes an amber callout: "This task will target the production environment."

---

## 2. Validation Waiting Flow

### Flow: SUBMITTED → PARSING → PLANNING → IN_DEVELOPMENT → IN_VALIDATION

```
User views Task Detail
  → Stepper shows current phase highlighted
  → Agent Activity Log streams updates
  → Each state transition:
    → Stepper advances
    → New log entry appears
    → Timestamp updates
  → During IN_VALIDATION:
    → Governance Status card shows gates being checked sequentially
    → Gate 1 (Static Analysis): spinner → ✓ or ✕
    → Gate 2 (Pattern Matching): spinner → ✓ or ✕
    → Gate 3 (Semantic Risk): spinner → score + level
```

#### States

| State | What the user sees | Why | What they can do |
|-------|-------------------|-----|------------------|
| **Actively processing** | Stepper node pulsing blue, activity log streaming new entries every few seconds, "Auto-refreshing" indicator | Agent is working | Watch progress, cancel task |
| **Between transitions** | Stepper stable, last log entry shows completed step, waiting indicator | System processing next transition | Watch, cancel |
| **Validation in progress** | Safety gates checklist updating sequentially (spinner on current gate) | Code passing through 4 safety gates | Watch gate results |
| **Validation passed** | All gates show ✓ (emerald), next stepper node activates | Code cleared all safety checks | Await next phase |
| **Validation failed** | Failed gate shows ✕ (rose) with reason, stepper node turns red | Code failed a safety check | View failure reason, may re-trigger |

#### Loading Patterns
- **Stepper nodes**: Current node has a subtle pulse animation (respects `prefers-reduced-motion`)
- **Activity log**: New entries slide in from the bottom with a 150ms ease-out
- **Gate checks**: Each gate shows a small spinner (12px) while evaluating, then snaps to ✓ or ✕
- **Auto-refresh indicator**: Small "Live" label with a green dot in the page header, signals real-time updates are active

#### Rules
- Log entries are append-only — never removed or reordered
- Token usage bar updates with each agent action
- If the user navigates away and returns, the log reconstructs from persisted state (no gaps)
- Retry count (0/3) is always visible; increments are accompanied by a log entry explaining why

---

## 3. Approval Required Flow

### Flow: VALIDATION_PASSED → APPROVAL_PENDING → IN_REVIEW → APPROVED

```
Task reaches APPROVAL_PENDING
  → Dashboard: task row gets amber left border, "APPROVAL_PENDING" badge
  → "Pending Approval" tab count increments
  → Notification: reviewer receives bell notification + optional email
  
Reviewer opens task
  → Approval Review screen:
    → Alert banner: "This task requires human approval"
    → Decision Explanation: why approval was triggered, risk score, gate results
    → Execution plan: numbered steps of what will happen
    → Generated code: syntax-highlighted with dangerous operations marked
    → Audit trail: full timeline of state transitions
  
Reviewer clicks "Approve"
  → Confirmation modal:
    → Title: "Confirm Approval"
    → Body: "This will authorize execution of [task description] in [ENVIRONMENT]."
    → If PRODUCTION: amber callout "This action will modify production resources."
    → Reviewer comment (optional)
    → Buttons: "Cancel" (secondary) | "Approve" (emerald)
  → On confirm:
    → State transitions: APPROVAL_PENDING → APPROVED → DEPLOYING
    → Stepper advances
    → Audit trail records: reviewer, timestamp, comment
    → Toast: "Task T-XXXX approved"
```

#### States

| State | What the user sees | Why | What they can do |
|-------|-------------------|-----|------------------|
| **Pending (Dashboard)** | Amber left-border row, ⚠ badge, time-waiting counter | Task awaiting human decision | Click to review |
| **Pending > 15 min** | Amber border intensifies, time counter turns amber text | Task aging without action | Click to review (urgency cue) |
| **In review** | Full approval screen with decision explanation, code, plan | Reviewer examining task | Approve, Reject, Request Changes, Escalate |
| **Confirmation modal** | Modal with action consequences, environment badge, comment field | Preventing accidental approval | Confirm or Cancel |
| **Approving** | Button spinner + "Approving...", other actions disabled | Recording decision | Wait |
| **Approved** | Toast notification, redirect to Task Detail, state = APPROVED | Decision recorded | Monitor deployment |

#### Rules
- Approval screen MUST display all information needed — reviewer should never need to navigate away
- Decision Explanation (INV-09) is always visible, never collapsed by default
- "Approve" and "Reject" always require confirmation modals
- "Request Changes" opens an inline comment field (no modal) and transitions to REJECTED with a "changes requested" flag
- Reviewer identity and timestamp are permanently recorded in the audit trail

---

## 4. Approval Rejection Flow

### Flow: APPROVAL_PENDING → IN_REVIEW → REJECTED

```
Reviewer opens task → Approval Review screen (same as §3)
  
Reviewer clicks "Reject"
  → Confirmation modal:
    → Title: "Confirm Rejection"
    → Body: "This will stop execution of [task description]. The submitter will be notified."
    → Rose callout: "This task will not proceed. A new task must be submitted to retry."
    → Rejection reason textarea (REQUIRED — cannot submit without)
    → Buttons: "Cancel" (secondary) | "Reject" (rose)
  → On confirm:
    → State transitions: IN_REVIEW → REJECTED
    → Stepper shows ✕ on APPROVE phase (rose)
    → Audit trail records: reviewer, timestamp, rejection reason
    → Submitter receives notification with rejection reason
    → Toast: "Task T-XXXX rejected"
    → Redirect to Task Detail (read-only)
```

#### Rejection-specific states

| State | What the user sees | Why | What they can do |
|-------|-------------------|-----|------------------|
| **Rejection modal** | Modal with required reason textarea, rose styling | Must document why | Type reason and confirm, or cancel |
| **Reason empty** | "Reject" button disabled, helper text: "A rejection reason is required for the audit trail" | INV-06 audit completeness | Type a reason |
| **Rejected (detail)** | Rose left-border card, ✕ badge, rejection reason displayed, action bar removed | Terminal state | View details, submit a new task |
| **Rejected (dashboard)** | Rose left-border row, "REJECTED" badge, visible under "Failed" tab | Terminal state | Click to view, or submit new task |

#### Rules
- Rejection reason is **mandatory** — the modal cannot be dismissed without it (INV-06)
- Rejected tasks are **read-only** — no edit, re-submit, or re-approve
- The submitter sees the rejection reason on the Task Detail page and in their notification
- "Request Changes" is an alternative to hard rejection: it sets state to REJECTED but with a `changes_requested` flag, and the rejection reason serves as guidance

---

## 5. Viewing Execution Artifacts

### Flow: User navigates to Task Detail → Artifacts Panel → Artifact Viewer

```
Task Detail page → Right column "Artifacts" section
  → List of artifacts (execution plan, generated code, validation report, etc.)
  → Each artifact shows: name, type badge, timestamp, size
  
User clicks "View" on an artifact
  → Artifact Viewer opens (inline expansion or slide-over panel)
    → For code: syntax-highlighted with line numbers
    → For reports: structured markdown rendering
    → For diffs: side-by-side before/after
  → Toolbar: "Copy" | "Download" | "Expand" (full-screen) | "Close"
```

#### States

| State | What the user sees | Why | What they can do |
|-------|-------------------|-----|------------------|
| **Artifacts loading** | Skeleton placeholders (3 rows of animated gray bars) in the artifacts panel | Fetching artifact metadata | Wait |
| **Artifacts available** | List of artifact cards with type badges and timestamps | Artifacts have been produced | Click to view any artifact |
| **No artifacts yet** | Muted text: "No artifacts generated yet. Artifacts appear as the agent produces them." | Task hasn't reached code generation | Wait, check back |
| **Artifact viewer open** | Expanded panel showing content, toolbar at top | Reviewing a specific artifact | Copy, download, close, expand |
| **Artifact load error** | Error card: "Unable to load artifact. [Retry]" rose-50 background | Fetch failed | Retry or dismiss |

#### Rules
- Artifacts are append-only — once produced, they don't disappear
- Code artifacts use JetBrains Mono, dark code-block background (#1E1E2E)
- Dangerous operations in code are highlighted with a subtle rose background
- "Copy" copies raw content to clipboard with a toast: "Copied to clipboard"
- Artifact list auto-updates as new artifacts are produced (same real-time pattern as activity log)

---

## 6. Error & Failure Recovery

### 6.1 Agent Failure (DEV_FAILED, VALIDATION_FAILED)

```
Agent encounters failure
  → Stepper node turns rose ✕
  → Activity log shows last action + error reason
  → If retries remain (< 3):
    → Log entry: "Retry 1/3 — [reason for retry]"
    → Stepper node returns to active (blue) 
    → Process continues
  → If retries exhausted:
    → State transitions to *_FAILED
    → Banner: rose-50, "Task failed after 3 attempts. [View error details]"
    → Action bar: "Escalate to Admin" (amber) | "Cancel Task" (rose ghost)
```

| State | What the user sees | Why | What they can do |
|-------|-------------------|-----|------------------|
| **Retrying** | Log entry: "Retry 1/3", stepper node flickers, retry count increments | Agent self-correcting (INV-03: max 3) | Watch, cancel if desired |
| **Failed (retries exhausted)** | Rose banner with error summary, stepper node ✕, full error in log | Agent cannot complete | Escalate or Cancel |
| **Escalated** | Amber banner: "Escalated to [admin]. Awaiting manual intervention." | Human took over | Wait for admin action |

### 6.2 Network / API Errors

```
Any API call fails
  → Inline error banner (rose-50, rose left border):
    → "[Action] failed: [error]. [Retry]"
  → Form state preserved (no data loss)
  → If real-time connection drops:
    → "Live" indicator turns gray, label changes to "Reconnecting..."
    → Auto-retry with exponential backoff (1s, 2s, 4s, max 30s)
    → On reconnect: "Live" restores, missed events backfilled
```

| State | What the user sees | Why | What they can do |
|-------|-------------------|-----|------------------|
| **API error** | Rose inline banner with error message and Retry link | Server returned error | Retry, or reload page |
| **Connection lost** | Gray "Reconnecting..." indicator replaces green "Live" dot | WebSocket/SSE dropped | Wait (auto-reconnects), or reload |
| **Reconnected** | Green "Live" dot restores, missed events appear in log | Connection restored | Continue normally |
| **Persistent failure** | Banner: "Unable to reach server. Check your connection." (rose) after 3 retries | Server unreachable | Reload page, contact admin |

### 6.3 Parse Failure (PARSE_FAILED)

```
NL input cannot be parsed
  → Task Detail: stepper shows ✕ on PARSE phase
  → Banner: "The system could not understand this task. Please rephrase and submit a new task."
  → Shows original NL input for reference
  → Action: "Submit New Task" button (pre-fills the original text for editing)
```

### 6.4 Cancellation

```
User clicks "Cancel Task"
  → Confirmation modal:
    → Title: "Cancel Task T-XXXX?"
    → Body: "This will permanently stop this task. Any in-progress agent work will be terminated."
    → If task has produced artifacts: "Generated artifacts will be preserved for review."
    → Buttons: "Keep Running" (secondary) | "Cancel Task" (rose)
  → On confirm:
    → State → CANCELLED
    → Stepper grays out all future nodes
    → Badge: "CANCELLED" (rose ✕)
    → Action bar removed (read-only)
    → Toast: "Task T-XXXX cancelled"
```

---

## 7. Universal Loading States

| Context | Pattern | Duration Threshold |
|---------|---------|-------------------|
| **Page load** | Full skeleton: header skeleton + 6 row skeletons in task list | Show skeleton immediately, content replaces within 2s |
| **Button action** | Button text replaced with 16px spinner, button disabled | Immediate on click |
| **Inline data** | Shimmer placeholder (animated gray bar, neutral-100 → neutral-200) | Individual cells/badges |
| **Long operation** | Spinner + descriptive text: "Evaluating safety gates..." | After 3s, show progress text |

**Rules:**
- Never show a blank screen — always skeleton or spinner
- Skeleton shapes match the final content layout exactly
- Spinners are 16px, `neutral-400`, simple rotation (no bounce/pulse)
- If an operation takes > 10s, show a progress message explaining what is happening

---

## 8. Universal Empty States

| Context | Message | Action |
|---------|---------|--------|
| **No tasks (first use)** | "No tasks yet. Submit your first data engineering task to get started." | "Submit Task" primary button |
| **No matching filters** | "No tasks match the current filters." | "Clear filters" ghost link |
| **No pending approvals** | "No tasks pending approval." | None (informational) |
| **No artifacts** | "No artifacts generated yet. Artifacts appear as the agent produces them." | None (informational) |
| **No activity log entries** | "Waiting for agent activity..." with a subtle pulse dot | None (informational) |

**Rules:**
- Empty states are centered in their container
- Use `neutral-500` text, 14px Inter
- No illustrations, icons, or emojis
- Include an action button only if the user can resolve the empty state

---

## 9. Universal Confirmation Rules

| Action | Requires Confirmation | Modal Style |
|--------|----------------------|-------------|
| Submit task (any environment) | YES | Neutral modal, shows environment + estimate |
| Submit task to PRODUCTION | YES | Neutral modal + amber callout about production |
| Approve task | YES | Emerald confirm button + environment badge |
| Reject task | YES | Rose confirm button + mandatory reason textarea |
| Cancel task | YES | Rose confirm button + artifact preservation note |
| Request Changes | NO | Inline comment field expands, submit with Enter |
| Escalate | YES | Amber confirm button + admin target |
| Filter / search | NO | Immediate, no confirmation |
| Navigate away from unsaved draft | YES | Browser-native "unsaved changes" prompt |

**Rules:**
- Confirmation modals state the **exact consequence** of the action
- PRODUCTION-targeting actions always display the `PRODUCTION` badge in the modal
- Destructive confirmations use rose styling; approval confirmations use emerald
- "Cancel" in a modal always means "do nothing and close"
- Modals are dismissible via Escape and backdrop click unless they contain a required field (rejection reason)
