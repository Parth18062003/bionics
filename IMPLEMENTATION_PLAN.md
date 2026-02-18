AADAP Agent Expansion - Implementation Plan
Overview
Expand AADAP from code-generation-only to full-orchestration platform with capability-specific agents supporting both Azure Databricks and Microsoft Fabric.
Key Principle: All changes are additive. No existing functionality should break.
---
Phase 0: Foundation (Read-Only Preparation)
Files to Read Before Starting
- aadap/agents/base.py - understand BaseAgent interface
- aadap/agents/fabric_agent.py - reference for execution-capable agent
- aadap/agents/tools/registry.py - understand ToolDefinition
- aadap/integrations/databricks_client.py - understand client interface
- aadap/integrations/fabric_client.py - understand client interface
- aadap/services/marketplace.py - understand agent catalog structure
- aadap/services/execution.py - understand execution flow
- frontend/src/api/types.ts - understand frontend types
---
Phase 1: Platform Adapters (Backend Infrastructure)
1.1 Create Adapter Interface
File: aadap/agents/adapters/__init__.py
File: aadap/agents/adapters/base.py
Create abstract PlatformAdapter class with methods:
- create_pipeline(definition: dict) -> str
- execute_pipeline(pipeline_id: str) -> dict
- create_job(definition: dict) -> str
- execute_job(job_id: str, params: dict) -> dict
- get_job_status(job_id: str) -> dict
- create_table(schema: dict) -> str
- list_tables() -> list
- create_shortcut(config: dict) -> str
- execute_sql(sql: str) -> dict
1.2 Implement Databricks Adapter
File: aadap/agents/adapters/databricks_adapter.py
Implement DatabricksAdapter(BasePlatformAdapter):
- Use existing DatabricksClient for job operations
- Add methods for: pipelines API, Unity Catalog, SQL execution
- Map adapter methods to Databricks REST API calls
1.3 Expand Fabric Adapter
File: aadap/agents/adapters/fabric_adapter.py
Implement FabricAdapter(BasePlatformAdapter):
- Use existing FabricClient for notebook operations
- Add methods for: pipelines, lakehouse, dataflows, scheduling
- Map adapter methods to Fabric REST API calls
1.4 Register in Factory
File: aadap/agents/__init__.py
Export new adapter classes.
Verification: Run python -c "from aadap.agents.adapters import DatabricksAdapter, FabricAdapter" - should not error.
---
Phase 2: Expanded Tool Definitions
2.1 Create Databricks Tools
File: aadap/agents/tools/databricks_tools.py
Create tools:
- databricks_create_job - Create multi-task job
- databricks_run_job - Execute job
- databricks_get_job_status - Poll status
- databricks_cancel_job - Cancel running job
- databricks_create_pipeline - Create DLT pipeline
- databricks_start_pipeline - Start DLT pipeline
- databricks_create_catalog - Unity Catalog operations
- databricks_create_schema - Schema creation
- databricks_grant_permissions - Permission grants
- databricks_execute_sql - Run SQL on warehouse
Each tool has: name, description, handler, requires_approval, is_destructive
2.2 Expand Fabric Tools
File: aadap/agents/tools/fabric_tools.py (modify existing)
Add tools:
- fabric_create_pipeline - Create Data Factory pipeline
- fabric_run_pipeline - Execute pipeline
- fabric_create_lakehouse - Create lakehouse
- fabric_create_shortcut - OneLake shortcut
- fabric_create_warehouse - Create warehouse
- fabric_create_dataflow - Create Dataflow Gen2
- fabric_run_dataflow - Execute dataflow
- fabric_create_schedule - Job scheduling
- fabric_execute_sql - SQL on warehouse/lakehouse
2.3 Register Tools
File: aadap/agents/tools/__init__.py
Export new tool names and registration functions.
Verification: Run python -c "from aadap.agents.tools.databricks_tools import DATABRICKS_TOOL_NAMES" - should show all tools.
---
Phase 3: Ingestion Agent
3.1 Create Prompt Templates
File: aadap/agents/prompts/ingestion.py
Create PromptTemplate objects:
- BATCH_INGESTION_PROMPT - Auto Loader, Copy Activity, batch files
- STREAMING_INGESTION_PROMPT - Kafka, Event Hubs, streaming tables
- CDC_INGESTION_PROMPT - Change Data Capture patterns
Output schema should include:
{
    "platform": "databricks|fabric",
    "ingestion_type": "batch|streaming|cdc",
    "source": {...},
    "target": {...},
    "code": "generated code",
    "resource_config": {...},
    "checkpoint_location": "...",
    "schedule": {...}
}
3.2 Create Agent
File: aadap/agents/ingestion_agent.py
Create IngestionAgent(BaseAgent):
- Accept platform_adapter: PlatformAdapter in constructor
- Implement _do_execute() with:
  1. Build prompt from task context
  2. Call LLM with ingestion prompt
  3. Parse and validate output
  4. If execution mode: call adapter methods to create resources
  5. Return AgentResult with artifacts
3.3 Register Agent
File: aadap/agents/__init__.py
Export IngestionAgent.
3.4 Add to Marketplace
File: aadap/services/marketplace.py
Add catalog entries:
- ingestion-databricks - Databricks ingestion agent
- ingestion-fabric - Fabric ingestion agent
3.5 Write Tests
File: tests/test_ingestion_agent.py
Test:
- Batch ingestion code generation
- Streaming ingestion code generation
- Execution mode with mock adapter
- Self-correction on schema violation
- Token budget enforcement
Verification: Run pytest tests/test_ingestion_agent.py -v
---
Phase 4: ETL Pipeline Agent
4.1 Create Prompt Templates
File: aadap/agents/prompts/etl_pipeline.py
Create:
- DLT_PIPELINE_PROMPT - Delta Live Tables
- FABRIC_PIPELINE_PROMPT - Data Factory pipelines
- TRANSFORMATION_PROMPT - Pure transformation logic
Output schema:
{
    "platform": "databricks|fabric",
    "pipeline_type": "dlt|workflow|datafactory",
    "transformations": [...],
    "pipeline_definition": {...},
    "notebooks": [...],
    "data_quality_rules": [...],
    "schedule": {...}
}
4.2 Create Agent
File: aadap/agents/etl_pipeline_agent.py
Create ETLPipelineAgent(BaseAgent):
- Generate pipeline definitions
- Generate notebook code for transformations
- Add data quality expectations
- Execute via platform adapter if requested
4.3 Register and Add to Marketplace
Same pattern as Phase 3.
4.4 Write Tests
File: tests/test_etl_pipeline_agent.py
Verification: Run pytest tests/test_etl_pipeline_agent.py -v
---
Phase 5: Job Scheduler Agent
5.1 Create Prompt Templates
File: aadap/agents/prompts/job_scheduler.py
Create:
- JOB_CREATION_PROMPT - Multi-task job definitions
- SCHEDULE_CONFIG_PROMPT - Cron schedules, triggers
- DAG_BUILDER_PROMPT - Task dependency graphs
Output schema:
{
    "platform": "databricks|fabric",
    "job_type": "notebook|spark|pipeline|dbt",
    "job_definition": {
        "name": "...",
        "tasks": [...],
        "schedule": {...},
        "triggers": [...],
        "cluster_spec": {...}
    },
    "job_id": "...|None",
    "created": true|false
}
5.2 Create Agent
File: aadap/agents/job_scheduler_agent.py
Create JobSchedulerAgent(BaseAgent):
- Build job DAG from requirements
- Configure cluster/environment specs
- Set up schedules and triggers
- Create job via adapter
- Return job ID for monitoring
5.3 Register and Add to Marketplace
5.4 Write Tests
File: tests/test_job_scheduler_agent.py
Verification: Run pytest tests/test_job_scheduler_agent.py -v
---
Phase 6: Catalog Agent
6.1 Create Prompt Templates
File: aadap/agents/prompts/catalog.py
Create:
- SCHEMA_DESIGN_PROMPT - Design schemas from requirements
- PERMISSION_GRANT_PROMPT - Generate GRANT statements
Output schema:
{
    "platform": "databricks|fabric",
    "operation": "create|alter|grant|drop",
    "resource_type": "catalog|schema|table|volume|lakehouse",
    "ddl_statements": [...],
    "api_payloads": [...],
    "permissions": [...]
}
6.2 Create Agent
File: aadap/agents/catalog_agent.py
Create CatalogAgent(BaseAgent):
- Design and create schemas
- Manage Unity Catalog / Lakehouse resources
- Handle permissions with approval gates
6.3 Register and Add to Marketplace
6.4 Write Tests
File: tests/test_catalog_agent.py
Verification: Run pytest tests/test_catalog_agent.py -v
---
Phase 7: Enhance Existing Agents
7.1 Enhance ValidationAgent
File: aadap/agents/validation_agent.py
Modify _do_execute():
1. Call SafetyPipeline.evaluate() first (deterministic)
2. Then call LLM for semantic review
3. Merge results
7.2 Enhance OptimizationAgent
File: aadap/agents/optimization_agent.py
Add platform-specific optimization patterns:
- Databricks: Delta Lake, Photon, AQE
- Fabric: V-Order, Z-Order
7.3 Enhance OrchestratorAgent
File: aadap/agents/orchestrator_agent.py
Add capability routing:
- Classify task type (ingestion, etl, job, catalog)
- Route to appropriate capability agent
7.4 Update Tests
Files: tests/test_validation_agent.py, tests/test_optimization_agent.py
Verification: Run pytest tests/ -v -k "validation or optimization"
---
Phase 8: Integration with ExecutionService
8.1 Update ExecutionService
File: aadap/services/execution.py
Modify execute_task():
1. Add _classify_task_type() method
2. Add _get_capability_agent() method
3. Route to appropriate agent based on task type
4. Include optimization phase after validation
5. Handle new artifact types
8.2 Add State Transitions
Ensure state machine handles:
- VALIDATION_PASSED → OPTIMIZATION_PENDING → IN_OPTIMIZATION → OPTIMIZED
8.3 Update Tests
File: tests/test_execution_service.py
Verification: Run pytest tests/test_execution_service.py -v
---
Phase 9: Frontend Updates
9.1 Update Types
File: frontend/src/api/types.ts
Add types:
interface IngestionConfig {
  source_type: string;
  target_type: string;
  ingestion_mode: 'batch' | 'streaming' | 'cdc';
}
interface PipelineConfig {
  pipeline_type: 'dlt' | 'datafactory' | 'workflow';
  transformations: Transformation[];
}
interface JobConfig {
  job_type: 'notebook' | 'spark' | 'pipeline';
  schedule?: ScheduleConfig;
}
9.2 Update Marketplace
File: aadap/services/marketplace.py
Add new agent entries:
- ingestion-databricks - Data Ingestion (Databricks)
- ingestion-fabric - Data Ingestion (Fabric)
- pipeline-databricks - ETL Pipeline (Databricks)
- pipeline-fabric - ETL Pipeline (Fabric)
- scheduler-databricks - Job Scheduler (Databricks)
- scheduler-fabric - Job Scheduler (Fabric)
- catalog-databricks - Unity Catalog Manager
- catalog-fabric - Lakehouse Manager
9.3 Update Task Creation Form
File: frontend/src/app/tasks/new/page.tsx
Add capability-specific configuration options:
- If agent is ingestion type: show source/target fields
- If agent is pipeline type: show transformation options
- If agent is scheduler type: show schedule fields
9.4 Update Task Detail Page
File: frontend/src/app/tasks/[id]/page.tsx
Display new artifact types:
- Pipeline definitions
- Job configurations
- Schedule configurations
- Ingestion configs
9.5 Add New Artifact Views
File: frontend/src/app/artifacts/[taskId]/[id]/page.tsx
Add renderers for:
- pipeline_definition - JSON viewer
- job_config - JSON viewer
- ingestion_config - Summary card
Verification: Run npm run build in frontend/
---
Phase 10: End-to-End Testing
10.1 Create E2E Test Suite
File: tests/e2e/test_capability_agents.py
Test full flows:
1. Create task with ingestion agent
2. Execute and verify artifacts
3. Verify database records
4. Verify frontend API responses
10.2 Integration Test
File: tests/integration/test_full_pipeline.py
Test:
- Task creation → Agent assignment → Code generation → Safety analysis → Execution
Verification: Run pytest tests/e2e/ tests/integration/ -v
---
Execution Order Summary
Phase 1: Platform Adapters (no dependencies)
Phase 2: Expanded Tools (depends on Phase 1)
Phase 3: Ingestion Agent (depends on Phases 1-2)
Phase 4: ETL Pipeline Agent (depends on Phases 1-2)
Phase 5: Job Scheduler Agent (depends on Phases 1-2)
Phase 6: Catalog Agent (depends on Phases 1-2)
Phase 7: Enhance Existing Agents (independent)
Phase 8: ExecutionService Integration (depends on Phases 3-7)
Phase 9: Frontend Updates (depends on Phase 8)
Phase 10: E2E Testing (depends on all phases)
---
Backward Compatibility Checklist
Before each phase, verify:
- [ ] Existing tests still pass
- [ ] Existing API endpoints unchanged
- [ ] Existing frontend pages load
- [ ] No breaking changes to DB models
- [ ] New code is additive only
After each phase:
- [ ] Run pytest tests/ -v - all pass
- [ ] Run npm run build in frontend/ - success
- [ ] Start server and hit /health - returns healthy
---
Files Summary
New Files to Create
| File | Purpose |
|------|---------|
| aadap/agents/adapters/__init__.py | Package init |
| aadap/agents/adapters/base.py | PlatformAdapter interface |
| aadap/agents/adapters/databricks_adapter.py | Databricks implementation |
| aadap/agents/adapters/fabric_adapter.py | Fabric implementation |
| aadap/agents/tools/databricks_tools.py | Databricks tool definitions |
| aadap/agents/prompts/ingestion.py | Ingestion prompts |
| aadap/agents/prompts/etl_pipeline.py | Pipeline prompts |
| aadap/agents/prompts/job_scheduler.py | Scheduler prompts |
| aadap/agents/prompts/catalog.py | Catalog prompts |
| aadap/agents/ingestion_agent.py | Ingestion agent |
| aadap/agents/etl_pipeline_agent.py | ETL pipeline agent |
| aadap/agents/job_scheduler_agent.py | Job scheduler agent |
| aadap/agents/catalog_agent.py | Catalog agent |
| tests/test_ingestion_agent.py | Ingestion tests |
| tests/test_etl_pipeline_agent.py | Pipeline tests |
| tests/test_job_scheduler_agent.py | Scheduler tests |
| tests/test_catalog_agent.py | Catalog tests |
| tests/integration/test_full_pipeline.py | Integration tests |
| tests/e2e/test_capability_agents.py | E2E tests |
Files to Modify
| File | Changes |
|------|---------|
| aadap/agents/__init__.py | Export new agents |
| aadap/agents/tools/__init__.py | Export new tools |
| aadap/agents/tools/fabric_tools.py | Add more tools |
| aadap/agents/validation_agent.py | Add SafetyPipeline integration |
| aadap/agents/optimization_agent.py | Add platform patterns |
| aadap/agents/orchestrator_agent.py | Add capability routing |
| aadap/services/marketplace.py | Add new agent entries |
| aadap/services/execution.py | Route to capability agents |
| frontend/src/api/types.ts | Add new types |
| frontend/src/app/tasks/new/page.tsx | Add config options |
| frontend/src/app/tasks/[id]/page.tsx | Display new artifacts |
| frontend/src/app/artifacts/[taskId]/[id]/page.tsx | New artifact views |