# AADAP — Sample Tasks for End-to-End Testing

This document provides step-by-step sample tasks you can run through the AADAP UI to demonstrate end-to-end functionality.

## Prerequisites

1. **Start the Backend API**:
   ```bash
   cd d:/bionics
   python -m uvicorn aadap.main:app --reload --port 8000
   ```

2. **Start the Frontend**:
   ```bash
   cd d:/bionics/frontend
   npm run dev
   ```

3. **Access the UI**: Open http://localhost:3000 in your browser

---

## Task 1: Quick Connectivity Test (SQL)

A minimal test to verify Databricks connectivity without code generation.

### Steps:
1. Navigate to http://localhost:3000
2. Click on "Microsoft Azure" card to enter the dashboard
3. Click "New Task" or navigate to `/tasks/new`
4. Fill in the form:
   - **Title**: `Test Query - Current Timestamp`
   - **Description**: 
     ```
     Execute a simple SQL query to verify Databricks connectivity.
     Run: SELECT current_timestamp() as test_time, 1+1 as calculation
     ```
   - **Environment**: Sandbox
   - **Priority**: 0
5. Toggle "Execute Immediately" to ON
6. Click "Submit & Execute"

### Expected Outcome:
- Task created in SUBMITTED state
- Routes through Orchestrator → Developer Agent → Validation Agent
- Code generated for Databricks SQL Warehouse
- Executed on connected Databricks instance
- Results displayed in the task detail page

---

## Task 2: List Tables (Direct Execution - No Code Gen)

This task uses the LIST mode which bypasses code generation entirely.

### Steps:
1. Navigate to `/tasks/new`
2. Fill in:
   - **Title**: `List Tables in Main Catalog`
   - **Description**: `List all tables in the main.catalog schema`
   - **Environment**: Sandbox
3. Select the following from the capability config (if shown):
   - **Operation Type**: `list_tables`
   - **Catalog**: `main`
   - **Schema**: (leave empty for all schemas)
4. Click "Submit Task"

### Expected Outcome:
- Task executes directly via Databricks/Fabric API
- No LLM code generation required
- Fast response with table list
- Results shown in artifacts panel

---

## Task 3: Ingestion Pipeline (Code Generation)

A complete ingestion task that demonstrates code generation.

### Steps:
1. Navigate to `/marketplace` to select an agent
2. Click on "Databricks Ingestion Agent" or similar
3. You'll be redirected to `/tasks/new?agent=ingestion-databricks`
4. Fill in:
   - **Title**: `Ingest Customer Data from ADLS`
   - **Description**:
     ```
     Create a batch ingestion pipeline to load customer CSV files from 
     ADLS location: abfss://raw-data@storage.dfs.core.windows.net/customers/
     
     Target table: main.raw.customers
     
     Requirements:
     - Use Auto Loader for incremental file discovery
     - Include _ingestion_timestamp metadata column
     - Handle schema evolution
     - Partition by region column if present
     ```
   - **Environment**: Sandbox
5. Configure ingestion options:
   - **Source Type**: `adls_csv`
   - **Target Type**: `delta_lake`
   - **Ingestion Mode**: `Batch`
6. Toggle "Execute Immediately" ON
7. Click "Submit & Execute"

### Expected Outcome:
- Orchestrator routes to IngestionAgent
- Platform-specific code generated (Databricks Auto Loader)
- Validation agent checks for safety issues
- Code displayed in artifacts with explanation
- (If connected) Execution on Databricks cluster

---

## Task 4: ETL Pipeline Transformation

Generate a Delta Live Tables pipeline definition.

### Steps:
1. Navigate to `/tasks/new?agent=etl-databricks`
2. Fill in:
   - **Title**: `Customer Orders Silver Layer ETL`
   - **Description**:
     ```
     Create a DLT pipeline to transform raw customer orders:
     
     Source: main.raw.orders (bronze)
     Target: main.silver.orders (silver)
     
     Transformations:
     - Filter out cancelled orders (status != 'cancelled')
     - Calculate order_total = quantity * unit_price
     - Add _processed_timestamp
     - Deduplicate on order_id using watermark
     
     Quality expectations:
     - order_id must be unique
     - order_total must be positive
     - customer_id must not be null
     ```
   - **Environment**: Sandbox
3. Select:
   - **Pipeline Type**: Delta Live Tables (DLT)
4. Toggle "Execute Immediately" ON
5. Click "Submit & Execute"

### Expected Outcome:
- DLT pipeline Python code generated
- Includes quality expectations (expect/expect_or_drop)
- Shows medallion architecture pattern
- Code reviewable in artifacts

---

## Task 5: Job Scheduling

Create a scheduled job with multiple tasks.

### Steps:
1. Navigate to `/tasks/new?agent=scheduler-databricks`
2. Fill in:
   - **Title**: `Nightly Customer ETL Job`
   - **Description**:
     ```
     Create a multi-task job with the following tasks:
     
     1. ingest_orders - Ingest daily orders from ADLS
     2. transform_orders - Transform to silver layer
     3. aggregate_metrics - Create daily metrics summary
     
     Dependencies: task 2 depends on task 1, task 3 depends on task 2
     ```
   - **Environment**: Sandbox
3. Configure:
   - **Job Type**: Notebook
   - **Cron Expression**: `0 2 * * *` (2 AM daily)
   - **Timezone**: `UTC`
4. Click "Submit Task"

### Expected Outcome:
- Job definition JSON generated
- Includes task DAG with dependencies
- Schedule configuration included
- Ready for Databricks Jobs API submission

---

## Task 6: Governance - Grant Permissions

Request permission grants (requires approval in production).

### Steps:
1. Navigate to `/tasks/new?agent=catalog-databricks`
2. Fill in:
   - **Title**: `Grant Read Access to Analytics Team`
   - **Description**:
     ```
     Grant SELECT permission on main.sales.orders table 
     to the analytics_team group.
     
     Justification: Monthly reporting requires read access.
     ```
   - **Environment**: Production (to test approval workflow)
3. Click "Submit Task"

### Expected Outcome:
- Task created in SUBMITTED state
- Approval request generated (INV-01 governance)
- Shows in `/approvals` queue
- Requires human approval before execution
- Approval workflow demonstrates safety controls

---

## Task 7: Code Optimization

Submit existing code for optimization suggestions.

### Steps:
1. Navigate to `/tasks/new`
2. Fill in:
   - **Title**: `Optimize Customer Query`
   - **Description**:
     ```
     Optimize the following PySpark code for better performance:
     
     ```python
     df1 = spark.read.table('main.sales.orders')
     df2 = spark.read.table('main.catalog.customers')
     result = df1.join(df2, df1.customer_id == df2.id)
     result.write.mode('overwrite').saveAsTable('main.sales.customer_orders')
     ```
     ```
   - **Environment**: Sandbox
3. No agent selection needed - routes to OptimizationAgent
4. Click "Submit Task"

### Expected Outcome:
- Optimization agent analyzes code
- Suggests broadcast join for customers table
- Shows performance improvement estimates
- Provides optimized code with explanations

---

## Task 8: Code Validation (Safety Review)

Submit code for security and safety validation.

### Steps:
1. Navigate to `/tasks/new`
2. Fill in:
   - **Title**: `Validate Pipeline Code`
   - **Description**:
     ```
     Review this code for security and safety issues:
     
     ```python
     password = "hardcoded_secret_123"
     df = spark.read.jdbc(url, table, properties={"user": "admin", "password": password})
     spark.sql("DROP TABLE IF EXISTS main.prod.customers")
     ```
     ```
   - **Environment**: Production
3. Click "Submit Task"

### Expected Outcome:
- Validation agent detects:
  - Hardcoded credentials (BLOCKER)
  - Destructive DROP operation (CRITICAL)
- Risk score close to 1.0
- Recommendation: REJECT
- Remediation steps provided

---

## Quick Actions (One-Click Operations)

The UI provides quick actions that bypass code generation entirely.

### Available Quick Actions:

| Action | Description | Requires Selection |
|--------|-------------|-------------------|
| 📋 List Tables | List all tables in a schema | Schema |
| 📁 List Schemas | List schemas in a catalog | Catalog |
| 🗄️ List Catalogs | List all catalogs/workspaces | None |
| 👁️ Preview Table | Show first 100 rows | Table |
| 📝 Get Table Schema | Get column definitions | Table |
| 📄 List Files | List files in path | Path |
| 🏠 List Lakehouses | List Fabric lakehouses | None |
| 📓 List Notebooks | List workspace notebooks | None |
| ⚡ List Jobs | List jobs/pipelines | None |
| 🔍 Run SQL Query | Execute SQL directly | None |

### Using Quick Actions:
1. Navigate to the dashboard
2. Click on any quick action button
3. Select the required context (catalog/schema/table)
4. Results appear immediately without task creation

---

## Monitoring Task Progress

### Task States:
- **SUBMITTED** → Task received, awaiting processing
- **QUEUED** → Orchestrator has queued the task
- **RUNNING** → Agent is processing
- **COMPLETED** → Successfully finished
- **FAILED** → Execution failed (check logs)
- **AWAITING_APPROVAL** → Waiting for human approval

### Checking Status:
1. Navigate to `/tasks` for the task list
2. Click on any task to see details
3. View the "Events" tab for state transitions
4. Check "Artifacts" tab for generated code/results
5. "Logs" tab shows execution details

---

## Troubleshooting

### Common Issues:

1. **"Agent not found" error**
   - Ensure the agent is registered in the marketplace
   - Check `/marketplace` for available agents

2. **Task stuck in SUBMITTED**
   - Check orchestrator logs
   - Verify LLM client configuration
   - Check token budget settings

3. **Approval not appearing**
   - Ensure environment is PRODUCTION
   - Check approval engine configuration
   - Navigate to `/approvals` directly

4. **Code generation fails**
   - Check LLM API key configuration
   - Verify token budget is sufficient
   - Check agent logs for schema validation errors

---

## API Testing (Alternative to UI)

You can also test directly via API:

```bash
# Create a simple test task
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Query",
    "description": "SELECT current_timestamp()",
    "environment": "SANDBOX",
    "auto_execute": true
  }'

# List tasks
curl http://localhost:8000/api/v1/tasks

# Get task details
curl http://localhost:8000/api/v1/tasks/{task_id}

# Get quick actions
curl http://localhost:8000/api/v1/tasks/quick-actions
```

---

## Expected End-to-End Flow

```
User Request (UI)
      ↓
   FastAPI (/api/v1/tasks)
      ↓
   Orchestrator (graph.create_task)
      ↓
   Intent Parser (parse task type)
      ↓
   Agent Router (select agent)
      ↓
   Agent Execution (generate code)
      ↓
   Validation Agent (safety check)
      ↓
   Approval Engine (if required)
      ↓
   Execution Service (run code)
      ↓
   Artifacts stored
      ↓
   UI displays results