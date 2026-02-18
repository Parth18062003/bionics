"""
AADAP — Ingestion Agent Tests
=================================
Tests for IngestionAgent: batch / streaming / CDC code generation,
self-correction, escalation after retries, token budget enforcement,
and execution mode with a mock platform adapter.

Mirrors test_fabric_agent.py patterns.
"""

from __future__ import annotations

import json
import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest

from aadap.agents.adapters.base import PlatformAdapter
from aadap.agents.base import AgentContext, AgentState
from aadap.agents.ingestion_agent import MAX_SELF_CORRECTIONS, IngestionAgent
from aadap.integrations.llm_client import LLMResponse, MockLLMClient


# ── Helpers ─────────────────────────────────────────────────────────────


def _valid_batch_output() -> str:
    return json.dumps({
        "platform": "databricks",
        "ingestion_type": "batch",
        "source": {
            "type": "cloud_storage",
            "location": "abfss://raw@storage.dfs.core.windows.net/data/",
            "format": "parquet",
        },
        "target": {
            "table": "bronze.raw_events",
            "schema": "bronze",
            "format": "delta",
            "mode": "append",
        },
        "code": (
            "df = (spark.readStream\n"
            "  .format('cloudFiles')\n"
            "  .option('cloudFiles.format', 'parquet')\n"
            "  .load('abfss://raw@storage.dfs.core.windows.net/data/'))\n"
            "df.writeStream.toTable('bronze.raw_events')"
        ),
        "language": "python",
        "explanation": "Auto Loader batch ingestion from ADLS to Delta table.",
        "resource_config": {"cluster_size": "Standard_DS3_v2"},
        "checkpoint_location": "/checkpoints/raw_events",
        "schedule": {"cron": "0 0 * * *"},
    })


def _valid_streaming_output() -> str:
    return json.dumps({
        "platform": "databricks",
        "ingestion_type": "streaming",
        "source": {
            "type": "eventhub",
            "connection_string": "${{secrets/eh-connection}}",
            "consumer_group": "$Default",
        },
        "target": {
            "table": "silver.live_events",
            "schema": "silver",
            "format": "delta",
            "mode": "append",
        },
        "code": (
            "df = (spark.readStream\n"
            "  .format('eventhubs')\n"
            "  .options(**ehConf)\n"
            "  .load())\n"
            "df.writeStream.toTable('silver.live_events')"
        ),
        "language": "python",
        "explanation": "Streaming ingestion from Azure Event Hubs.",
    })


def _valid_cdc_output() -> str:
    return json.dumps({
        "platform": "fabric",
        "ingestion_type": "cdc",
        "source": {
            "type": "delta_cdf",
            "table": "bronze.raw_orders",
        },
        "target": {
            "table": "silver.orders",
            "schema": "silver",
            "format": "delta",
            "mode": "merge",
        },
        "code": (
            "changes = spark.readStream.format('delta')\n"
            "  .option('readChangeFeed', 'true')\n"
            "  .table('bronze.raw_orders')\n"
            "# MERGE logic omitted for brevity"
        ),
        "language": "python",
        "explanation": "CDC ingestion using Delta Change Data Feed.",
    })


def _invalid_output() -> str:
    """Missing required fields — will trigger schema violation."""
    return json.dumps({"code": "print('hello')"})


def _make_context(
    ingestion_type: str = "batch",
    platform: str = "databricks",
    **overrides: Any,
) -> AgentContext:
    defaults: dict[str, Any] = {
        "task_id": uuid.uuid4(),
        "task_data": {
            "description": "Ingest raw events from ADLS into bronze table",
            "ingestion_type": ingestion_type,
            "platform": platform,
            "source_description": "Parquet files in ADLS container",
            "target_description": "Delta table bronze.raw_events",
            "environment": "SANDBOX",
            "context": "",
        },
        "token_budget": 50_000,
        "allowed_tools": set(),
    }
    defaults.update(overrides)
    return AgentContext(**defaults)


# ── Mock Adapter ────────────────────────────────────────────────────────


class MockPlatformAdapter(PlatformAdapter):
    """Minimal concrete adapter for testing execution-mode paths."""

    def __init__(self) -> None:
        super().__init__(platform_name="mock")
        self.created_tables: list[dict] = []
        self.created_pipelines: list[dict] = []
        self.executed_pipelines: list[str] = []

    async def create_pipeline(self, definition: dict[str, Any]) -> str:
        self.created_pipelines.append(definition)
        return f"pipe-{len(self.created_pipelines)}"

    async def execute_pipeline(self, pipeline_id: str) -> dict[str, Any]:
        self.executed_pipelines.append(pipeline_id)
        return {"status": "SUCCESS", "pipeline_id": pipeline_id}

    async def create_job(self, definition: dict[str, Any]) -> str:
        return "job-1"

    async def execute_job(
        self, job_id: str, params: dict[str, Any] | None = None,
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
        return "shortcut-1"

    async def execute_sql(self, sql: str) -> dict[str, Any]:
        return {"rows": []}


# ── Batch Ingestion Tests ──────────────────────────────────────────────


class TestIngestionAgentBatch:
    async def test_successful_batch_generation(self):
        llm = MockLLMClient(default_response=_valid_batch_output())
        agent = IngestionAgent(agent_id="ingest-b-1", llm_client=llm)
        ctx = _make_context(ingestion_type="batch")

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert result.output["ingestion_type"] == "batch"
        assert result.output["platform"] == "databricks"
        assert "cloudFiles" in result.output["code"]
        assert result.tokens_used > 0

    async def test_batch_produces_artifact(self):
        llm = MockLLMClient(default_response=_valid_batch_output())
        agent = IngestionAgent(agent_id="ingest-b-2", llm_client=llm)
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert len(result.artifacts) == 1
        artifact = result.artifacts[0]
        assert artifact["type"] == "generated_code"
        assert artifact["ingestion_type"] == "batch"


# ── Streaming Ingestion Tests ──────────────────────────────────────────


class TestIngestionAgentStreaming:
    async def test_successful_streaming_generation(self):
        llm = MockLLMClient(default_response=_valid_streaming_output())
        agent = IngestionAgent(agent_id="ingest-s-1", llm_client=llm)
        ctx = _make_context(ingestion_type="streaming")

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert result.output["ingestion_type"] == "streaming"
        assert "readStream" in result.output["code"]


# ── CDC Ingestion Tests ────────────────────────────────────────────────


class TestIngestionAgentCDC:
    async def test_successful_cdc_generation(self):
        llm = MockLLMClient(default_response=_valid_cdc_output())
        agent = IngestionAgent(agent_id="ingest-c-1", llm_client=llm)
        ctx = _make_context(ingestion_type="cdc", platform="fabric")

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert result.output["ingestion_type"] == "cdc"
        assert result.output["platform"] == "fabric"


# ── Self-Correction Tests ──────────────────────────────────────────────


class TestIngestionAgentSelfCorrection:
    async def test_self_corrects_on_schema_violation(self):
        """Agent should retry when output doesn't match schema (INV-03)."""
        responses = [
            LLMResponse(
                content=_invalid_output(), tokens_used=100, model="gpt-4o",
            ),
            LLMResponse(
                content=_valid_batch_output(), tokens_used=150, model="gpt-4o",
            ),
        ]
        call_count = 0

        class CorrectingLLM(MockLLMClient):
            async def complete(self, prompt, model=None, max_tokens=4096):
                nonlocal call_count
                resp = responses[min(call_count, len(responses) - 1)]
                call_count += 1
                return resp

        agent = IngestionAgent(
            agent_id="ingest-sc-1", llm_client=CorrectingLLM(),
        )
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert call_count == 2
        assert result.tokens_used == 250  # 100 + 150

    async def test_escalates_after_max_corrections(self):
        """Agent should escalate after MAX_SELF_CORRECTIONS (INV-03)."""
        llm = MockLLMClient(default_response=_invalid_output())
        agent = IngestionAgent(agent_id="ingest-esc-1", llm_client=llm)
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is False
        assert result.error is not None
        assert "ESCALATE" in result.error
        assert "INV-03" in result.error


# ── Token Budget Tests ─────────────────────────────────────────────────


class TestIngestionAgentTokenBudget:
    async def test_token_budget_exhaustion(self):
        """Agent should escalate when token budget is exhausted (INV-04)."""
        llm = MockLLMClient(
            default_response=_invalid_output(),
            tokens_per_response=30_000,
        )
        agent = IngestionAgent(agent_id="ingest-tok-1", llm_client=llm)
        ctx = _make_context(token_budget=50_000)

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is False
        assert result.error is not None
        assert (
            "Token budget exhausted" in result.error
            or "ESCALATE" in result.error
        )


# ── LLM Error Handling Tests ───────────────────────────────────────────


class TestIngestionAgentLLMError:
    async def test_llm_failure_escalates(self):
        """Agent should escalate on LLM client errors."""

        class FailingLLM(MockLLMClient):
            async def complete(self, prompt, model=None, max_tokens=4096):
                raise RuntimeError("LLM unavailable")

        agent = IngestionAgent(
            agent_id="ingest-err-1", llm_client=FailingLLM(),
        )
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is False
        assert result.error is not None
        assert "ESCALATE" in result.error
        assert "LLM call failed" in result.error


# ── Agent Lifecycle Tests ──────────────────────────────────────────────


class TestIngestionAgentLifecycle:
    async def test_agent_type_is_ingestion(self):
        llm = MockLLMClient(default_response=_valid_batch_output())
        agent = IngestionAgent(agent_id="ingest-lc-1", llm_client=llm)
        assert agent.agent_type == "ingestion"

    async def test_agent_starts_idle(self):
        llm = MockLLMClient(default_response=_valid_batch_output())
        agent = IngestionAgent(agent_id="ingest-lc-2", llm_client=llm)
        assert agent.state == AgentState.IDLE

    async def test_agent_transitions_through_lifecycle(self):
        llm = MockLLMClient(default_response=_valid_batch_output())
        agent = IngestionAgent(agent_id="ingest-lc-3", llm_client=llm)
        ctx = _make_context()

        assert agent.state == AgentState.IDLE

        await agent.accept_task(ctx)
        assert agent.state == AgentState.ACCEPTING

        result = await agent.execute(ctx)
        assert result.success is True
        # Agent should be back to IDLE after execution
        assert agent.state == AgentState.IDLE


# ── Execution Mode Tests (with mock adapter) ──────────────────────────


class TestIngestionAgentExecution:
    async def test_generate_and_execute_success(self):
        """When adapter is set, agent generates code AND executes on platform."""
        llm = MockLLMClient(default_response=_valid_batch_output())
        adapter = MockPlatformAdapter()
        agent = IngestionAgent(
            agent_id="ingest-exec-1",
            llm_client=llm,
            platform_adapter=adapter,
        )
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        # Should have both code generation and execution artefacts
        assert len(result.artifacts) == 2
        assert result.artifacts[0]["type"] == "generated_code"
        assert result.artifacts[1]["type"] == "execution_result"
        assert result.artifacts[1]["status"] == "SUCCESS"

        # Adapter should have been called
        assert len(adapter.created_tables) == 1
        assert len(adapter.created_pipelines) == 1
        assert len(adapter.executed_pipelines) == 1

    async def test_execution_output_attached(self):
        """Execution metadata should appear in the output dict."""
        llm = MockLLMClient(default_response=_valid_batch_output())
        adapter = MockPlatformAdapter()
        agent = IngestionAgent(
            agent_id="ingest-exec-2",
            llm_client=llm,
            platform_adapter=adapter,
        )
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert "execution" in result.output
        assert result.output["execution"]["status"] == "SUCCESS"

    async def test_execution_failure_returns_failure(self):
        """If adapter raises, agent should report failure but include artefacts."""
        llm = MockLLMClient(default_response=_valid_batch_output())

        class FailingAdapter(MockPlatformAdapter):
            async def create_pipeline(self, definition):
                raise RuntimeError("Cluster unavailable")

        agent = IngestionAgent(
            agent_id="ingest-exec-3",
            llm_client=llm,
            platform_adapter=FailingAdapter(),
        )
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is False
        assert result.error is not None
        assert "Platform execution failed" in result.error
        assert len(result.artifacts) == 2  # code + failed execution

    async def test_generate_only_without_adapter(self):
        """Without adapter, agent should only produce generated_code artefact."""
        llm = MockLLMClient(default_response=_valid_batch_output())
        agent = IngestionAgent(
            agent_id="ingest-exec-4", llm_client=llm,
        )
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert len(result.artifacts) == 1
        assert result.artifacts[0]["type"] == "generated_code"
        assert "execution" not in result.output
