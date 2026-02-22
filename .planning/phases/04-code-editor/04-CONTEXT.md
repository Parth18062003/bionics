# Phase 4: Code Editor - Context

**Gathered:** 2026-02-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can view, edit, and version generated code artifacts before deployment. This includes syntax-highlighted viewing (Python/PySpark), diff comparison against original, and saving edits as new artifact versions. The editor loads without hydration issues via lazy loading.

</domain>

<decisions>
## Implementation Decisions

### Editor Layout
- Full-screen editor as default viewing mode — code takes the full page for maximum readability
- Side-by-side diff view when comparing changes — original on left, edited on right
- Sticky top bar for toolbar actions — always visible while scrolling code
- Rich header above code showing: artifact name, version history dropdown, language indicator, last modified timestamp, author

### Claude's Discretion
- Exact toolbar button design and icons
- Syntax highlighting theme (should match project's dark theme)
- Line numbers styling and width
- Scroll behavior and minimap
- Error/warning squiggle styling
- Keyboard shortcuts for common actions (save, undo, format)

</decisions>

<specifics>
## Specific Ideas

- Editor should feel like a proper IDE code view, not a simple textarea
- Diff view similar to GitHub's pull request diff — clear visual separation between original and edited

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 04-code-editor*
*Context gathered: 2026-02-22*
