"""
AADAP — Job Scheduler Agent Tests
=====================================
Tests for JobSchedulerAgent: job creation / schedule config / DAG
generation, self-correction, escalation, token budget enforcement,
and execution mode with a mock platform adapter.

Mirrors test_etl_pipeline_agent.py patterns.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest

from aadap.agents.adapters.base import PlatformAdapter
from aadap.agents.base import AgentContext, AgentState
from aadap.agents.job_scheduler_agent import (
    MAX_SELF_CORRECTIONS,
    JobSchedulerAgent,
)
from aadap.integrations.llm_client import LLMResponse, MockLLMClient


# ── Helpers ─────────────────────────────────────────────────────────────


def _valid_job_creation_output() -> str:
    return json.dumps({
        "platform": "databricks",
        "job_type": "notebook",
        "job_definition": {
            "name": "daily_etl_job",
            "tasks": [
                {
                    "task_key": "ingest",
                    "notebook_task": {"notebook_path": "/jobs/ingest"},
                    "max_retries": 2,
                    "timeout_seconds": 3600,
                },
                {
                    "task_key": "transform",
                    "notebook_task": {"notebook_path": "/jobs/transform"},
                    "depends_on": [{"task_key": "ingest"}],
                    "max_retries": 1,
                    "timeout_seconds": 7200,
                },
            ],
            "schedule": {"quartz_cron_expression": "0 0 6 * * ?", "timezone_id": "UTC"},
            "clusters": [{"num_workers": 4, "spark_version": "13.3.x-scala2.12"}],
        },
        "code": '{"name": "daily_etl_job", "tasks": [...]}',
        "language": "json",
        "explanation": "Two-task DAG: ingest → transform, daily at 06:00 UTC.",
        "job_id": None,
        "created": False,
    })


def _valid_schedule_output() -> str:
    return json.dumps({
        "platform": "fabric",
        "job_type": "pipeline",
        "job_definition": {
            "name": "hourly_refresh",
            "tasks": [{"task_key": "refresh", "pipeline": "sales_refresh"}],
            "schedule": {"type": "cron", "expression": "0 * * * *", "timezone": "UTC"},
            "triggers": [{"type": "schedule", "recurrence": "hourly"}],
        },
        "code": "-- Fabric trigger definition (see job_definition)",
        "language": "json",
        "explanation": "Hourly pipeline trigger for sales refresh.",
    })


def _valid_dag_output() -> str:
    return json.dumps({
        "platform": "databricks",
        "job_type": "spark",
        "job_definition": {
            "name": "parallel_processing",
            "tasks": [
                {"task_key": "extract_a", "spark_jar_task": {
                    "main_class": "com.Extract"}},
                {"task_key": "extract_b", "spark_jar_task": {
                    "main_class": "com.Extract"}},
                {
                    "task_key": "merge",
                    "depends_on": [{"task_key": "extract_a"}, {"task_key": "extract_b"}],
                    "notebook_task": {"notebook_path": "/jobs/merge"},
                },
            ],
        },
        "code": '{"name": "parallel_processing", "tasks": [...]}',
        "language": "json",
        "explanation": "Fan-out/fan-in DAG: parallel extracts → merge.",
    })


def _invalid_output() -> str:
    """Missing required fields — will trigger schema violation."""
    return json.dumps({"code": "print('hello')"})


def _make_context(
    scheduler_mode: str = "job_creation",
    platform: str = "databricks",
    **overrides: Any,
) -> AgentContext:
    defaults: dict[str, Any] = {
        "task_id": uuid.uuid4(),
        "task_data": {
            "description": "Create a daily ETL job with ingest and transform tasks",
            "scheduler_mode": scheduler_mode,
            "platform": platform,
            "job_type": "notebook",
            "tasks_description": "ingest → transform",
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
        self.created_jobs: list[dict] = []
        self.executed_jobs: list[tuple[str, dict | None]] = []

    async def create_pipeline(self, definition: dict[str, Any]) -> str:
        return "pipe-1"

    async def execute_pipeline(self, pipeline_id: str) -> dict[str, Any]:
        return {"status": "SUCCESS"}

    async def create_job(self, definition: dict[str, Any]) -> str:
        self.created_jobs.append(definition)
        return f"job-{len(self.created_jobs)}"

    async def execute_job(
        self, job_id: str, params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.executed_jobs.append((job_id, params))
        return {"status": "SUCCESS", "run_id": "run-1"}

    async def get_job_status(self, job_id: str) -> dict[str, Any]:
        return {"status": "COMPLETED"}

    async def create_table(self, schema: dict[str, Any]) -> str:
        return "table-1"

    async def list_tables(self) -> list[dict[str, Any]]:
        return []

    async def create_shortcut(self, config: dict[str, Any]) -> str:
        return "shortcut-1"

    async def execute_sql(self, sql: str) -> dict[str, Any]:
        return {"rows": []}


# ── Job Creation Tests ─────────────────────────────────────────────────


class TestJobSchedulerAgentCreation:
    async def test_successful_job_creation(self):
        llm = MockLLMClient(default_response=_valid_job_creation_output())
        agent = JobSchedulerAgent(agent_id="sched-1", llm_client=llm)
        ctx = _make_context(scheduler_mode="job_creation")

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert result.output["job_type"] == "notebook"
        assert result.output["platform"] == "databricks"
        assert "daily_etl_job" in result.output["job_definition"]["name"]
        assert result.tokens_used > 0

    async def test_job_creation_produces_artifact(self):
        llm = MockLLMClient(default_response=_valid_job_creation_output())
        agent = JobSchedulerAgent(agent_id="sched-2", llm_client=llm)
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert len(result.artifacts) == 1
        artifact = result.artifacts[0]
        assert artifact["type"] == "generated_code"
        assert artifact["job_type"] == "notebook"


# ── Schedule Config Tests ──────────────────────────────────────────────


class TestJobSchedulerAgentSchedule:
    async def test_successful_schedule_generation(self):
        llm = MockLLMClient(default_response=_valid_schedule_output())
        agent = JobSchedulerAgent(agent_id="sched-s-1", llm_client=llm)
        ctx = _make_context(scheduler_mode="schedule", platform="fabric")

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert result.output["platform"] == "fabric"
        assert result.output["job_type"] == "pipeline"


# ── DAG Builder Tests ──────────────────────────────────────────────────


class TestJobSchedulerAgentDAG:
    async def test_successful_dag_generation(self):
        llm = MockLLMClient(default_response=_valid_dag_output())
        agent = JobSchedulerAgent(agent_id="sched-d-1", llm_client=llm)
        ctx = _make_context(scheduler_mode="dag")

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert result.output["job_type"] == "spark"
        tasks = result.output["job_definition"]["tasks"]
        assert len(tasks) == 3
        # merge depends on both extracts
        merge = [t for t in tasks if t["task_key"] == "merge"][0]
        assert len(merge["depends_on"]) == 2


# ── Self-Correction Tests ──────────────────────────────────────────────


class TestJobSchedulerAgentSelfCorrection:
    async def test_self_corrects_on_schema_violation(self):
        """Agent should retry when output doesn't match schema (INV-03)."""
        responses = [
            LLMResponse(
                content=_invalid_output(), tokens_used=100, model="gpt-4o",
            ),
            LLMResponse(
                content=_valid_job_creation_output(),
                tokens_used=150,
                model="gpt-4o",
            ),
        ]
        call_count = 0

        class CorrectingLLM(MockLLMClient):
            async def complete(self, prompt, model=None, max_tokens=4096):
                nonlocal call_count
                resp = responses[min(call_count, len(responses) - 1)]
                call_count += 1
                return resp

        agent = JobSchedulerAgent(
            agent_id="sched-sc-1", llm_client=CorrectingLLM(),
        )
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert call_count == 2
        assert result.tokens_used == 250

    async def test_escalates_after_max_corrections(self):
        """Agent should escalate after MAX_SELF_CORRECTIONS (INV-03)."""
        llm = MockLLMClient(default_response=_invalid_output())
        agent = JobSchedulerAgent(agent_id="sched-esc-1", llm_client=llm)
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is False
        assert result.error is not None
        assert "ESCALATE" in result.error
        assert "INV-03" in result.error


# ── Token Budget Tests ─────────────────────────────────────────────────


class TestJobSchedulerAgentTokenBudget:
    async def test_token_budget_exhaustion(self):
        """Agent should escalate when token budget is exhausted (INV-04)."""
        llm = MockLLMClient(
            default_response=_invalid_output(),
            tokens_per_response=30_000,
        )
        agent = JobSchedulerAgent(agent_id="sched-tok-1", llm_client=llm)
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


class TestJobSchedulerAgentLLMError:
    async def test_llm_failure_escalates(self):
        """Agent should escalate on LLM client errors."""

        class FailingLLM(MockLLMClient):
            async def complete(self, prompt, model=None, max_tokens=4096):
                raise RuntimeError("LLM unavailable")

        agent = JobSchedulerAgent(
            agent_id="sched-err-1", llm_client=FailingLLM(),
        )
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is False
        assert result.error is not None
        assert "ESCALATE" in result.error
        assert "LLM call failed" in result.error


# ── Agent Lifecycle Tests ──────────────────────────────────────────────


class TestJobSchedulerAgentLifecycle:
    async def test_agent_type_is_job_scheduler(self):
        llm = MockLLMClient(default_response=_valid_job_creation_output())
        agent = JobSchedulerAgent(agent_id="sched-lc-1", llm_client=llm)
        assert agent.agent_type == "job_scheduler"

    async def test_agent_starts_idle(self):
        llm = MockLLMClient(default_response=_valid_job_creation_output())
        agent = JobSchedulerAgent(agent_id="sched-lc-2", llm_client=llm)
        assert agent.state == AgentState.IDLE

    async def test_agent_transitions_through_lifecycle(self):
        llm = MockLLMClient(default_response=_valid_job_creation_output())
        agent = JobSchedulerAgent(agent_id="sched-lc-3", llm_client=llm)
        ctx = _make_context()

        assert agent.state == AgentState.IDLE

        await agent.accept_task(ctx)
        assert agent.state == AgentState.ACCEPTING

        result = await agent.execute(ctx)
        assert result.success is True
        assert agent.state == AgentState.IDLE


# ── Execution Mode Tests (with mock adapter) ──────────────────────────


class TestJobSchedulerAgentExecution:
    async def test_generate_and_create_job(self):
        """When adapter is set, agent generates definition AND creates job."""
        llm = MockLLMClient(default_response=_valid_job_creation_output())
        adapter = MockPlatformAdapter()
        agent = JobSchedulerAgent(
            agent_id="sched-exec-1",
            llm_client=llm,
            platform_adapter=adapter,
        )
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert len(result.artifacts) == 2
        assert result.artifacts[0]["type"] == "generated_code"
        assert result.artifacts[1]["type"] == "execution_result"
        assert result.artifacts[1]["status"] == "SUCCESS"
        assert result.artifacts[1]["created"] is True

        # Job created on adapter
        assert len(adapter.created_jobs) == 1
        # No immediate run by default
        assert len(adapter.executed_jobs) == 0

    async def test_immediate_run_when_requested(self):
        """When run_immediately=True, agent also executes the job."""
        llm = MockLLMClient(default_response=_valid_job_creation_output())
        adapter = MockPlatformAdapter()
        agent = JobSchedulerAgent(
            agent_id="sched-exec-2",
            llm_client=llm,
            platform_adapter=adapter,
        )
        ctx = _make_context()
        ctx.task_data["run_immediately"] = True

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert len(adapter.created_jobs) == 1
        assert len(adapter.executed_jobs) == 1

    async def test_execution_output_attached(self):
        """Execution metadata should appear in the output dict."""
        llm = MockLLMClient(default_response=_valid_job_creation_output())
        adapter = MockPlatformAdapter()
        agent = JobSchedulerAgent(
            agent_id="sched-exec-3",
            llm_client=llm,
            platform_adapter=adapter,
        )
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert "execution" in result.output
        assert result.output["execution"]["status"] == "SUCCESS"
        assert result.output["execution"]["job_id"] == "job-1"

    async def test_execution_failure_returns_failure(self):
        """If adapter raises, agent should report failure but include artefacts."""
        llm = MockLLMClient(default_response=_valid_job_creation_output())

        class FailingAdapter(MockPlatformAdapter):
            async def create_job(self, definition):
                raise RuntimeError("Quota exceeded")

        agent = JobSchedulerAgent(
            agent_id="sched-exec-4",
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
        """Without adapter, agent should only produce generated_code artefact."""
        llm = MockLLMClient(default_response=_valid_job_creation_output())
        agent = JobSchedulerAgent(
            agent_id="sched-exec-5", llm_client=llm,
        )
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert len(result.artifacts) == 1
        assert result.artifacts[0]["type"] == "generated_code"
        assert "execution" not in result.output
