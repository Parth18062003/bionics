"""
AADAP — Catalog Agent Tests
===============================
Tests for CatalogAgent: schema design / permission grant generation,
self-correction, escalation, token budget enforcement, approval gates,
and execution mode with a mock platform adapter.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from aadap.agents.adapters.base import PlatformAdapter
from aadap.agents.base import AgentContext, AgentState
from aadap.agents.catalog_agent import CatalogAgent
from aadap.integrations.llm_client import LLMResponse, MockLLMClient


def _valid_schema_design_output() -> str:
    return json.dumps({
        "platform": "databricks",
        "operation": "create",
        "resource_type": "schema",
        "ddl_statements": [
            "CREATE CATALOG IF NOT EXISTS analytics",
            "CREATE SCHEMA IF NOT EXISTS analytics.sales",
            "CREATE TABLE IF NOT EXISTS analytics.sales.orders (id BIGINT, amount DECIMAL(10,2))",
        ],
        "api_payloads": [{"name": "orders", "type": "managed_table"}],
        "permissions": [{"principal": "data_eng", "privileges": ["USE SCHEMA", "SELECT"]}],
        "code": "CREATE SCHEMA IF NOT EXISTS analytics.sales;",
        "language": "sql",
        "explanation": "Creates a governed analytics.sales schema and orders table.",
    })


def _valid_permission_output() -> str:
    return json.dumps({
        "platform": "fabric",
        "operation": "grant",
        "resource_type": "lakehouse",
        "ddl_statements": ["GRANT SELECT ON TABLE sales.orders TO reporting_team"],
        "api_payloads": [{"name": "sales-lakehouse-shortcut", "path": "/tables/orders"}],
        "permissions": [{"principal": "reporting_team", "privileges": ["SELECT"]}],
        "code": "GRANT SELECT ON TABLE sales.orders TO reporting_team;",
        "language": "sql",
        "explanation": "Grants read-only access for reporting_team.",
    })


def _invalid_output() -> str:
    return json.dumps({"code": "SELECT 1"})


def _make_context(
    catalog_mode: str = "schema_design",
    platform: str = "databricks",
    **overrides: Any,
) -> AgentContext:
    defaults: dict[str, Any] = {
        "task_id": uuid.uuid4(),
        "task_data": {
            "description": "Create analytics schema and grant reporting read access",
            "catalog_mode": catalog_mode,
            "platform": platform,
            "operation": "create",
            "resource_type": "schema",
            "naming_conventions": "snake_case; env prefix",
            "principals": "data_eng, reporting_team",
            "required_access": "data_eng=modify; reporting_team=read",
            "environment": "SANDBOX",
            "context": "",
        },
        "token_budget": 50_000,
        "allowed_tools": set(),
        "metadata": {},
    }
    defaults.update(overrides)
    return AgentContext(**defaults)


class MockPlatformAdapter(PlatformAdapter):
    def __init__(self) -> None:
        super().__init__(platform_name="mock")
        self.executed_sql: list[str] = []
        self.created_tables: list[dict[str, Any]] = []
        self.created_shortcuts: list[dict[str, Any]] = []

    async def create_pipeline(self, definition: dict[str, Any]) -> str:
        return "pipe-1"

    async def execute_pipeline(self, pipeline_id: str) -> dict[str, Any]:
        return {"status": "SUCCESS"}

    async def create_job(self, definition: dict[str, Any]) -> str:
        return "job-1"

    async def execute_job(
        self,
        job_id: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {"status": "SUCCESS"}

    async def get_job_status(self, job_id: str) -> dict[str, Any]:
        return {"status": "COMPLETED"}

    async def create_table(self, schema: dict[str, Any]) -> str:
        self.created_tables.append(schema)
        return f"table-{len(self.created_tables)}"

    async def list_tables(self) -> list[dict[str, Any]]:
        return []

    async def create_shortcut(self, config: dict[str, Any]) -> str:
        self.created_shortcuts.append(config)
        return f"shortcut-{len(self.created_shortcuts)}"

    async def execute_sql(self, sql: str) -> dict[str, Any]:
        self.executed_sql.append(sql)
        return {"status": "SUCCESS"}


class TestCatalogAgentGeneration:
    async def test_successful_schema_design_generation(self):
        llm = MockLLMClient(default_response=_valid_schema_design_output())
        agent = CatalogAgent(agent_id="catalog-1", llm_client=llm)
        ctx = _make_context(catalog_mode="schema_design")

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert result.output["operation"] == "create"
        assert result.output["resource_type"] == "schema"
        assert len(result.output["ddl_statements"]) == 3
        assert result.tokens_used > 0

    async def test_successful_permission_grant_generation(self):
        llm = MockLLMClient(default_response=_valid_permission_output())
        agent = CatalogAgent(agent_id="catalog-2", llm_client=llm)
        ctx = _make_context(catalog_mode="permission_grant", platform="fabric")
        ctx.task_data["operation"] = "grant"
        ctx.task_data["resource_type"] = "lakehouse"

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert result.output["operation"] == "grant"
        assert result.output["platform"] == "fabric"

    async def test_generation_produces_artifact(self):
        llm = MockLLMClient(default_response=_valid_schema_design_output())
        agent = CatalogAgent(agent_id="catalog-3", llm_client=llm)
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert len(result.artifacts) == 1
        assert result.artifacts[0]["type"] == "generated_code"


class TestCatalogAgentSelfCorrection:
    async def test_self_corrects_on_schema_violation(self):
        responses = [
            LLMResponse(content=_invalid_output(),
                        tokens_used=100, model="gpt-4o"),
            LLMResponse(content=_valid_schema_design_output(),
                        tokens_used=120, model="gpt-4o"),
        ]
        call_count = 0

        class CorrectingLLM(MockLLMClient):
            async def complete(self, prompt, model=None, max_tokens=4096):
                nonlocal call_count
                response = responses[min(call_count, len(responses) - 1)]
                call_count += 1
                return response

        agent = CatalogAgent(agent_id="catalog-sc-1",
                             llm_client=CorrectingLLM())
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert call_count == 2
        assert result.tokens_used == 220

    async def test_escalates_after_max_corrections(self):
        llm = MockLLMClient(default_response=_invalid_output())
        agent = CatalogAgent(agent_id="catalog-sc-2", llm_client=llm)
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is False
        assert result.error is not None
        assert "ESCALATE" in result.error
        assert "INV-03" in result.error


class TestCatalogAgentFailures:
    async def test_token_budget_exhaustion(self):
        llm = MockLLMClient(default_response=_invalid_output(),
                            tokens_per_response=30_000)
        agent = CatalogAgent(agent_id="catalog-f-1", llm_client=llm)
        ctx = _make_context(token_budget=50_000)

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is False
        assert result.error is not None
        assert "Token budget exhausted" in result.error or "ESCALATE" in result.error

    async def test_llm_failure_escalates(self):
        class FailingLLM(MockLLMClient):
            async def complete(self, prompt, model=None, max_tokens=4096):
                raise RuntimeError("LLM unavailable")

        agent = CatalogAgent(agent_id="catalog-f-2", llm_client=FailingLLM())
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is False
        assert result.error is not None
        assert "ESCALATE" in result.error
        assert "LLM call failed" in result.error


class TestCatalogAgentLifecycle:
    async def test_agent_type_is_catalog(self):
        llm = MockLLMClient(default_response=_valid_schema_design_output())
        agent = CatalogAgent(agent_id="catalog-l-1", llm_client=llm)
        assert agent.agent_type == "catalog"

    async def test_agent_starts_idle(self):
        llm = MockLLMClient(default_response=_valid_schema_design_output())
        agent = CatalogAgent(agent_id="catalog-l-2", llm_client=llm)
        assert agent.state == AgentState.IDLE

    async def test_agent_transitions_through_lifecycle(self):
        llm = MockLLMClient(default_response=_valid_schema_design_output())
        agent = CatalogAgent(agent_id="catalog-l-3", llm_client=llm)
        ctx = _make_context()

        assert agent.state == AgentState.IDLE
        await agent.accept_task(ctx)
        assert agent.state == AgentState.ACCEPTING
        result = await agent.execute(ctx)
        assert result.success is True
        assert agent.state == AgentState.IDLE


class TestCatalogAgentExecution:
    async def test_generate_and_execute_schema_operations(self):
        llm = MockLLMClient(default_response=_valid_schema_design_output())
        adapter = MockPlatformAdapter()
        agent = CatalogAgent(
            agent_id="catalog-exec-1",
            llm_client=llm,
            platform_adapter=adapter,
        )
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert len(result.artifacts) == 2
        assert result.artifacts[1]["type"] == "execution_result"
        assert result.artifacts[1]["status"] == "SUCCESS"
        assert len(adapter.executed_sql) == 3
        assert len(adapter.created_tables) == 1

    async def test_permission_grant_requires_approval(self):
        llm = MockLLMClient(default_response=_valid_permission_output())
        adapter = MockPlatformAdapter()
        agent = CatalogAgent(
            agent_id="catalog-exec-2",
            llm_client=llm,
            platform_adapter=adapter,
        )
        ctx = _make_context(catalog_mode="permission_grant", platform="fabric")
        ctx.task_data["operation"] = "grant"
        ctx.task_data["resource_type"] = "lakehouse"

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is False
        assert result.error is not None
        assert "Approval required" in result.error
        assert len(adapter.executed_sql) == 0

    async def test_permission_grant_executes_with_approval(self):
        llm = MockLLMClient(default_response=_valid_permission_output())
        adapter = MockPlatformAdapter()
        agent = CatalogAgent(
            agent_id="catalog-exec-3",
            llm_client=llm,
            platform_adapter=adapter,
        )
        ctx = _make_context(catalog_mode="permission_grant", platform="fabric")
        ctx.task_data["operation"] = "grant"
        ctx.task_data["resource_type"] = "lakehouse"
        ctx.task_data["approval_granted"] = True

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert len(adapter.executed_sql) == 1
        assert len(adapter.created_shortcuts) == 1

    async def test_execution_failure_returns_failure(self):
        llm = MockLLMClient(default_response=_valid_schema_design_output())

        class FailingAdapter(MockPlatformAdapter):
            async def execute_sql(self, sql: str) -> dict[str, Any]:
                raise RuntimeError("SQL warehouse unavailable")

        agent = CatalogAgent(
            agent_id="catalog-exec-4",
            llm_client=llm,
            platform_adapter=FailingAdapter(),
        )
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is False
        assert result.error is not None
        assert "Platform execution failed" in result.error
        assert len(result.artifacts) == 2

    async def test_generate_only_without_adapter(self):
        llm = MockLLMClient(default_response=_valid_schema_design_output())
        agent = CatalogAgent(agent_id="catalog-exec-5", llm_client=llm)
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert len(result.artifacts) == 1
        assert result.artifacts[0]["type"] == "generated_code"
        assert "execution" not in result.output
