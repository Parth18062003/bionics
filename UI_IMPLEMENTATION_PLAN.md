# AADAP UI Implementation Plan

## Overview

This document outlines the comprehensive UI implementation plan for the AADAP multi-agent data engineering platform. The UI needs to support:

1. **Task Management** - Create, monitor, and manage tasks
2. **Agent Marketplace** - Browse and select agents
3. **Execution Dashboard** - Real-time task execution monitoring
4. **Resource Explorer** - Browse catalogs, schemas, tables
5. **Approval Workflow** - Review and approve/reject tasks
6. **Artifact Viewer** - View generated code, validation reports, execution results

---

## Current UI State

### Existing Pages
| Page | Path | Status |
|------|------|--------|
| Dashboard | `/` | Basic - needs enhancement |
| Task List | `/tasks` | Basic - needs filters and search |
| Task Detail | `/tasks/[id]` | Basic - needs execution timeline |
| New Task | `/tasks/new` | Functional - needs quick actions |
| Marketplace | `/marketplace` | Basic - needs categorization |
| Approvals | `/approvals` | Basic - needs bulk actions |
| Approval Detail | `/approvals/[id]` | Basic |
| Artifacts | `/artifacts/[taskId]/[id]` | Basic - needs code viewer |

### Missing Features
- Real-time execution progress
- Resource explorer (catalog/schema browser)
- Quick actions panel
- Execution timeline visualization
- Code editor with syntax highlighting
- Error trace viewer
- Bulk operations
- Search and filtering
- Notifications

---

## Implementation Phases

### Phase 1: Core Dashboard Enhancement

#### 1.1 Dashboard Overview (`/app/page.tsx`)

```
Layout:
┌─────────────────────────────────────────────────────────┐
│ Header: AADAP Platform                    [User] [⚙️]   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Stats Row                                          │ │
│ │ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │ │
│ │ │ Tasks   │ │ Running │ │ Pending │ │ Completed│   │ │
│ │ │ 1,234   │ │ 5       │ │ 12      │ │ 1,200   │   │ │
│ │ └─────────┘ └─────────┘ └─────────┘ └─────────┘   │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                         │
│ ┌────────────────────┐ ┌────────────────────────────┐  │
│ │ Quick Actions      │ │ Recent Tasks               │  │
│ │ ┌────────────────┐ │ │ ┌────────────────────────┐ │  │
│ │ │ 📋 List Tables │ │ │ │ Task: Generate ETL    │ │  │
│ │ │ 📁 List Schemas│ │ │ │ Status: Running ████  │ │  │
│ │ │ 📊 Preview     │ │ │ │ Agent: developer      │ │  │
│ │ │ 🔍 Run Query   │ │ │ └────────────────────────┘ │  │
│ │ │ 📝 Get Schema  │ │ │                            │  │
│ │ └────────────────┘ │ │ [View All Tasks →]        │  │
│ └────────────────────┘ └────────────────────────────┘  │
│                                                         │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Execution Activity (Live)                          │ │
│ │ [Real-time WebSocket updates]                      │ │
│ └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

**Components to Create:**
- `StatsCard.tsx` - Reusable stat card with trend indicator
- `QuickActionsPanel.tsx` - Grid of quick action buttons
- `RecentTasksList.tsx` - List of recent tasks with status
- `ActivityFeed.tsx` - Real-time activity log

**API Endpoints Needed:**
- `GET /api/v1/dashboard/stats` - Dashboard statistics
- `GET /api/v1/tasks?limit=5&sort=updated_at` - Recent tasks
- `WebSocket /ws/activity` - Real-time activity feed

---

#### 1.2 Resource Explorer Component

```
┌─────────────────────────────────────┐
│ Resource Explorer                   │
├─────────────────────────────────────┤
│ Platform: [Databricks ▼]            │
│ ┌─────────────────────────────────┐ │
│ │ 🔽 main (catalog)               │ │
│ │   🔽 default (schema)           │ │
│ │     📄 users                    │ │
│ │     📄 orders                   │ │
│ │     📄 products                 │ │
│ │   🔽 analytics (schema)         │ │
│ │     📄 reports                  │ │
│ └─────────────────────────────────┘ │
│ ┌─────────────────────────────────┐ │
│ │ Table: users                    │ │
│ │ ┌─────────┬──────────┬────────┐ │ │
│ │ │ Column  │ Type     │ Null   │ │ │
│ │ ├─────────┼──────────┼────────┤ │ │
│ │ │ id      │ BIGINT   │ NO     │ │ │
│ │ │ name    │ STRING   │ YES    │ │ │
│ │ │ email   │ STRING   │ NO     │ │ │
│ │ └─────────┴──────────┴────────┘ │ │
│ │ [Preview] [Generate Query]      │ │
│ └─────────────────────────────────┘ │
└─────────────────────────────────────┘
```

**Components to Create:**
- `ResourceExplorer.tsx` - Main explorer container
- `CatalogTree.tsx` - Tree view of catalogs/schemas/tables
- `TableSchemaViewer.tsx` - Table column viewer
- `DataPreview.tsx` - Sample data preview

**API Endpoints Needed:**
- `GET /api/v1/resources/catalogs` - List catalogs
- `GET /api/v1/resources/catalogs/{id}/schemas` - List schemas
- `GET /api/v1/resources/schemas/{id}/tables` - List tables
- `GET /api/v1/resources/tables/{id}` - Table details
- `GET /api/v1/resources/tables/{id}/preview` - Data preview

---

### Phase 2: Task Management Enhancement

#### 2.1 Task List Page (`/app/tasks/page.tsx`)

```
┌─────────────────────────────────────────────────────────┐
│ Tasks                              [+ New Task]         │
├─────────────────────────────────────────────────────────┤
│ Filters:                                                │
│ Status: [All ▼] Agent: [All ▼] Env: [All ▼] Date: [↔]  │
│ Search: [________________] [🔍]                        │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ □ Task         Agent      Status    Environment    │ │
│ ├─────────────────────────────────────────────────────┤ │
│ │ □ ETL Pipeline developer   ✓ COMPLETED SANDBOX    │ │
│ │ □ Data Ingest  ingestion   ◐ RUNNING  SANDBOX     │ │
│ │ □ SQL Report   adb-sql     ⏳ PENDING  PRODUCTION  │ │
│ │ □ Job Schedule scheduler   ❌ FAILED   SANDBOX     │ │
│ └─────────────────────────────────────────────────────┘ │
│ [Bulk Execute] [Bulk Cancel] [Export]                   │
│ ────────────────────────────────────────────────────    │
│ Showing 1-25 of 234                         [1][2][3]→  │
└─────────────────────────────────────────────────────────┘
```

**Components to Create:**
- `TaskFilters.tsx` - Filter controls
- `TaskTable.tsx` - Sortable/filterable table
- `TaskStatusBadge.tsx` - Status indicator
- `BulkActions.tsx` - Bulk operation buttons
- `Pagination.tsx` - Page navigation

---

#### 2.2 Task Detail Page with Execution Timeline

```
┌─────────────────────────────────────────────────────────┐
│ Task: Generate ETL Pipeline                    [Execute]│
├─────────────────────────────────────────────────────────┤
│ Status: RUNNING ████░░░░░░ 60%     Agent: developer     │
│ Environment: SANDBOX         Created: 2024-01-15 10:30  │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Execution Timeline                                  │ │
│ │                                                     │ │
│ │ ● SUBMITTED     ─── 10:30:00                       │ │
│ │ ● PARSING       ─── 10:30:02                       │ │
│ │ ● PARSED        ─── 10:30:05                       │ │
│ │ ● PLANNING      ─── 10:30:08                       │ │
│ │ ● AGENT_ASSIGNED─── 10:30:10  → developer          │ │
│ │ ● IN_DEVELOPMENT─── 10:30:12                       │ │
│ │ ◐ IN_VALIDATION ─── 10:30:45  (running...)         │ │
│ │ ○ OPTIMIZATION  ─── pending                        │ │
│ │ ○ APPROVAL      ─── pending                        │ │
│ │ ○ DEPLOYED      ─── pending                        │ │
│ │ ○ COMPLETED     ─── pending                        │ │
│ └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ [Code] [Validation] [Artifacts] [Logs]                  │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Generated Code                                     │ │
│ │ ┌───────────────────────────────────────────────┐ │ │
│ │ │ 1│ from pyspark.sql import SparkSession       │ │ │
│ │ │ 2│ from pyspark.sql.functions import col      │ │ │
│ │ │ 3│                                            │ │ │
│ │ │ 4│ spark = SparkSession.builder.getOrCreate() │ │ │
│ │ │ 5│                                            │ │ │
│ │ │ 6│ df = spark.read.table('main.sales.orders') │ │ │
│ │ └───────────────────────────────────────────────┘ │ │
│ │ [Copy] [Download] [Edit & Re-run]                  │ │
│ └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

**Components to Create:**
- `ExecutionTimeline.tsx` - Visual state progression
- `CodeViewer.tsx` - Syntax-highlighted code viewer
- `ValidationReport.tsx` - Validation results display
- `ArtifactGallery.tsx` - List/download artifacts
- `LogViewer.tsx` - Execution logs

---

### Phase 3: Quick Actions & Chat Interface

#### 3.1 Quick Actions Panel

```
┌─────────────────────────────────────┐
│ Quick Actions                       │
├─────────────────────────────────────┤
│ ┌─────────┐ ┌─────────┐ ┌─────────┐│
│ │ 📋      │ │ 📁      │ │ 👁️      ││
│ │List     │ │List     │ │Preview  ││
│ │Tables   │ │Schemas  │ │Table    ││
│ └─────────┘ └─────────┘ └─────────┘│
│ ┌─────────┐ ┌─────────┐ ┌─────────┐│
│ │ 📝      │ │ 🔍      │ │ 📊      ││
│ │Get      │ │Run SQL  │ │Create   ││
│ │Schema   │ │Query    │ │Pipeline ││
│ └─────────┘ └─────────┘ └─────────┘│
│                                     │
│ Selected: Preview Table             │
│ ┌─────────────────────────────────┐ │
│ │ Catalog: [main ▼]               │ │
│ │ Schema:  [default ▼]            │ │
│ │ Table:   [users ▼]              │ │
│ │                                 │ │
│ │ [Execute]  [Cancel]             │ │
│ └─────────────────────────────────┘ │
└─────────────────────────────────────┘
```

**Components to Create:**
- `QuickActionsPanel.tsx` - Quick action selector
- `ActionConfigForm.tsx` - Dynamic form for action config
- `ActionResult.tsx` - Display action results

---

#### 3.2 Natural Language Task Interface (Chat)

```
┌─────────────────────────────────────────────────────────┐
│ Create Task with Natural Language                       │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ 💬 Describe what you want to do:                   │ │
│ │                                                     │ │
│ │ "Read orders from main.sales.orders, filter by    │ │
│ │  status='completed', and save to main.analytics.  │ │
│ │  completed_orders"                                 │ │
│ │                                                     │ │
│ │ [____________________________] [Send]              │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                         │
│ AI will:                                                │
│ 1. Route to the appropriate agent (developer)          │
│ 2. Generate optimized PySpark code                     │
│ 3. Validate for safety                                 │
│ 4. Request approval if needed                          │
│ 5. Execute on platform                                 │
│                                                         │
│ [Create Task]                                          │
└─────────────────────────────────────────────────────────┘
```

**Components to Create:**
- `ChatInput.tsx` - Natural language input
- `IntentPreview.tsx` - Show parsed intent
- `AgentRecommendation.tsx` - Show recommended agent

**API Endpoints Needed:**
- `POST /api/v1/tasks/parse-intent` - Parse natural language to task

---

### Phase 4: Approval Workflow

#### 4.1 Approval Queue

```
┌─────────────────────────────────────────────────────────┐
│ Approvals                                [3 Pending]    │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Task: Drop staging table                            │ │
│ │ Environment: PRODUCTION                             │ │
│ │ Operation: Destructive (DROP TABLE)                 │ │
│ │ Risk Score: 0.75 (HIGH)                            │ │
│ │ Requested by: john@company.com                      │ │
│ │ Reason: Cleanup old data                            │ │
│ │                                                     │ │
│ │ [View Code] [View Task]                            │ │
│ │                                                     │ │
│ │ [✓ Approve] [✗ Reject] [⏸ Request Info]            │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                         │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Task: Create production schema                      │ │
│ │ ...                                                 │ │
│ └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

**Components to Create:**
- `ApprovalQueue.tsx` - List of pending approvals
- `ApprovalCard.tsx` - Individual approval item
- `ApprovalDecision.tsx` - Approve/reject form
- `RiskIndicator.tsx` - Visual risk score

---

### Phase 5: Real-time Features

#### 5.1 WebSocket Integration

```typescript
// WebSocket connection for real-time updates
interface ActivityEvent {
  type: 'task_created' | 'state_changed' | 'execution_complete' | 'approval_needed';
  task_id: string;
  timestamp: string;
  data: Record<string, any>;
}

// Hook for WebSocket connection
function useActivityFeed() {
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  
  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8000/ws/activity');
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setEvents(prev => [data, ...prev].slice(0, 50));
    };
    return () => ws.close();
  }, []);
  
  return events;
}
```

#### 5.2 Polling Fallback

```typescript
// Fallback polling for environments without WebSocket
function useTaskStatus(taskId: string) {
  const [status, setStatus] = useState<TaskStatus>();
  
  useEffect(() => {
    const interval = setInterval(async () => {
      const response = await fetch(`/api/v1/tasks/${taskId}/status`);
      const data = await response.json();
      setStatus(data);
      
      if (data.is_terminal) {
        clearInterval(interval);
      }
    }, 2000);
    
    return () => clearInterval(interval);
  }, [taskId]);
  
  return status;
}
```

---

## File Structure

```
frontend/src/
├── app/
│   ├── page.tsx                    # Dashboard (enhanced)
│   ├── tasks/
│   │   ├── page.tsx                # Task list (enhanced)
│   │   ├── new/
│   │   │   └── page.tsx            # New task form
│   │   └── [id]/
│   │       └── page.tsx            # Task detail (enhanced)
│   ├── resources/
│   │   └── page.tsx                # Resource explorer (NEW)
│   ├── approvals/
│   │   ├── page.tsx                # Approval queue (enhanced)
│   │   └── [id]/
│   │       └── page.tsx            # Approval detail
│   └── settings/
│       └── page.tsx                # Settings (NEW)
├── components/
│   ├── dashboard/
│   │   ├── StatsCard.tsx
│   │   ├── QuickActionsPanel.tsx
│   │   ├── RecentTasksList.tsx
│   │   └── ActivityFeed.tsx
│   ├── tasks/
│   │   ├── TaskFilters.tsx
│   │   ├── TaskTable.tsx
│   │   ├── TaskStatusBadge.tsx
│   │   ├── ExecutionTimeline.tsx
│   │   └── BulkActions.tsx
│   ├── resources/
│   │   ├── ResourceExplorer.tsx
│   │   ├── CatalogTree.tsx
│   │   ├── TableSchemaViewer.tsx
│   │   └── DataPreview.tsx
│   ├── code/
│   │   ├── CodeViewer.tsx
│   │   └── DiffViewer.tsx
│   ├── approvals/
│   │   ├── ApprovalCard.tsx
│   │   ├── ApprovalQueue.tsx
│   │   └── RiskIndicator.tsx
│   └── ui/
│       ├── Button.tsx
│       ├── Card.tsx
│       ├── Modal.tsx
│       ├── Toast.tsx
│       └── ...
├── hooks/
│   ├── useTaskStatus.ts
│   ├── useActivityFeed.ts
│   ├── useResourceExplorer.ts
│   └── useApprovals.ts
├── api/
│   ├── client.ts
│   └── types.ts
└── lib/
    ├── utils.ts
    └── constants.ts
```

---

## Backend API Endpoints Needed

### New Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/dashboard/stats` | Dashboard statistics |
| GET | `/api/v1/resources/catalogs` | List catalogs |
| GET | `/api/v1/resources/catalogs/{id}/schemas` | List schemas |
| GET | `/api/v1/resources/schemas/{id}/tables` | List tables |
| GET | `/api/v1/resources/tables/{id}` | Table details |
| GET | `/api/v1/resources/tables/{id}/preview` | Data preview |
| POST | `/api/v1/tasks/parse-intent` | Parse natural language |
| GET | `/api/v1/tasks/{id}/status` | Task status (polling) |
| WS | `/ws/activity` | Real-time activity feed |

---

## Implementation Priority

### P0 - Critical (Week 1)
1. Dashboard stats and quick actions
2. Task list with filters
3. Task detail with execution timeline
4. Code viewer component

### P1 - High (Week 2)
1. Resource explorer
2. Approval workflow enhancement
3. Real-time status updates

### P2 - Medium (Week 3-4)
1. Natural language task creation
2. Bulk operations
3. Settings page
4. Notifications

---

## Dependencies

- `@monaco-editor/react` - Code editor
- `@tanstack/react-table` - Advanced tables
- `@xyflow/react` - Flow diagrams (for pipeline visualization)
- `recharts` - Charts for dashboard
- `date-fns` - Date formatting
- `zustand` - State management (optional)

---

## Testing Strategy

1. **Unit Tests** - All components with React Testing Library
2. **Integration Tests** - API client functions
3. **E2E Tests** - Critical user flows with Playwright
4. **Visual Regression** - Storybook for component documentation
