# Testing Patterns

**Analysis Date:** 2026-02-22

## Framework

**Runner:**
- pytest 8.3+ with pytest-asyncio 0.24+
- Config: `pyproject.toml`
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

**Assertion Library:**
- Built-in `assert` statements
- pytest.raises for exception testing

**Run Commands:**
```bash
pytest                           # Run all tests
pytest tests/test_health.py      # Run specific file
pytest -v                        # Verbose output
pytest --cov=aadap               # Coverage report
pytest -k "test_agent"           # Run tests matching pattern
```

## Test File Organization

**Location:**
- Separate `tests/` directory at project root
- Mirrors source structure for module tests
- All tests in `tests/` folder

**Naming:**
- Pattern: `test_<module>.py`
- Examples: `test_models.py`, `test_health.py`, `test_execution_service.py`

**Structure:**
```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── test_health.py           # API health tests
├── test_api_tasks.py        # Task API tests
├── test_api_approvals.py    # Approval API tests
├── test_api_artifacts.py    # Artifact API tests
├── test_models.py           # Model/schema tests
├── test_logging.py          # Logging tests
├── test_agent_base.py       # Agent lifecycle tests
├── test_pool_manager.py     # Agent pool tests
├── test_execution_service.py # Execution service tests
├── test_orchestrator_agent.py
├── test_state_machine.py    # State machine tests
└── ...                      # More test files
```

## Test Structure

### Suite Organization

Tests are organized into classes by functional area:
```python
class TestAgentLifecycle:
    """Lifecycle transition tests."""
    
    async def test_initial_state_is_idle(self, agent: SuccessAgent):
        assert agent.state == AgentState.IDLE
    
    async def test_accept_transitions_to_accepting(self, agent, context):
        result = await agent.accept_task(context)
        assert result is True
        assert agent.state == AgentState.ACCEPTING


class TestLifecycleGuards:
    """Guards against invalid lifecycle transitions."""
    
    async def test_cannot_execute_without_accepting(self, agent, context):
        with pytest.raises(AgentLifecycleError, match="cannot execute"):
            await agent.execute(context)
```

### Async Test Pattern

All async tests use `@pytest.mark.asyncio`:
```python
@pytest.mark.asyncio
async def test_health_returns_200(client):
    """Health endpoint returns 200 with structured response."""
    resp = await client.get("/health")
    assert resp.status_code == 200
```

### Test Docstrings

Tests include descriptive docstrings explaining the test purpose:
```python
@pytest.mark.asyncio
async def test_create_task_persists_capability_contract(test_app, client, mock_task):
    """POST /api/v1/tasks persists normalized capability metadata and config."""
```

## Fixtures

### Shared Fixtures (conftest.py)

```python
# tests/conftest.py

@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """Ensure a fresh Settings instance for each test."""
    from aadap.core.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def settings():
    """Return a settings instance with test defaults."""
    os.environ.setdefault("AADAP_ENVIRONMENT", "development")
    os.environ.setdefault("AADAP_LOG_LEVEL", "DEBUG")
    from aadap.core.config import get_settings
    return get_settings()


@pytest.fixture
def mock_db_engine():
    """Provide a mock async engine for tests that don't need real DB."""
    engine = MagicMock()
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=MagicMock())
    engine.connect = MagicMock(return_value=_async_cm(conn))
    return engine


@pytest.fixture
def mock_memory_store_client():
    """Provide a MemoryStoreClient backed by InMemoryBackend for tests."""
    from aadap.core.memory_store import InMemoryBackend, MemoryStoreClient
    backend = InMemoryBackend()
    return MemoryStoreClient(backend)


@pytest.fixture
async def test_app(mock_db_engine, mock_memory_store_client):
    """FastAPI app instance with mocked DB and in-memory store."""
    import aadap.db.session as sess_mod
    import aadap.core.memory_store as mem_mod

    sess_mod._engine = mock_db_engine
    sess_mod._session_factory = MagicMock()
    mem_mod._memory_store_client = mock_memory_store_client

    with (
        patch.object(sess_mod, "init_db", new_callable=AsyncMock, return_value=mock_db_engine),
        patch.object(sess_mod, "close_db", new_callable=AsyncMock),
        patch.object(mem_mod, "init_memory_store", new_callable=AsyncMock, return_value=mock_memory_store_client),
        patch.object(mem_mod, "close_memory_store", new_callable=AsyncMock),
    ):
        from aadap.main import create_app
        app = create_app()
        yield app

    # Cleanup module state
    sess_mod._engine = None
    sess_mod._session_factory = None
    mem_mod._memory_store_client = None


@pytest.fixture
async def client(test_app):
    """AsyncClient wired to the FastAPI app with mocked dependencies."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
```

### Local Test Fixtures

```python
# tests/test_pool_manager.py

@pytest.fixture
def pool() -> AgentPoolManager:
    return AgentPoolManager(max_pool_size=5)


@pytest.fixture
def agent_dev() -> StubAgent:
    return StubAgent(agent_id="dev-1", agent_type="developer")


@pytest.fixture
def context() -> AgentContext:
    return AgentContext(
        task_id=uuid.uuid4(),
        task_data={"instruction": "test"},
        token_budget=50_000,
        allowed_tools={"read_file"},
    )
```

### Helper Classes

```python
# Helper for async context manager mocking
class _async_cm:
    """Turn an async mock into an async context manager."""
    def __init__(self, value):
        self._value = value
    async def __aenter__(self):
        return self._value
    async def __aexit__(self, *args):
        pass


# Stub implementations for testing
class StubAgent(BaseAgent):
    """Minimal agent for pool testing."""
    async def _do_execute(self, context: AgentContext) -> AgentResult:
        return AgentResult(success=True, output="stub")


class SuccessAgent(BaseAgent):
    """Agent that always succeeds."""
    async def _do_execute(self, context: AgentContext) -> AgentResult:
        return AgentResult(success=True, output="done", tokens_used=42)


class FailingAgent(BaseAgent):
    """Agent that always returns a failed result."""
    async def _do_execute(self, context: AgentContext) -> AgentResult:
        return AgentResult(success=False, error="intentional failure", tokens_used=10)


class ExplodingAgent(BaseAgent):
    """Agent that raises an exception during execution."""
    async def _do_execute(self, context: AgentContext) -> AgentResult:
        raise RuntimeError("boom")
```

## Mocking

### Mock Client Pattern

Mock clients are defined alongside real clients:
```python
# aadap/integrations/llm_client.py

class MockLLMClient(BaseLLMClient):
    """Mock LLM client for testing."""
    
    def __init__(
        self,
        default_response: str = "Mock LLM response",
        default_model: str = "mock-model",
        tokens_per_response: int = 100,
    ) -> None:
        self._default_response = default_response
        self._default_model = default_model
        self._tokens_per_response = tokens_per_response

    async def complete(self, prompt: str, model: str | None = None, max_tokens: int = 4096) -> LLMResponse:
        return LLMResponse(
            content=self._default_response,
            tokens_used=self._tokens_per_response,
            model=model or self._default_model,
        )
```

### unittest.mock Usage

```python
from unittest.mock import AsyncMock, MagicMock, patch

# AsyncMock for async methods
mock_session = AsyncMock()
mock_session.execute = AsyncMock(return_value=mock_result)

# MagicMock for sync objects
mock_engine = MagicMock()
mock_result = MagicMock()
mock_result.scalar_one_or_none.return_value = mock_task

# Patching for isolation
with patch("aadap.api.routes.tasks.create_task", new_callable=AsyncMock, return_value=mock_task.id):
    response = await client.post("/api/v1/tasks", json={...})
```

### Dependency Override Pattern

Override FastAPI dependencies for testing:
```python
def _override_session(mock_result):
    """Create a session dependency override returning mock query results."""
    async def override():
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        yield mock_session
    return override

# Usage in test:
test_app.dependency_overrides[get_session] = _override_session(mock_result)
try:
    response = await client.get("/api/v1/tasks")
finally:
    test_app.dependency_overrides.pop(get_session, None)
```

### Monkeypatch for Settings

```python
def test_create_fails_when_required_config_missing(self, monkeypatch):
    import aadap.services.execution as execution_mod

    monkeypatch.setattr(
        execution_mod,
        "get_settings",
        lambda: SimpleNamespace(
            azure_openai_api_key=None,
            databricks_host=None,
        ),
    )

    with pytest.raises(RuntimeError, match="Missing"):
        ExecutionService.create()
```

## Test Data

### SimpleNamespace for Task Mocks

```python
from types import SimpleNamespace

def _task(*, title: str, description: str, metadata_: dict | None = None, environment: str = "SANDBOX") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        title=title,
        description=description,
        environment=environment,
        metadata_=metadata_ or {},
        token_budget=50_000,
    )

# Usage:
task = _task(
    title="Create ETL",
    description="Create a PySpark ETL pipeline",
    metadata_={"language": "python", "platform": "databricks"},
)
```

### Pydantic Model Instances

```python
@pytest.fixture
def mock_task():
    """Create a mock Task ORM object."""
    return Task(
        id=uuid.uuid4(),
        title="Test Task",
        description="A test task",
        current_state="SUBMITTED",
        priority=1,
        environment="SANDBOX",
        created_by="system",
        token_budget=50_000,
        tokens_used=0,
        retry_count=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
```

## Coverage

**Requirements:** No enforced minimum in configuration

**View Coverage:**
```bash
pytest --cov=aadap --cov-report=html
# Open htmlcov/index.html for detailed report
```

**Package:**
- coverage 7.6+ (in dev dependencies)

## Test Types

### Unit Tests

Unit tests focus on isolated components with mocked dependencies:
```python
def test_exactly_25_authoritative_states():
    """ARCHITECTURE.md mandates exactly 25 states."""
    assert len(TASK_STATES) == 25


def test_task_default_state():
    """New tasks default to SUBMITTED (schema-level default)."""
    col = Task.__table__.c.current_state
    assert col.default.arg == "SUBMITTED"
```

### Integration Tests

Integration tests use the full FastAPI app with mocked infrastructure:
```python
@pytest.mark.asyncio
async def test_create_task_returns_201(test_app, client, mock_task):
    """POST /api/v1/tasks should create a task and return 201."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_task
    test_app.dependency_overrides[get_session] = _override_session(mock_result)
    
    with patch("aadap.api.routes.tasks.create_task", new_callable=AsyncMock, return_value=mock_task.id):
        response = await client.post("/api/v1/tasks", json={"title": "Test Task"})
    
    assert response.status_code == 201
```

### E2E Tests

E2E tests verify full workflows:
```python
@pytest.mark.asyncio
async def test_execute_task_includes_optimization_transitions(service: ExecutionService):
    """Full execution pipeline includes optimization phase transitions."""
    task = _task(title="Create ETL", description="Create a PySpark ETL pipeline")
    transitions: list[tuple[TaskState, TaskState]] = []

    async def record_transition(task_id, from_state, to_state):
        transitions.append((from_state, to_state))

    service._transition = AsyncMock(side_effect=record_transition)
    # ... setup mocks ...

    result = await service.execute_task(task.id)

    assert result["status"] == "COMPLETED"
    assert (TaskState.VALIDATION_PASSED, TaskState.OPTIMIZATION_PENDING) in transitions
    assert (TaskState.IN_OPTIMIZATION, TaskState.OPTIMIZED) in transitions
```

## Common Patterns

### Exception Testing

```python
# Testing that an exception is raised
async def test_cannot_execute_without_accepting(agent, context):
    with pytest.raises(AgentLifecycleError, match="cannot execute"):
        await agent.execute(context)

# Testing exception properties
async def test_resume_after_approval_requires_decision_explanation(service):
    task = _task(title="Resume", metadata_={"approval_id": str(uuid.uuid4())})
    task.current_state = TaskState.APPROVAL_PENDING.value
    
    with pytest.raises(RuntimeError, match="INV-09"):
        await service._resume_after_approval(task)
```

### Response Validation

```python
@pytest.mark.asyncio
async def test_health_response_structure(client):
    """Response contains status, postgres, and redis fields."""
    resp = await client.get("/health")
    data = resp.json()

    assert "status" in data
    assert "postgres" in data
    assert "redis" in data
```

### Correlation ID Testing

```python
@pytest.mark.asyncio
async def test_correlation_id_propagated(client):
    """Custom X-Correlation-ID is echoed back."""
    custom_id = str(uuid.uuid4())
    response = await client.get("/health", headers={"X-Correlation-ID": custom_id})
    assert response.headers.get("x-correlation-id") == custom_id
```

### State Machine Testing

```python
class TestPoolCapacity:
    """Pool size limits."""

    def test_capacity_enforced(self):
        pool = AgentPoolManager(max_pool_size=2)
        pool.register_agent(StubAgent(agent_id="a1", agent_type="dev"))
        pool.register_agent(StubAgent(agent_id="a2", agent_type="dev"))
        with pytest.raises(PoolCapacityError, match="maximum capacity"):
            pool.register_agent(StubAgent(agent_id="a3", agent_type="dev"))
```

### Mock Behavior Verification

```python
@pytest.mark.asyncio
async def test_execute_task_routes_to_capability_agent(service):
    """Capability agent is called and artifacts are persisted."""
    service._execute_capability_agent = AsyncMock(return_value=(
        "print('capability code')",
        [{"type": "pipeline_definition", "content": {"name": "pipe"}}],
    ))
    service._persist_capability_artifacts = AsyncMock()

    result = await service.execute_task(task.id)

    service._execute_capability_agent.assert_awaited_once()
    service._persist_capability_artifacts.assert_awaited_once()
    service._generate_code.assert_not_called()
```

### Context Variable Testing

```python
def test_correlation_id_context_isolation():
    """Context variable is properly scoped and reset."""
    assert correlation_id_ctx.get(None) is None

    token = correlation_id_ctx.set("isolated-id")
    assert correlation_id_ctx.get() == "isolated-id"
    correlation_id_ctx.reset(token)

    assert correlation_id_ctx.get(None) is None
```

### Logging Testing

```python
def test_structured_log_output(settings, capsys):
    """Structured logs include required fields when format is console."""
    from aadap.core.logging import configure_logging, get_logger

    configure_logging()
    logger = get_logger("test")

    token = correlation_id_ctx.set("log-test-cid")
    try:
        logger.info("test.event", task_id="abc")
    finally:
        correlation_id_ctx.reset(token)
```

---

*Testing analysis: 2026-02-22*
