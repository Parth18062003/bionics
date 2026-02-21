# External Integrations

**Analysis Date:** 2026-02-22

## APIs & External Services

**Azure OpenAI (LLM Provider):**
- Purpose: LLM completions and embeddings for agent operations
- SDK: `openai` package (AsyncAzureOpenAI client)
- Client: `aadap/integrations/llm_client.py` - `AzureOpenAIClient` class
- Auth: API key via `AADAP_AZURE_OPENAI_API_KEY`
- Endpoint: `AADAP_AZURE_OPENAI_ENDPOINT`
- Models: GPT-4o (completions), text-embedding-ada-002 (embeddings)

**Databricks:**
- Purpose: SQL and Python code execution, data pipelines
- SDK: `databricks-sdk` package
- Client: `aadap/integrations/databricks_client.py` - `DatabricksClient` class
- Auth: CLI credentials (`databricks auth login`)
- Features:
  - SQL execution via SQL Warehouse (Statement Execution API)
  - Python execution via Compute Cluster (Command Execution API)
  - Resource management (jobs, notebooks, pipelines)

**Microsoft Fabric:**
- Purpose: Notebook execution, Lakehouse SQL, pipeline orchestration
- SDK: `msal` for authentication, REST APIs via `httpx`
- Client: `aadap/integrations/fabric_client.py` - `FabricClient` class
- Auth: Service Principal Authentication (OAuth2 client_credentials flow)
- Features:
  - Notebook execution via Fabric REST API
  - Lakehouse SQL execution via SQL endpoint
  - Item job submission (Spark jobs, notebooks, pipelines)

## Data Storage

**Primary Database:**
- Type: PostgreSQL 16 with pgvector extension
- Connection: `AADAP_DATABASE_URL` (asyncpg driver)
- ORM: SQLAlchemy 2.0 async mode
- Client: `aadap/db/session.py` - async session management
- Migrations: Alembic (`alembic/versions/`)

**Database Tables:**
- `tasks` - Primary work units with 25-state lifecycle
- `state_transitions` - Immutable event sourcing
- `artifacts` - Code, config, and documents
- `approval_requests` - Human-in-the-loop decisions
- `executions` - Code execution records
- `audit_events` - Full audit trail
- `platform_resources` - External platform resource metadata

**Vector Store:**
- Type: ChromaDB (local/embedded)
- Client: `aadap/memory/vector_store.py` - `VectorStore` class
- Purpose: Tier 2 memory entities with similarity search
- Minimum similarity threshold: 0.85 (INV-08)

**In-Memory Store:**
- Type: Process-local in-memory key-value store
- Client: `aadap/core/memory_store.py` - `MemoryStoreClient` class
- Purpose: Working memory, checkpoints, token tracking, sessions
- Namespaces: `wm` (working memory), `cp` (checkpoints), `tt` (token tracking), `sess` (sessions)

## Authentication & Identity

**Backend API:**
- No authentication currently implemented
- CORS middleware allows `localhost:3000` for development
- Correlation ID tracking via `X-Correlation-ID` header

**External Services:**
- Databricks: CLI-based authentication (`databricks auth login`)
- Microsoft Fabric: Service Principal Authentication (SPA)
  - Tenant ID, Client ID, Client Secret via environment
  - Token caching and auto-refresh handled by MSAL

**Frontend:**
- No authentication layer
- API client adds correlation ID to all requests
- API base URL: `NEXT_PUBLIC_API_URL` or `http://localhost:8000`

## Monitoring & Observability

**Logging:**
- Framework: `structlog` for structured JSON logging
- Configuration: `aadap/core/logging.py`
- Log level: `AADAP_LOG_LEVEL` (default: INFO)
- Format: JSON or console (configurable via `AADAP_LOG_FORMAT`)

**Tracing:**
- Correlation IDs for request tracking
- Implementation: `aadap/core/tracing.py`
- Middleware: `aadap/core/middleware.py` - `CorrelationMiddleware`

**Error Tracking:**
- No external error tracking service configured

## CI/CD & Deployment

**Containerization:**
- `docker-compose.yml` - Local development PostgreSQL
- Image: `pgvector/pgvector:pg16`

**Hosting:**
- Not specified (infrastructure not yet defined)

**CI Pipeline:**
- Not configured

## Environment Configuration

**Required Environment Variables:**

| Category | Variables |
|----------|-----------|
| Core | `AADAP_DATABASE_URL`, `AADAP_ENVIRONMENT` |
| LLM | `AADAP_AZURE_OPENAI_API_KEY`, `AADAP_AZURE_OPENAI_ENDPOINT`, `AADAP_AZURE_OPENAI_DEPLOYMENT_NAME` |
| Databricks | `AADAP_DATABRICKS_HOST`, `AADAP_DATABRICKS_WAREHOUSE_ID` or `AADAP_DATABRICKS_CLUSTER_ID` |
| Fabric | `AADAP_FABRIC_TENANT_ID`, `AADAP_FABRIC_CLIENT_ID`, `AADAP_FABRIC_CLIENT_SECRET`, `AADAP_FABRIC_WORKSPACE_ID` |

**Secrets Management:**
- Environment variables (`.env` file for development)
- `pydantic.SecretStr` for sensitive values in config

## Webhooks & Callbacks

**Incoming Webhooks:**
- None currently implemented

**Outgoing Webhooks:**
- None currently implemented

**Callback Pattern:**
- Job status polling for Databricks/Fabric executions
- No push notifications or webhooks from external services

## Third-Party Services

**Payment/Analytics:**
- None configured

**Email/Notifications:**
- `aadap/services/notifications.py` exists but not yet integrated with external providers

---

*Integration audit: 2026-02-22*
