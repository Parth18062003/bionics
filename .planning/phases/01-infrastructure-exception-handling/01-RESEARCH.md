# Phase 1: Infrastructure & Exception Handling - Research

**Researched:** 2026-02-22
**Domain:** Database models, exception handling, async patterns
**Confidence:** HIGH

## Summary

Phase 1 adds three new database models (TaskLog, CostRecord, PlatformConnection) and fixes exception handling across core execution paths. The codebase already has established patterns for all these concerns—research focused on understanding existing conventions to ensure consistency.

**Key discoveries:**
1. **Exception hierarchy already exists** — ~20 custom exceptions scattered across modules following `class XError(Exception)` pattern with context parameters
2. **Structlog already configured** — JSON logging with correlation IDs, accessed via `get_logger(__name__)`
3. **SQLAlchemy async pattern established** — AsyncSession, UUID primary keys, JSONB metadata, UTC timestamps
4. **Sync wrapper problem localized** — `approval_engine.py` has 6 ThreadPoolExecutor wrappers that need removal

**Primary recommendation:** Extend existing patterns rather than introduce new ones. Create `aadap/core/exceptions.py` to centralize the taxonomy, add models to `aadap/db/models.py`, and use standard Alembic migration.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **Hierarchy:** Hybrid approach — category-based exceptions (OrchestratorError, AgentError, IntegrationError, etc.) with a severity property on each
- **API layer behavior:** Include context in responses (error code + context), but hide stack traces in production environment
- **Context capture:** Technical details only — full traceback, error code, timestamp
- **Identifiers:** Include task_id, agent_id, correlation_id for tracing (from existing structured logging)

### Claude's Discretion

- **Severity levels:** Planner to determine appropriate severity levels based on existing codebase patterns and AADAP blueprint invariants
- **Exact exception class names:** Match existing patterns in codebase
- **Logging format:** Follow existing structlog patterns in `aadap/core/logging.py`
- **Migration rollback strategy:** Standard Alembic approach

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INFRA-01 | TaskLog database model stores structured logs with task_id, timestamp, level, message, correlation_id | Follow existing model pattern in `aadap/db/models.py` — UUID PK, task_id FK, indexed columns |
| INFRA-02 | CostRecord database model stores token usage and costs with task_id, agent_type, tokens_in, tokens_out, cost_usd | Same model pattern — add agent_type enum, decimal for cost_usd |
| INFRA-03 | PlatformConnection database model stores Databricks/Fabric connection configs securely | Use `SecretStr` pattern from `config.py`, encrypt secrets at rest |
| INFRA-04 | Remove hardcoded credentials from config.py, use SecretStr placeholders | Replace default values with placeholders, validate at runtime |
| INFRA-05 | Alembic migration for new database models | Follow `alembic/versions/002_*.py` pattern |
| EXCPT-01 | Replace bare `except Exception` in orchestrator/graph.py with specific exception types | 6 locations identified — use `OrchestratorError` category |
| EXCPT-02 | Replace bare `except Exception` in orchestrator/graph_executor.py with specific exception types | 5 locations identified — use `OrchestratorError` category |
| EXCPT-03 | Replace bare `except Exception` in services/execution.py with specific exception types | Multiple locations — use `ExecutionError` category |
| EXCPT-04 | Add logging to empty `pass` statements in agents/adapters/databricks_adapter.py | Line 304 — add `logger.debug()` for invalid task_id fallback |
| EXCPT-05 | Add logging to empty `pass` statements in agents/adapters/fabric_adapter.py | Line 309 — add `logger.debug()` for invalid task_id fallback |
| EXCPT-06 | Add logging to empty `pass` statements in agents/base.py | Line 293 — `register_tools()` no-op, document as intentional |
| EXCPT-07 | Remove ThreadPoolExecutor sync wrappers in safety/approval_engine.py, standardize on async | 6 sync methods (lines 309-338, 670-777) — remove, update callers |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy | 2.0+ | Async ORM | Already in use — AsyncSession, declarative models |
| Alembic | 1.14+ | Migrations | Already configured — 2 migrations exist |
| Pydantic | 2.10+ | Settings/validation | Already in use — BaseSettings, SecretStr |
| structlog | 24.4+ | Structured logging | Already configured — JSON output, correlation IDs |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| asyncpg | 0.30+ | PostgreSQL async driver | Already in use via SQLAlchemy |
| pydantic-settings | 2.7+ | Environment config | Already in use for Settings class |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Central exceptions module | Keep exceptions in modules | Centralized = easier imports, discoverability |
| Custom severity enum | Use logging levels | Severity is for error taxonomy, not log level |

**Installation:**
No new packages required. All dependencies already in `requirements.txt`.

## Architecture Patterns

### Recommended Project Structure

Follow existing patterns:

```
aadap/
├── core/
│   ├── exceptions.py      # NEW: Centralized exception taxonomy
│   ├── config.py          # MODIFY: Remove hardcoded credentials
│   └── logging.py         # KEEP: Already correct
├── db/
│   ├── models.py          # EXTEND: Add TaskLog, CostRecord, PlatformConnection
│   └── session.py         # KEEP: Already async
├── orchestrator/
│   ├── graph.py           # FIX: Replace bare except
│   └── graph_executor.py  # FIX: Replace bare except
├── services/
│   └── execution.py       # FIX: Replace bare except
├── agents/
│   ├── base.py            # FIX: Add logging to pass
│   └── adapters/
│       ├── databricks_adapter.py  # FIX: Add logging to pass
│       └── fabric_adapter.py      # FIX: Add logging to pass
├── safety/
│   └── approval_engine.py # FIX: Remove sync wrappers
alembic/versions/
└── 003_add_infra_models.py  # NEW: Migration
```

### Pattern 1: SQLAlchemy Async Model

**What:** Async-compatible SQLAlchemy model with UUID, timestamps, JSONB metadata
**When to use:** All new database entities
**Example:**
```python
class TaskLog(Base):
    __tablename__ = "task_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    level: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        Index("ix_task_logs_task_id", "task_id"),
        Index("ix_task_logs_created_at", "created_at"),
    )
```

### Pattern 2: Exception with Context and Severity

**What:** Category-based exceptions with severity property, following existing codebase pattern
**When to use:** All new exceptions
**Example:**
```python
from enum import StrEnum

class ErrorSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class AADAPError(Exception):
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    error_code: str = "AADAP_ERROR"

    def __init__(self, message: str, *, task_id: str | None = None,
                 agent_id: str | None = None, correlation_id: str | None = None):
        self.task_id = task_id
        self.agent_id = agent_id
        self.correlation_id = correlation_id
        super().__init__(message)

class OrchestratorError(AADAPError):
    error_code = "ORCHESTRATOR_ERROR"

class GraphExecutionError(OrchestratorError):
    severity = ErrorSeverity.HIGH
    error_code = "GRAPH_EXECUTION_ERROR"
```

### Pattern 3: Structured Logging

**What:** Use existing structlog pattern with event name and key-value pairs
**When to use:** All new log statements
**Example:**
```python
from aadap.core.logging import get_logger

logger = get_logger(__name__)

# Good — structured with event name
logger.error(
    "graph.execution_failed",
    task_id=str(task_id),
    error_code=exc.error_code,
    error=str(exc),
)

# Bad — unstructured
logger.error(f"Graph execution failed for task {task_id}: {exc}")
```

### Anti-Patterns to Avoid

- **Bare `except Exception`:** Silent failures, loses error context — use specific types
- **Empty `pass` in except:** Swallows errors — at minimum, log debug
- **ThreadPoolExecutor in async code:** Thread exhaustion, deadlocks — use native async
- **Hardcoded credentials in defaults:** Security risk — use placeholders, validate at runtime

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Exception hierarchy | Custom base classes | Existing pattern from `approval_engine.py`, `base.py` | Consistency, already ~20 exceptions |
| Secret encryption | Custom crypto | PostgreSQL pgcrypto or app-level encryption | Security, key management |
| Async session management | Custom connection pool | `get_db_session()` from `aadap/db/session.py` | Already handles commit/rollback |
| Logging format | Custom JSON | `structlog` via `get_logger(__name__)` | Correlation IDs auto-injected |

**Key insight:** The codebase has mature patterns for all infrastructure concerns. The work is extension and cleanup, not new architecture.

## Common Pitfalls

### Pitfall 1: Bare Exception Handlers
**What goes wrong:** Catches `KeyboardInterrupt`, `SystemExit`, and masks real errors
**Why it happens:** Quick debugging that became permanent
**How to avoid:** Always specify exception type: `except ValueError as exc:`
**Warning signs:** `except Exception:` or bare `except:` without re-raise

### Pitfall 2: Sync Wrappers in Async Code
**What goes wrong:** Thread pool exhaustion under load, potential deadlocks
**Why it happens:** Legacy sync API that wasn't migrated
**How to avoid:** Remove sync wrappers, update all callers to use async
**Warning signs:** `ThreadPoolExecutor`, `asyncio.run()` inside async context

### Pitfall 3: Missing Indexes on Foreign Keys
**What goes wrong:** Full table scans on JOINs, slow queries
**Why it happens:** Forgetting to add index after creating FK
**How to avoid:** Always create index on FK columns in migration
**Warning signs:** `EXPLAIN ANALYZE` shows sequential scan

### Pitfall 4: SecretStr Direct Access
**What goes wrong:** `str(secret)` or `f"{secret}"` exposes secret in logs
**Why it happens:** Pydantic's SecretStr requires explicit `.get_secret_value()`
**How to avoid:** Always use `.get_secret_value()` for actual use, never log
**Warning signs:** SecretStr in f-string or print

## Code Examples

### Exception Handler Replacement

From `graph.py:571-582` (current):
```python
except Exception as exc:
    logger.error(
        "graph.run_failed",
        task_id=str(task_id),
        error=str(exc),
    )
    return {
        "task_id": str(task_id),
        "final_state": "CANCELLED",
        "success": False,
        "error": str(exc),
    }
```

To (fixed):
```python
except (GraphExecutionError, AgentLifecycleError) as exc:
    logger.error(
        "graph.run_failed",
        task_id=str(task_id),
        error_code=exc.error_code,
        severity=exc.severity.value,
        error=str(exc),
    )
    return {
        "task_id": str(task_id),
        "final_state": "CANCELLED",
        "success": False,
        "error_code": exc.error_code,
        "error": str(exc),
    }
except Exception as exc:
    logger.exception(
        "graph.run_unexpected_error",
        task_id=str(task_id),
        error=str(exc),
    )
    raise
```

### PlatformConnection Model with Encrypted Secrets

```python
from cryptography.fernet import Fernet
from aadap.core.config import get_settings

class PlatformConnection(Base):
    __tablename__ = "platform_connections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)  # databricks/fabric
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False)  # Encrypted
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    def get_config(self) -> dict:
        settings = get_settings()
        fernet = Fernet(settings.encryption_key.get_secret_value())
        return json.loads(fernet.decrypt(self.config.encode()).decode())
```

### Removing Sync Wrapper

From `approval_engine.py:670-692` (current):
```python
def approve_sync(self, approval_id, decided_by, reason=None):
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, self.approve(...))
            return future.result()
    else:
        return asyncio.run(self.approve(...))
```

To (remove entirely):
```python
# DELETE approve_sync, reject_sync, check_expired_sync, get_record_sync, enforce_approval_sync
# UPDATE ALL CALLERS to use async versions
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Sync database | Async SQLAlchemy 2.0 | Initial | Non-blocking I/O |
| Print debugging | Structured logging (structlog) | Initial | Searchable logs, correlation |
| Bare exceptions | Typed exceptions with context | This phase | Debugging, error handling |
| ThreadPoolExecutor | Native async | This phase | Performance, simplicity |

**Deprecated/outdated:**
- `redis_*` config fields in `config.py:66-71`: Marked deprecated, retained for compatibility — remove in v2.0
- Sync wrappers in `approval_engine.py`: Remove in this phase

## Open Questions

1. **Encryption key for PlatformConnection secrets**
   - What we know: `SecretStr` prevents logging exposure
   - What's unclear: Should secrets be encrypted at rest in database?
   - Recommendation: Use application-level encryption (Fernet) with key from environment

2. **Migration order for new models**
   - What we know: 3 new models, 1 migration
   - What's unclear: Should this be one migration or three?
   - Recommendation: Single migration for all infrastructure models — easier rollback

3. **Severity level granularity**
   - What we know: User wants severity on exceptions
   - What's unclear: 4 levels vs 5 levels?
   - Recommendation: Use `LOW | MEDIUM | HIGH | CRITICAL` matching existing `RiskLevel` pattern

## Sources

### Primary (HIGH confidence)
- `aadap/db/models.py` — Existing model patterns (UUID, JSONB, timestamps, indexes)
- `aadap/core/logging.py` — Structlog configuration (JSON output, correlation IDs)
- `aadap/safety/approval_engine.py` — Exception pattern (context parameters, inheritance)
- `alembic/versions/002_add_risk_level_and_resources.py` — Migration pattern

### Secondary (MEDIUM confidence)
- `requirements.txt` — Version constraints (SQLAlchemy 2.0+, Pydantic 2.10+, structlog 24.4+)
- `.planning/codebase/CONCERNS.md` — Tech debt inventory (78 bare excepts, 22 empty pass)

### Tertiary (LOW confidence)
- None — all findings verified against codebase

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — All libraries already in use, versions confirmed in requirements.txt
- Architecture: HIGH — Existing patterns well-documented in codebase
- Pitfalls: HIGH — Specific file:line references from CONCERNS.md

**Research date:** 2026-02-22
**Valid until:** 30 days (stable stack, internal codebase)
