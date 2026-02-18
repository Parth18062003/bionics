"""
AADAP — ETL Pipeline Agent Tests
====================================
Tests for ETLPipelineAgent: DLT / Data Factory / transformation code
generation, self-correction, escalation after retries, token budget
enforcement, and execution mode with a mock platform adapter.

Mirrors test_ingestion_agent.py patterns.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest

from aadap.agents.adapters.base import PlatformAdapter
from aadap.agents.base import AgentContext, AgentState
from aadap.agents.etl_pipeline_agent import MAX_SELF_CORRECTIONS, ETLPipelineAgent
from aadap.integrations.llm_client import LLMResponse, MockLLMClient


# ── Helpers ─────────────────────────────────────────────────────────────


def _valid_dlt_output() -> str:
    return json.dumps({
        "platform": "databricks",
        "pipeline_type": "dlt",
        "transformations": [
            {"step": "bronze", "source": "raw_events", "target": "bronze_events"},
            {"step": "silver", "source": "bronze_events", "target": "silver_events"},
        ],
        "pipeline_definition": {
            "name": "events_dlt_pipeline",
            "target_schema": "silver",
            "continuous": False,
            "clusters": [{"label": "default", "num_workers": 2}],
        },
        "notebooks": [
            {
                "name": "bronze_events",
                "language": "python",
                "code": "@dlt.table\ndef bronze_events():\n  return spark.readStream.table('raw_events')",
            },
        ],
        "data_quality_rules": [
            {"expectation": "valid_id",
                "expression": "id IS NOT NULL", "action": "drop"},
        ],
        "code": (
            "import dlt\n\n"
            "@dlt.table\n"
            "def bronze_events():\n"
            "  return spark.readStream.table('raw_events')\n\n"
            "@dlt.table\n"
            "@dlt.expect_or_drop('valid_id', 'id IS NOT NULL')\n"
            "def silver_events():\n"
            "  return dlt.read_stream('bronze_events')"
        ),
        "language": "python",
        "explanation": "DLT pipeline with bronze/silver medallion pattern.",
        "schedule": {"cron": "0 */6 * * *"},
    })


def _valid_datafactory_output() -> str:
    return json.dumps({
        "platform": "fabric",
        "pipeline_type": "datafactory",
        "transformations": [
            {"step": "copy", "source": "blob_csv", "target": "lakehouse_raw"},
            {"step": "notebook", "source": "lakehouse_raw",
                "target": "lakehouse_curated"},
        ],
        "pipeline_definition": {
            "name": "sales_etl_pipeline",
            "activities": [
                {"type": "Copy", "source": "blob_csv", "sink": "lakehouse_raw"},
                {"type": "Notebook", "notebook": "transform_sales"},
            ],
        },
        "notebooks": [],
        "data_quality_rules": [],
        "code": (
            "-- Fabric Data Factory pipeline JSON\n"
            "-- See pipeline_definition for activity graph"
        ),
        "language": "sql",
        "explanation": "Data Factory pipeline: Copy + Notebook activities.",
    })


def _valid_transformation_output() -> str:
    return json.dumps({
        "platform": "databricks",
        "pipeline_type": "transformation",
        "transformations": [
            {"step": "deduplicate", "column": "event_id"},
            {"step": "enrich", "lookup": "dim_users"},
        ],
        "pipeline_definition": {"name": "transform_events"},
        "code": (
            "from pyspark.sql import functions as F\n\n"
            "df = spark.read.table('bronze.events')\n"
            "df = df.dropDuplicates(['event_id'])\n"
            "df.write.mode('overwrite').saveAsTable('silver.events')"
        ),
        "language": "python",
        "explanation": "Deduplicate and enrich events into silver layer.",
    })


def _invalid_output() -> str:
    """Missing required fields — will trigger schema violation."""
    return json.dumps({"code": "print('hello')"})


def _make_context(
    pipeline_type: str = "dlt",
    platform: str = "databricks",
    **overrides: Any,
) -> AgentContext:
    defaults: dict[str, Any] = {
        "task_id": uuid.uuid4(),
        "task_data": {
            "description": "Build a bronze-to-silver DLT pipeline for events",
            "pipeline_type": pipeline_type,
            "platform": platform,
            "source_tables": "raw_events",
            "target_tables": "silver.events",
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


# ── DLT Pipeline Tests ─────────────────────────────────────────────────


class TestETLPipelineAgentDLT:
    async def test_successful_dlt_generation(self):
        llm = MockLLMClient(default_response=_valid_dlt_output())
        agent = ETLPipelineAgent(agent_id="etl-dlt-1", llm_client=llm)
        ctx = _make_context(pipeline_type="dlt")

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert result.output["pipeline_type"] == "dlt"
        assert result.output["platform"] == "databricks"
        assert "@dlt.table" in result.output["code"]
        assert result.tokens_used > 0

    async def test_dlt_produces_artifact(self):
        llm = MockLLMClient(default_response=_valid_dlt_output())
        agent = ETLPipelineAgent(agent_id="etl-dlt-2", llm_client=llm)
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert len(result.artifacts) == 1
        artifact = result.artifacts[0]
        assert artifact["type"] == "generated_code"
        assert artifact["pipeline_type"] == "dlt"

    async def test_dlt_includes_data_quality_rules(self):
        llm = MockLLMClient(default_response=_valid_dlt_output())
        agent = ETLPipelineAgent(agent_id="etl-dlt-3", llm_client=llm)
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        content = result.artifacts[0]["content"]
        assert len(content["data_quality_rules"]) > 0
        assert content["data_quality_rules"][0]["expectation"] == "valid_id"


# ── Data Factory Pipeline Tests ────────────────────────────────────────


class TestETLPipelineAgentDataFactory:
    async def test_successful_datafactory_generation(self):
        llm = MockLLMClient(default_response=_valid_datafactory_output())
        agent = ETLPipelineAgent(agent_id="etl-df-1", llm_client=llm)
        ctx = _make_context(pipeline_type="datafactory", platform="fabric")

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert result.output["pipeline_type"] == "datafactory"
        assert result.output["platform"] == "fabric"


# ── Transformation Tests ───────────────────────────────────────────────


class TestETLPipelineAgentTransformation:
    async def test_successful_transformation_generation(self):
        llm = MockLLMClient(default_response=_valid_transformation_output())
        agent = ETLPipelineAgent(agent_id="etl-tx-1", llm_client=llm)
        ctx = _make_context(pipeline_type="transformation")

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert result.output["pipeline_type"] == "transformation"
        assert "dropDuplicates" in result.output["code"]


# ── Self-Correction Tests ──────────────────────────────────────────────


class TestETLPipelineAgentSelfCorrection:
    async def test_self_corrects_on_schema_violation(self):
        """Agent should retry when output doesn't match schema (INV-03)."""
        responses = [
            LLMResponse(
                content=_invalid_output(), tokens_used=100, model="gpt-4o",
            ),
            LLMResponse(
                content=_valid_dlt_output(), tokens_used=150, model="gpt-4o",
            ),
        ]
        call_count = 0

        class CorrectingLLM(MockLLMClient):
            async def complete(self, prompt, model=None, max_tokens=4096):
                nonlocal call_count
                resp = responses[min(call_count, len(responses) - 1)]
                call_count += 1
                return resp

        agent = ETLPipelineAgent(
            agent_id="etl-sc-1", llm_client=CorrectingLLM(),
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
        agent = ETLPipelineAgent(agent_id="etl-esc-1", llm_client=llm)
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is False
        assert result.error is not None
        assert "ESCALATE" in result.error
        assert "INV-03" in result.error


# ── Token Budget Tests ─────────────────────────────────────────────────


class TestETLPipelineAgentTokenBudget:
    async def test_token_budget_exhaustion(self):
        """Agent should escalate when token budget is exhausted (INV-04)."""
        llm = MockLLMClient(
            default_response=_invalid_output(),
            tokens_per_response=30_000,
        )
        agent = ETLPipelineAgent(agent_id="etl-tok-1", llm_client=llm)
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


class TestETLPipelineAgentLLMError:
    async def test_llm_failure_escalates(self):
        """Agent should escalate on LLM client errors."""

        class FailingLLM(MockLLMClient):
            async def complete(self, prompt, model=None, max_tokens=4096):
                raise RuntimeError("LLM unavailable")

        agent = ETLPipelineAgent(
            agent_id="etl-err-1", llm_client=FailingLLM(),
        )
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is False
        assert result.error is not None
        assert "ESCALATE" in result.error
        assert "LLM call failed" in result.error


# ── Agent Lifecycle Tests ──────────────────────────────────────────────


class TestETLPipelineAgentLifecycle:
    async def test_agent_type_is_etl_pipeline(self):
        llm = MockLLMClient(default_response=_valid_dlt_output())
        agent = ETLPipelineAgent(agent_id="etl-lc-1", llm_client=llm)
        assert agent.agent_type == "etl_pipeline"

    async def test_agent_starts_idle(self):
        llm = MockLLMClient(default_response=_valid_dlt_output())
        agent = ETLPipelineAgent(agent_id="etl-lc-2", llm_client=llm)
        assert agent.state == AgentState.IDLE

    async def test_agent_transitions_through_lifecycle(self):
        llm = MockLLMClient(default_response=_valid_dlt_output())
        agent = ETLPipelineAgent(agent_id="etl-lc-3", llm_client=llm)
        ctx = _make_context()

        assert agent.state == AgentState.IDLE

        await agent.accept_task(ctx)
        assert agent.state == AgentState.ACCEPTING

        result = await agent.execute(ctx)
        assert result.success is True
        assert agent.state == AgentState.IDLE


# ── Execution Mode Tests (with mock adapter) ──────────────────────────


class TestETLPipelineAgentExecution:
    async def test_generate_and_execute_success(self):
        """When adapter is set, agent generates code AND executes on platform."""
        llm = MockLLMClient(default_response=_valid_dlt_output())
        adapter = MockPlatformAdapter()
        agent = ETLPipelineAgent(
            agent_id="etl-exec-1",
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
        assert len(adapter.created_pipelines) == 1
        assert len(adapter.executed_pipelines) == 1

    async def test_execution_output_attached(self):
        """Execution metadata should appear in the output dict."""
        llm = MockLLMClient(default_response=_valid_dlt_output())
        adapter = MockPlatformAdapter()
        agent = ETLPipelineAgent(
            agent_id="etl-exec-2",
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
        llm = MockLLMClient(default_response=_valid_dlt_output())

        class FailingAdapter(MockPlatformAdapter):
            async def create_pipeline(self, definition):
                raise RuntimeError("Cluster unavailable")

        agent = ETLPipelineAgent(
            agent_id="etl-exec-3",
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
        llm = MockLLMClient(default_response=_valid_dlt_output())
        agent = ETLPipelineAgent(
            agent_id="etl-exec-4", llm_client=llm,
        )
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert len(result.artifacts) == 1
        assert result.artifacts[0]["type"] == "generated_code"
        assert "execution" not in result.output

    async def test_notebook_tables_created(self):
        """Notebooks with target_table should trigger create_table calls."""
        # Build output with notebook that has target_table
        output_data = json.loads(_valid_dlt_output())
        output_data["notebooks"] = [
            {"name": "nb1", "language": "python",
                "code": "...", "target_table": "silver.events"},
        ]
        llm = MockLLMClient(default_response=json.dumps(output_data))
        adapter = MockPlatformAdapter()
        agent = ETLPipelineAgent(
            agent_id="etl-exec-5",
            llm_client=llm,
            platform_adapter=adapter,
        )
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert len(adapter.created_tables) == 1
        assert adapter.created_tables[0]["table"] == "silver.events"
