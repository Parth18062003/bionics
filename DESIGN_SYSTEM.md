# AADAP DESIGN SYSTEM — Specification

> Authoritative design system for the AADAP Control Plane.
> Phase 7 frontend implementation MUST conform to this document.
> Visual reference: Stitch project `10373594301173479537`, screen `9e7175ebf409411eab8e62b60bd8ad5e`

---

## 1. Design Principles

| Principle | Rule |
|-----------|------|
| Information-first | Every pixel serves comprehension. No decorative elements. |
| Calm authority | Neutral surfaces, restrained color. The UI never shouts. |
| No color-only signaling | Every status uses **icon + text + color**. WCAG AA minimum. |
| Consistency | One component per purpose. No ad-hoc variants. |
| Density with clarity | High information density, but generous line-height and padding. |

---

## 2. Color Palette

### 2.1 Neutral Scale (Surfaces & Text)

| Token | Hex | Usage |
|-------|-----|-------|
| `neutral-white` | `#FFFFFF` | Card surfaces, input backgrounds |
| `neutral-50` | `#F7F8FA` | Page background, table headers, info panels |
| `neutral-100` | `#EEEEF0` | Hover states, disabled backgrounds |
| `neutral-200` | `#E2E2E8` | Borders, dividers |
| `neutral-300` | `#C8C8D0` | Inactive stepper lines, placeholder text |
| `neutral-500` | `#71717A` | Caption text, metadata |
| `neutral-700` | `#3F3F46` | Body text, secondary content |
| `neutral-900` | `#1A1A2E` | Headings, primary text |

### 2.2 Primary Accent

| Token | Hex | Usage |
|-------|-----|-------|
| `primary-100` | `#EEF2FF` | Selected row backgrounds, focus rings |
| `primary-500` | `#4A6CF7` | Active tabs, primary buttons, links, active stepper |
| `primary-600` | `#3B5DE6` | Primary button hover |

> **Rule**: Blue is the ONLY accent color. It signals interactivity and active state.

### 2.3 Semantic Colors

Each semantic category has a **foreground** (text/border), **background** (fill), and **icon**.

| Category | Foreground | Background | Icon | Meaning |
|----------|-----------|------------|------|---------|
| **Informational** | `#64748B` (Slate-500) | `#F8FAFC` (Slate-50) | `ℹ` circle-info | Neutral in-progress states |
| **Success** | `#059669` (Emerald-600) | `#ECFDF5` (Emerald-50) | `✓` check-circle | Completed, passed, deployed |
| **Warning / Approval** | `#D97706` (Amber-600) | `#FFFBEB` (Amber-50) | `⚠` alert-triangle | Pending approval, attention needed |
| **Destructive / Blocking** | `#DC2626` (Rose-600) | `#FFF1F2` (Rose-50) | `✕` x-circle | Failed, rejected, cancelled |

> **WCAG Rule**: All foreground colors meet 4.5:1 contrast on their respective backgrounds AND on white.

---

## 3. Typography

| Role | Family | Weight | Size | Color | Usage |
|------|--------|--------|------|-------|-------|
| Page Title | Inter | SemiBold (600) | 20px | `neutral-900` | Page-level headings |
| Section Heading | Inter | Medium (500) | 16px | `neutral-900` | Card titles, section labels |
| Body | Inter | Regular (400) | 14px / 1.5 line-height | `neutral-700` | All body content |
| Caption | Inter | Regular (400) | 12px | `neutral-500` | Timestamps, metadata, helper text |
| Monospace | JetBrains Mono | Regular (400) | 13px | `neutral-700` | Task IDs, agent IDs, code, timestamps |

> **Rule**: Never use Inter below 12px. Never use bold (700) in body text — reserve for headings only.

---

## 4. Spacing & Layout

| Token | Value | Usage |
|-------|-------|-------|
| `space-1` | 4px | Inline padding (badge internals) |
| `space-2` | 8px | Base unit. Icon gaps, tight padding. |
| `space-3` | 12px | Input internal padding |
| `space-4` | 16px | Card padding, section gaps |
| `space-6` | 24px | Between card groups |
| `space-8` | 32px | Page margins, major section separation |

**Border radius**: `6px` (rounded-md) for all components. No fully-rounded elements except badges.

---

## 5. Components

### 5.1 Buttons

| Variant | Fill | Border | Text | Height | When to use |
|---------|------|--------|------|--------|-------------|
| **Primary** | `primary-500` | none | White | 36px | Single primary action per view (Submit, Approve) |
| **Secondary** | White | 1px `neutral-200` | `neutral-700` | 36px | Non-primary actions (Save Draft, Cancel) |
| **Destructive** | `rose-600` | none | White | 36px | Irreversible actions (Cancel Task, Reject) |
| **Ghost** | transparent | none | `primary-500` | 36px | Tertiary actions (Clear Filters, links) |
| **Disabled** | `neutral-100` | none | `neutral-300` | 36px | Inactive state for any variant |

**Rules**:
- Maximum ONE primary button visible per action context
- Destructive buttons require a confirmation modal before executing
- All buttons have a 2px `primary-100` focus ring for keyboard navigation
- Minimum touch target: 36×36px

### 5.2 Form Inputs

| Property | Value |
|----------|-------|
| Height | 40px (single-line), 120px min (textarea) |
| Border | 1px `neutral-200`, on focus: 2px `primary-500` |
| Background | White |
| Placeholder | `neutral-300`, Inter Regular 14px |
| Border radius | 6px |
| Label | 12px `neutral-500`, positioned above, 4px gap |
| Error state | Border becomes `rose-600`, error message below in `rose-600` 12px |

**Segmented Controls** (e.g., Environment selector):
- Connected buttons sharing a 1px `neutral-200` border
- Active segment: `primary-500` background, white text
- Inactive segment: white background, `neutral-700` text

**Dropdowns**: Same border treatment as text input. Chevron icon right-aligned. Menu appears below with `neutral-50` header if grouped.

### 5.3 Tables

| Element | Style |
|---------|-------|
| Header row | `neutral-50` background, 12px `neutral-500` uppercase text, `space-3` padding |
| Data rows | White background, 14px `neutral-700`, `space-3` padding |
| Row divider | 1px `neutral-200` horizontal lines only (no vertical) |
| Hover row | `neutral-50` background transition |
| Clickable rows | Cursor pointer, `neutral-50` hover |
| Monospace columns | Task ID, Agent ID, Timestamps in JetBrains Mono 13px |

**Rules**:
- No zebra striping — use dividers
- Sortable columns show a chevron icon in the header
- Tables must be horizontally scrollable on narrow viewports

### 5.4 Status Badges

Pill-shaped, outlined, with **icon + text**. Never color-only.

| State Group | States | Border | Text | Icon | Background |
|-------------|--------|--------|------|------|------------|
| **In Progress** | `PARSING`, `PLANNING`, `IN_DEVELOPMENT`, `IN_VALIDATION`, `IN_OPTIMIZATION`, `DEPLOYING` | `slate-300` | `slate-600` | `●` (filled dot) | `slate-50` |
| **Waiting** | `APPROVAL_PENDING`, `IN_REVIEW`, `OPTIMIZATION_PENDING` | `amber-400` | `amber-700` | `⚠` (triangle) | `amber-50` |
| **Success** | `DEPLOYED`, `COMPLETED`, `VALIDATION_PASSED`, `OPTIMIZED`, `APPROVED` | `emerald-400` | `emerald-700` | `✓` (check) | `emerald-50` |
| **Failed / Terminal** | `PARSE_FAILED`, `DEV_FAILED`, `VALIDATION_FAILED`, `REJECTED`, `CANCELLED` | `rose-400` | `rose-700` | `✕` (x) | `rose-50` |
| **Queued** | `SUBMITTED`, `PARSED`, `PLANNED`, `AGENT_ASSIGNED`, `CODE_GENERATED` | `neutral-300` | `neutral-600` | `○` (hollow dot) | White |

**Badge sizing**: 12px text, `space-1` vertical padding, `space-2` horizontal padding, full-round corners.

### 5.5 Risk Level Badges

| Level | Style | Text Treatment |
|-------|-------|----------------|
| `LOW` | `neutral-200` border, `neutral-500` text | lowercase |
| `MEDIUM` | `amber-300` border, `amber-700` text | lowercase |
| `HIGH` | `rose-300` border, `rose-700` text, **bold** | uppercase |
| `CRITICAL` | `rose-600` **filled**, white text, **bold** | uppercase |

### 5.6 Cards & Panels

| Variant | Background | Border | Padding | When to use |
|---------|------------|--------|---------|-------------|
| **Default Card** | White | 1px `neutral-200` | `space-4` | General content containers |
| **Approval Card** | White | 1px `neutral-200` + **2px amber left border** | `space-4` | Items pending human action |
| **Alert Card** | White | 1px `neutral-200` + **2px rose left border** | `space-4` | Failed or blocked items |
| **Info Panel** | `neutral-50` | none | `space-4` | Read-only context, governance notices |
| **Metric Card** | White | 1px `neutral-200` | `space-4` | Dashboard KPIs (count + label) |

**Rules**:
- No box shadows. Borders only.
- Cards do not nest inside other cards.
- Maximum card content width: 720px for text-heavy cards.

### 5.7 Modals & Confirmation Dialogs

| Property | Value |
|----------|-------|
| Backdrop | Black at 40% opacity |
| Container | White, 480px width, 6px border radius |
| Title | 16px Inter SemiBold, `neutral-900` |
| Body | 14px Inter Regular, `neutral-700` |
| Warning callout | `amber-50` background, `amber-600` left border (2px), `⚠` icon + text |
| Danger callout | `rose-50` background, `rose-600` left border (2px), `✕` icon + text |
| Footer | Right-aligned buttons, 8px gap. Secondary left, Primary/Destructive right. |

**Rules**:
- Destructive and approval actions **always** require a confirmation modal
- Modal must state the exact consequence of the action
- Production-targeting operations display a `PRODUCTION` badge in the modal title bar
- Modal is dismissible via Escape key and backdrop click (unless confirmation-required)

---

## 6. State Stepper (Task Progress)

A compact horizontal progress indicator used in task list rows and task detail headers.

| Property | Value |
|----------|-------|
| Phases | PARSE → PLAN → DEVELOP → VALIDATE → APPROVE → DEPLOY |
| Node size | 12px circles, 1px connecting lines |
| Completed | Emerald-600 filled circle, `✓` icon |
| Active | Primary-500 filled circle, slightly larger (14px), pulsing animation optional |
| Future | `neutral-300` hollow circle |
| Failed | Rose-600 filled circle, `✕` icon |
| Label | 10px `neutral-500` below each node, current state label in bold |
| Max width | 200px |

---

## 7. Accessibility Rules

| Requirement | Standard |
|-------------|----------|
| Color contrast (text) | Minimum 4.5:1 against background (WCAG AA) |
| Color contrast (large text) | Minimum 3:1 (WCAG AA) |
| No color-only signaling | All statuses use icon + text + color |
| Focus indicators | 2px `primary-100` ring on all interactive elements |
| Keyboard navigation | All actions reachable via Tab/Enter/Escape |
| Screen reader labels | All icons have `aria-label`. Status badges read as "[icon meaning] [state name]" |
| Motion | Respect `prefers-reduced-motion`. No required animations. |

---

## 8. Anti-Patterns (Explicitly Forbidden)

- ❌ Gradients, shadows, or glowing effects
- ❌ Color-only status indication (must always pair with icon + text)
- ❌ More than one primary button per action group
- ❌ Nested cards
- ❌ Custom fonts beyond Inter and JetBrains Mono
- ❌ Rounded-full on anything except badges and avatars
- ❌ Consumer aesthetics: emojis, illustrations, playful copy
- ❌ Charts unless explicitly required by a specific screen contract
