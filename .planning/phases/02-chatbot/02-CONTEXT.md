# Phase 2: Chatbot - Context

**Gathered:** 2026-02-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Conversational task creation through natural language. Users describe requirements in plain English, the system extracts structured requirements for confirmation, then creates a task. Includes dedicated chat page (/chat) and slide-out panel accessible from any page.

**In scope:**
- Chat interface (dedicated page + slide-out panel)
- Streaming LLM responses
- Requirement extraction with auto-suggest
- Session conversation history

**Out of scope:**
- Multi-conversation persistence (saved chats across sessions)
- Task execution/monitoring (separate features)
- Advanced chat features (threads, search, export)

</domain>

<decisions>
## Implementation Decisions

### Conversation Flow
- **Multi-turn dialogue** — User refines requirements through back-and-forth conversation, not single-shot extraction
- **Auto-suggest extraction** — LLM displays extracted requirements as it gains confidence during conversation (no explicit "extract" button needed)
- **Split view layout** — Chat on left, live requirements panel on right that updates progressively
- **Dual editing modes** — User can edit fields directly in the side panel OR describe changes in chat (both update the panel)

### Requirement Confirmation UI
- **Progressive disclosure** — Show core fields (name, description, target, objective) by default; expandable sections for details (success criteria, constraints, examples)
- **Create and offer options** — After task creation, show: "View Task" / "Create Another" / "Continue Chatting" buttons
- **Block on incomplete** — Cannot create task until all required fields are filled or confirmed
- **Field-level indicators** — Warning icon or asterisk next to each incomplete/uncertain field to highlight gaps

### Claude's Discretion
- Chat panel trigger method and positioning (slide-out panel behavior)
- Mobile responsive handling of split view
- Error/recovery flows when LLM or extraction fails
- Exact visual styling of warning indicators
- Animation/transition for requirements panel updates

</decisions>

<specifics>
## Specific Ideas

- Split view pattern similar to modern AI assistants (ChatGPT artifacts, Claude's side panels)
- Requirements panel should feel live and responsive, not a static form
- User should feel they're having a conversation, not filling a form

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-chatbot*
*Context gathered: 2026-02-22*
