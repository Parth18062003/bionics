"""
AADAP — Fabric End-to-End Tests
====================================
Integration tests that exercise the full Fabric pipeline:

1. Agent creation via factory
2. Tool registration
3. Pool wiring
4. Code generation (FabricAgent → MockLLMClient)
5. Job submission (MockFabricClient)
6. Job status polling & output retrieval

All tests use mock backends — no real Fabric / LLM calls.
"""

from __future__ import annotations

import json
import uuid

import pytest

from aadap.agents.base import AgentContext, AgentState
from aadap.agents.fabric_agent import FabricAgent
from aadap.agents.factory import create_fabric_agent, wire_pool
from aadap.agents.pool_manager import NoAvailableAgentError
from aadap.agents.tools.fabric_tools import (
    FABRIC_TOOL_NAMES,
    build_fabric_tools,
    register_fabric_tools,
)
from aadap.agents.tools.registry import (
    ToolPermissionDeniedError,
    ToolRegistry,
)
from aadap.integrations.fabric_client import (
    JobStatus,
    MockFabricClient,
)
from aadap.integrations.llm_client import MockLLMClient


# ── Helpers ──────────────────────────────────────────────────────────────

def _valid_fabric_response(language: str = "python") -> str:
    """Return a JSON response that satisfies FABRIC_CODE_SCHEMA."""
    return json.dumps({
        "code": "df = spark.sql('SELECT 1')\ndf.show()",
        "language": language,
        "explanation": "Test query on Fabric.",
        "dependencies": [],
        "fabric_item_type": "Notebook",
    })


# ── Tool Registration ───────────────────────────────────────────────────

class TestFabricToolRegistration:
    """Tools are built from a client and registered correctly."""

    def test_build_fabric_tools_returns_five(self):
        client = MockFabricClient()
        tools = build_fabric_tools(client)
        assert len(tools) == 5
        names = {t.name for t in tools}
        assert names == FABRIC_TOOL_NAMES

    def test_register_fabric_tools_in_registry(self):
        registry = ToolRegistry()
        client = MockFabricClient()
        register_fabric_tools(registry, client)
        assert len(registry.list_tools()) == 5
        for name in FABRIC_TOOL_NAMES:
            tool = registry.get(name)
            assert tool.name == name

    def test_register_twice_is_idempotent(self):
        registry = ToolRegistry()
        client = MockFabricClient()
        register_fabric_tools(registry, client)
        register_fabric_tools(registry, client)  # should not raise
        assert len(registry.list_tools()) == 5

    def test_submit_notebook_requires_approval(self):
        client = MockFabricClient()
        tools = {t.name: t for t in build_fabric_tools(client)}
        assert tools["fabric_submit_notebook"].requires_approval is True
        assert tools["fabric_get_job_status"].requires_approval is False
        assert tools["fabric_get_job_output"].requires_approval is False
        assert tools["fabric_query_lakehouse"].requires_approval is True
        assert tools["fabric_list_lakehouse_tables"].requires_approval is False


# ── Tool Execution ──────────────────────────────────────────────────────

class TestFabricToolExecution:
    """Tool handlers correctly delegate to MockFabricClient."""

    @pytest.mark.asyncio
    async def test_submit_notebook_handler(self):
        client = MockFabricClient()
        registry = ToolRegistry()
        register_fabric_tools(registry, client)

        handler = registry.get("fabric_submit_notebook").handler
        result = await handler(
            task_id=str(uuid.uuid4()),
            code="print('hello')",
            environment="SANDBOX",
            language="python",
        )
        assert "job_id" in result
        assert result["status"] == JobStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_get_job_status_handler(self):
        client = MockFabricClient()
        registry = ToolRegistry()
        register_fabric_tools(registry, client)

        # Submit first, then check status
        submit = registry.get("fabric_submit_notebook").handler
        sub_result = await submit(
            task_id=str(uuid.uuid4()),
            code="x = 1",
            language="python",
        )
        job_id = sub_result["job_id"]

        status_handler = registry.get("fabric_get_job_status").handler
        status_result = await status_handler(job_id=job_id)
        assert status_result["job_id"] == job_id
        assert status_result["status"] in {s.value for s in JobStatus}

    @pytest.mark.asyncio
    async def test_get_job_output_handler(self):
        client = MockFabricClient()
        registry = ToolRegistry()
        register_fabric_tools(registry, client)

        submit = registry.get("fabric_submit_notebook").handler
        sub_result = await submit(
            task_id=str(uuid.uuid4()),
            code="print(42)",
            language="python",
        )

        output_handler = registry.get("fabric_get_job_output").handler
        output_result = await output_handler(job_id=sub_result["job_id"])
        assert "output" in output_result

    @pytest.mark.asyncio
    async def test_query_lakehouse_handler(self):
        client = MockFabricClient()
        registry = ToolRegistry()
        register_fabric_tools(registry, client)

        handler = registry.get("fabric_query_lakehouse").handler
        result = await handler(
            task_id=str(uuid.uuid4()),
            sql="SELECT 1",
        )
        assert "job_id" in result

    @pytest.mark.asyncio
    async def test_list_lakehouse_tables_handler(self):
        client = MockFabricClient()
        registry = ToolRegistry()
        register_fabric_tools(registry, client)

        handler = registry.get("fabric_list_lakehouse_tables").handler
        result = await handler(task_id=str(uuid.uuid4()))
        assert "job_id" in result

    def test_permission_denied_for_unallowed_tool(self):
        client = MockFabricClient()
        registry = ToolRegistry()
        register_fabric_tools(registry, client)

        # Only allow status checks
        allowed = {"fabric_get_job_status"}
        with pytest.raises(ToolPermissionDeniedError):
            registry.execute_tool(
                allowed_tools=allowed,
                tool_name="fabric_submit_notebook",
                agent_id="fabric-1",
            )


# ── Factory & Pool Wiring ──────────────────────────────────────────────

class TestFabricFactory:
    """create_fabric_agent and wire_pool produce correctly configured objects."""

    def test_create_fabric_agent(self):
        llm = MockLLMClient(default_response=_valid_fabric_response())
        client = MockFabricClient()
        agent, registry = create_fabric_agent(llm, client)
        assert isinstance(agent, FabricAgent)
        assert agent.agent_type == "fabric"
        assert agent.state == AgentState.IDLE
        assert len(registry.list_tools()) == 5

    def test_create_fabric_agent_custom_language(self):
        llm = MockLLMClient(default_response=_valid_fabric_response("scala"))
        client = MockFabricClient()
        agent, _ = create_fabric_agent(
            llm, client, language="scala", agent_id="fab-scala"
        )
        assert agent.agent_id == "fab-scala"
        assert agent._default_language == "scala"

    def test_create_fabric_agent_shared_registry(self):
        llm = MockLLMClient(default_response=_valid_fabric_response())
        client = MockFabricClient()
        shared = ToolRegistry()
        _, reg = create_fabric_agent(llm, client, registry=shared)
        assert reg is shared
        assert len(shared.list_tools()) == 5

    def test_wire_pool_without_fabric(self):
        llm = MockLLMClient(default_response="test")
        pool = wire_pool(llm, fabric_client=None)
        # Only the developer agent should be registered
        assert pool.size == 1
        dev = pool.acquire_agent("developer")
        assert dev.agent_type == "developer"
        with pytest.raises(NoAvailableAgentError):
            pool.acquire_agent("fabric")

    def test_wire_pool_with_fabric(self):
        llm = MockLLMClient(default_response=_valid_fabric_response())
        client = MockFabricClient()
        pool = wire_pool(llm, fabric_client=client)
        # 1 developer + 3 fabric (python/scala/sql)
        assert pool.size == 4
        fabric = pool.acquire_agent("fabric")
        assert fabric.agent_type == "fabric"

    def test_wire_pool_custom_languages(self):
        llm = MockLLMClient(default_response=_valid_fabric_response())
        client = MockFabricClient()
        pool = wire_pool(
            llm,
            fabric_client=client,
            fabric_languages=["python", "sql"],
        )
        assert pool.size == 3  # 1 dev + 2 fabric


# ── End-to-End: Agent + Tools + Pool + Execution ───────────────────────

class TestFabricEndToEnd:
    """Full lifecycle tests using mock backends."""

    @pytest.mark.asyncio
    async def test_agent_generates_code_and_submits_to_fabric(self):
        """
        Simulate the full pipeline:
        1. Create agent + tools via factory
        2. Agent generates code (MockLLMClient)
        3. Submit generated code to MockFabricClient
        4. Poll status + retrieve output
        """
        llm = MockLLMClient(default_response=_valid_fabric_response())
        fabric = MockFabricClient()
        agent, registry = create_fabric_agent(llm, fabric, agent_id="e2e-1")

        # Step 1: Generate code via agent
        task_id = uuid.uuid4()
        context = AgentContext(
            task_id=task_id,
            task_data={
                "description": "Create a simple test table in Lakehouse",
                "language": "python",
                "environment": "SANDBOX",
                "context": "Fabric Lakehouse",
            },
        )
        await agent.accept_task(context)
        result = await agent.execute(context)
        assert result.success is True
        assert result.output is not None
        assert result.artifacts
        assert result.artifacts[0]["platform"] == "Microsoft Fabric"

        generated_code = result.output["code"]

        # Step 2: Submit to Fabric via tool
        submit_handler = registry.get("fabric_submit_notebook").handler
        submission = await submit_handler(
            task_id=str(task_id),
            code=generated_code,
            environment="SANDBOX",
            language="python",
        )
        assert submission["status"] == JobStatus.PENDING.value
        job_id = submission["job_id"]

        # Step 3: Check status
        status_handler = registry.get("fabric_get_job_status").handler
        status = await status_handler(job_id=job_id)
        assert status["status"] in {s.value for s in JobStatus}

        # Step 4: Get output
        output_handler = registry.get("fabric_get_job_output").handler
        output = await output_handler(job_id=job_id)
        assert output["job_id"] == job_id

    @pytest.mark.asyncio
    async def test_pool_acquire_execute_release(self):
        """
        1. Wire a pool with Fabric agents
        2. Acquire a fabric agent
        3. Execute a task
        4. Release back to pool
        """
        llm = MockLLMClient(default_response=_valid_fabric_response("sql"))
        fabric = MockFabricClient()
        pool = wire_pool(llm, fabric_client=fabric)

        # Acquire
        agent = pool.acquire_agent("fabric")
        assert agent.state == AgentState.IDLE

        # Execute
        context = AgentContext(
            task_id=uuid.uuid4(),
            task_data={
                "description": "List all tables",
                "language": "sql",
                "environment": "SANDBOX",
            },
        )
        await agent.accept_task(context)
        result = await agent.execute(context)
        assert result.success is True

        # Agent auto-returns to IDLE after execute
        assert agent.state == AgentState.IDLE

        # Release (no-op since already idle, but verifies no crash)
        pool.release_agent(agent.agent_id)
        assert agent.state == AgentState.IDLE

    @pytest.mark.asyncio
    async def test_multiple_languages_in_pool(self):
        """Acquire agents for different languages and execute tasks."""
        llm_py = MockLLMClient(
            default_response=_valid_fabric_response("python"))
        fabric = MockFabricClient()
        pool = wire_pool(llm_py, fabric_client=fabric)

        # Should be able to acquire 3 fabric agents (python, scala, sql)
        agents = []
        for _ in range(3):
            a = pool.acquire_agent("fabric")
            agents.append(a)
            # Execute so it returns to IDLE (but we need different agents)
            # Actually pool returns them in order, each agent_id is unique
            ctx = AgentContext(
                task_id=uuid.uuid4(),
                task_data={"description": "test", "language": "python"},
            )
            await a.accept_task(ctx)
            result = await a.execute(ctx)
            assert result.success is True

    @pytest.mark.asyncio
    async def test_fabric_job_lifecycle(self):
        """Submit → poll → output using direct client + tools."""
        fabric = MockFabricClient(
            default_status=JobStatus.SUCCESS,
            default_output="Query completed: 42 rows",
        )
        registry = ToolRegistry()
        register_fabric_tools(registry, fabric)

        task_id = str(uuid.uuid4())

        # Submit
        submit = registry.get("fabric_submit_notebook").handler
        sub = await submit(
            task_id=task_id,
            code="SELECT COUNT(*) FROM lakehouse.events",
            language="sql",
        )

        # Poll until success
        poll = registry.get("fabric_get_job_status").handler
        status = await poll(job_id=sub["job_id"])
        assert status["status"] == JobStatus.SUCCESS.value

        # Retrieve output
        output_fn = registry.get("fabric_get_job_output").handler
        result = await output_fn(job_id=sub["job_id"])
        assert result["status"] == JobStatus.SUCCESS.value
        assert result["output"] == "Query completed: 42 rows"
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_agent_built_in_execution_via_factory(self):
        """
        Factory-created agent with fabric_client should generate code
        AND execute it automatically, returning 2 artifacts.
        """
        llm = MockLLMClient(default_response=_valid_fabric_response())
        fabric = MockFabricClient(
            default_output="Pipeline ran OK",
            default_status=JobStatus.SUCCESS,
            default_duration_ms=1234,
        )
        agent, _registry = create_fabric_agent(
            llm, fabric, agent_id="e2e-auto-exec")

        context = AgentContext(
            task_id=uuid.uuid4(),
            task_data={
                "description": "Run an ETL pipeline on Fabric",
                "language": "python",
                "environment": "SANDBOX",
            },
        )
        await agent.accept_task(context)
        result = await agent.execute(context)

        assert result.success is True
        assert len(result.artifacts) == 2
        assert result.artifacts[0]["type"] == "generated_code"
        assert result.artifacts[1]["type"] == "execution_result"
        assert result.artifacts[1]["status"] == "SUCCESS"
        assert result.artifacts[1]["output"] == "Pipeline ran OK"
        assert result.artifacts[1]["duration_ms"] == 1234
        assert result.output["execution"]["job_id"] is not None

    @pytest.mark.asyncio
    async def test_pool_agent_has_fabric_client(self):
        """
        Agents created via wire_pool should have fabric_client set so
        they perform built-in execution.
        """
        llm = MockLLMClient(default_response=_valid_fabric_response())
        fabric = MockFabricClient(default_output="Pool exec OK")
        pool = wire_pool(llm, fabric_client=fabric)

        agent = pool.acquire_agent("fabric")
        assert isinstance(agent, FabricAgent)
        assert agent._fabric_client is fabric

        ctx = AgentContext(
            task_id=uuid.uuid4(),
            task_data={"description": "Test pool exec", "language": "python"},
        )
        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert len(result.artifacts) == 2
        assert result.artifacts[1]["output"] == "Pool exec OK"
