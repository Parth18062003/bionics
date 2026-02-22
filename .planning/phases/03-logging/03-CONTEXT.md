# Phase 3: Logging - Context

**Gathered:** 2026-02-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can monitor and debug running tasks through comprehensive log visibility. Includes real-time logs embedded in task detail page, dedicated log viewer at /logs route with filtering and search, and export capability.

**In scope:**
- Real-time logs embedded in task detail page
- Dedicated log viewer at /logs route
- Filtering by level and text search
- Export capability (JSON, CSV)
- Logs display timestamp, level, message, correlation ID

**Out of scope:**
- Log aggregation across multiple systems
- Alerting/notifications based on logs
- Log retention policies (infrastructure concern)

</domain>

<decisions>
## Implementation Decisions

### Log Display Format
- **Standard info** — Each entry shows: timestamp, level, message, correlation ID, source/agent name
- **Icon + color** — Visual distinction for each log level (ERROR=red, WARN=amber, INFO=blue, DEBUG=gray) with icons
- **Inline chip for correlation ID** — Correlation ID shown as small clickable chip that filters to related logs
- **Truncate with expand** — Long messages truncated (~100 chars), click to expand full message

### Log Interaction
- **Auto-scroll + pause** — Auto-scrolls to newest logs, pauses when user scrolls up to read older entries
- **Multi-select dropdown** — Filter by multiple log levels at once (show ERROR + WARN, etc.)
- **Both search modes** — Search filters to matches by default, with option to show all logs with highlights
- **Auto-expand search** — When no results, suggest broadening (remove level filter, expand time range)

### Log Viewer Access
- **Both embedded + dedicated** — Logs viewable in task detail page AND dedicated /logs page
- **Embedded = minimal** — Embedded view is read-only stream, dedicated page has all filters/search/export
- **By task organization** — Dedicated page groups logs by task with task selector
- **JSON + CSV export** — Both formats available from dedicated page for different use cases

### Claude's Discretion
- Exact truncation length for messages
- Icon choices for each log level
- Animation/transition for expand/collapse
- Timestamp format (relative vs absolute)
- Loading states and skeleton design

</decisions>

<specifics>
## Specific Ideas

- Log viewer should feel like a modern IDE's output panel — scannable, responsive
- Correlation ID is key for debugging — make it easy to trace related events

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-logging*
*Context gathered: 2026-02-22*
