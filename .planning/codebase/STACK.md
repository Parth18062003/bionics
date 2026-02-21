# Technology Stack

**Analysis Date:** 2026-02-22

## Languages

**Primary:**
- Python 3.11+ - Backend API, agents, orchestration, integrations
- TypeScript 5.x - Frontend UI (Next.js application)

## Runtime

**Backend:**
- Python 3.11+ with uvicorn ASGI server
- Async/await throughout (asyncio, asyncpg, httpx)

**Frontend:**
- Node.js (version not specified, inferred from Next.js 16)
- npm package manager (package-lock.json present)

## Frameworks

**Backend:**
- FastAPI >=0.115.0 - ASGI web framework with OpenAPI generation
- Pydantic >=2.10.0 - Data validation and settings management
- SQLAlchemy >=2.0.0 (async mode) - ORM with async support
- LangGraph >=0.2.0 - Agent orchestration framework

**Frontend:**
- Next.js 16.1.6 - React framework with App Router
- React 19.2.3 - UI library

**Testing:**
- pytest >=8.3.0 - Test framework
- pytest-asyncio >=0.24.0 - Async test support
- testcontainers >=4.9.0 - Docker-based integration testing
- coverage >=7.6.0 - Code coverage

## Key Dependencies

**Core Backend:**
- `uvicorn[standard]` >=0.34.0 - ASGI server with HTTP/2 support
- `asyncpg` >=0.30.0 - Async PostgreSQL driver
- `alembic` >=1.14.0 - Database migrations
- `pydantic-settings` >=2.7.0 - Environment-based configuration
- `structlog` >=24.4.0 - Structured logging
- `python-dotenv` >=1.0.0 - Environment file loading

**LLM & AI:**
- `openai` >=1.0.0 - OpenAI SDK (Azure OpenAI compatible)
- `tiktoken` >=0.5.0 - Token counting for LLM prompts
- `chromadb` >=0.4.0 - Vector database for memory entities

**Data Platform Integrations:**
- `databricks-sdk` >=0.20.0 - Databricks API client
- `msal` >=1.25.0 - Microsoft Authentication Library (for Fabric)

**HTTP Client:**
- `httpx` >=0.28.0 - Async HTTP client for external APIs

## Build Tools

**Backend:**
- setuptools >=75.0 - Build backend
- pip - Package installer
- No build step required (Python runtime)

**Frontend:**
- Next.js built-in bundler (Turbopack in Next.js 16)
- TypeScript compiler (tsc)

## Configuration

**Environment Variables (AADAP_ prefix):**
All configuration is environment-driven via `pydantic-settings`. Key variables:

| Variable | Purpose | Default |
|----------|---------|---------|
| `AADAP_ENVIRONMENT` | deployment environment | `development` |
| `AADAP_DATABASE_URL` | PostgreSQL connection string | Required |
| `AADAP_AZURE_OPENAI_API_KEY` | Azure OpenAI API key | Required for LLM |
| `AADAP_AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint | Required for LLM |
| `AADAP_DATABRICKS_HOST` | Databricks workspace URL | Required for Databricks |
| `AADAP_FABRIC_TENANT_ID` | Azure tenant for Fabric | Required for Fabric |
| `AADAP_FABRIC_CLIENT_ID` | Service principal client ID | Required for Fabric |
| `AADAP_FABRIC_CLIENT_SECRET` | Service principal secret | Required for Fabric |

**Configuration Files:**
- `pyproject.toml` - Python project metadata, dependencies, pytest config
- `requirements.txt` - Pinned dependencies for deployment
- `.env.example` - Template for environment configuration
- `alembic.ini` - Database migration configuration
- `frontend/tsconfig.json` - TypeScript configuration
- `frontend/next.config.ts` - Next.js configuration

## Platform Requirements

**Development:**
- Python 3.11+
- Node.js 18+ (for Next.js 16)
- Docker (for testcontainers, local PostgreSQL)
- PostgreSQL 16 with pgvector extension

**Production:**
- PostgreSQL 16+ with pgvector extension
- Azure OpenAI deployment (GPT-4 or equivalent)
- Databricks workspace (optional, for Databricks execution)
- Microsoft Fabric workspace (optional, for Fabric execution)

---

*Stack analysis: 2026-02-22*
