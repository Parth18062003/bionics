# PHASE 6.5 — UI DESIGN (STITCH MCP) CONTRACTS

## Objective
Produce a governed, reusable, implementation-ready UI design
using Stitch MCP, without writing frontend code.

## Design Authority
- Stitch MCP is the sole design generator
- Claude Opus must NOT invent UI layout, structure, or styling
- Phase 7 must implement exactly what is defined here

## Inputs
- User personas
- Core user journeys
- System architecture (presentation layer)
- Governance constraints (approvals, audit visibility)

## Required Design Artifacts

### 1. Design System
- Color palette
- Typography scale
- Spacing system
- Component variants
- Accessibility rules (WCAG baseline)

### 2. Page-Level Layouts
Authoritative layouts for:
- Dashboard
- Task submission
- Task detail
- Approval review
- Artifact viewer
- Admin / system health

Each page must define:
- Layout grid
- Primary sections
- Information hierarchy
- States (loading, error, empty)

### 3. Component Inventory
Reusable components including:
- Navigation
- Task card
- State timeline
- Code/artifact viewer
- Approval action panel
- Status badges
- Alerts and confirmations

Each component must specify:
- Props (conceptual, not code)
- States
- Variants
- Accessibility notes

### 4. Interaction Flows
- Task creation → completion
- Approval flow
- Error and escalation paths
- Real-time updates

## Non-Goals
- No React/TanStack code
- No CSS/Tailwind decisions
- No implementation assumptions

## Definition of Done
- All required artifacts generated
- No UI gaps for Phase 7
- Design artifacts are complete enough for deterministic implementation
