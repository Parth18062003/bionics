"""
AADAP — Fabric Agent Tests
==============================
Tests for FabricAgent: code generation, self-correction,
escalation after retries, token budget enforcement,
and end-to-end Fabric execution (submit → poll → output).

Mirrors test_developer_agent.py pattern for Microsoft Fabric platform.
"""

from __future__ import annotations

import json
import uuid

import pytest

from aadap.agents.base import AgentContext, AgentState
from aadap.agents.fabric_agent import MAX_SELF_CORRECTIONS, FabricAgent
from aadap.integrations.fabric_client import (
    BaseFabricClient,
    FabricJobResult,
    FabricJobSubmission,
    JobStatus,
    MockFabricClient,
)
from aadap.integrations.llm_client import LLMResponse, MockLLMClient


# ── Helpers ─────────────────────────────────────────────────────────────


def _valid_fabric_python_output() -> str:
    return json.dumps({
        "code": "df = spark.read.table('lakehouse.sales')\ndf.show()",
        "language": "python",
        "explanation": "Reads a Lakehouse table and displays the first 20 rows.",
        "dependencies": ["pyspark"],
        "fabric_item_type": "Notebook",
    })


def _valid_fabric_scala_output() -> str:
    return json.dumps({
        "code": 'val df = spark.read.table("lakehouse.events")\ndf.show()',
        "language": "scala",
        "explanation": "Reads an events table from Fabric Lakehouse.",
        "dependencies": [],
        "fabric_item_type": "Notebook",
    })


def _valid_fabric_sql_output() -> str:
    return json.dumps({
        "code": "SELECT * FROM lakehouse.dbo.sales LIMIT 100",
        "language": "sql",
        "explanation": "Queries the sales table from Fabric Lakehouse SQL endpoint.",
        "dependencies": [],
        "fabric_item_type": "SQLEndpoint",
    })


def _invalid_output() -> str:
    return json.dumps({"code": "print('hello')"})


def _make_context(language: str = "python", **overrides) -> AgentContext:
    defaults = {
        "task_id": uuid.uuid4(),
        "task_data": {
            "description": "Read a Lakehouse table and display it",
            "environment": "SANDBOX",
            "context": "Microsoft Fabric Lakehouse",
            "language": language,
        },
        "token_budget": 50_000,
        "allowed_tools": set(),
    }
    defaults.update(overrides)
    return AgentContext(**defaults)


# ── Python Code Generation Tests ───────────────────────────────────────


class TestFabricAgentPython:
    async def test_successful_python_generation(self):
        llm = MockLLMClient(default_response=_valid_fabric_python_output())
        agent = FabricAgent(agent_id="fabric-py-1",
                            llm_client=llm, default_language="python")
        ctx = _make_context(language="python")

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert result.output["language"] == "python"
        assert "spark.read.table" in result.output["code"]
        assert result.tokens_used > 0

    async def test_produces_fabric_artifact(self):
        llm = MockLLMClient(default_response=_valid_fabric_python_output())
        agent = FabricAgent(agent_id="fabric-py-2", llm_client=llm)
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert len(result.artifacts) == 1
        artifact = result.artifacts[0]
        assert artifact["type"] == "generated_code"
        assert artifact["platform"] == "Microsoft Fabric"


# ── Scala Code Generation Tests ────────────────────────────────────────


class TestFabricAgentScala:
    async def test_successful_scala_generation(self):
        llm = MockLLMClient(default_response=_valid_fabric_scala_output())
        agent = FabricAgent(agent_id="fabric-sc-1",
                            llm_client=llm, default_language="scala")
        ctx = _make_context(language="scala")

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert result.output["language"] == "scala"
        assert "spark.read.table" in result.output["code"]


# ── SQL Code Generation Tests ──────────────────────────────────────────


class TestFabricAgentSQL:
    async def test_successful_sql_generation(self):
        llm = MockLLMClient(default_response=_valid_fabric_sql_output())
        agent = FabricAgent(agent_id="fabric-sql-1",
                            llm_client=llm, default_language="sql")
        ctx = _make_context(language="sql")

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert result.output["language"] == "sql"
        assert "SELECT" in result.output["code"]


# ── Self-Correction Tests ──────────────────────────────────────────────


class TestFabricAgentSelfCorrection:
    async def test_self_corrects_on_schema_violation(self):
        """Agent should retry when output doesn't match schema (INV-03)."""
        responses = [
            LLMResponse(content=_invalid_output(),
                        tokens_used=100, model="gpt-4o"),
            LLMResponse(content=_valid_fabric_python_output(),
                        tokens_used=150, model="gpt-4o"),
        ]
        call_count = 0

        class CorrectingLLM(MockLLMClient):
            async def complete(self, prompt, model=None, max_tokens=4096):
                nonlocal call_count
                resp = responses[min(call_count, len(responses) - 1)]
                call_count += 1
                return resp

        agent = FabricAgent(agent_id="fabric-sc-1", llm_client=CorrectingLLM())
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert call_count == 2
        assert result.tokens_used == 250  # 100 + 150

    async def test_escalates_after_max_corrections(self):
        """Agent should escalate after MAX_SELF_CORRECTIONS attempts (INV-03)."""
        llm = MockLLMClient(default_response=_invalid_output())
        agent = FabricAgent(agent_id="fabric-esc-1", llm_client=llm)
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is False
        assert "ESCALATE" in result.error
        assert "INV-03" in result.error


# ── Token Budget Tests ─────────────────────────────────────────────────


class TestFabricAgentTokenBudget:
    async def test_token_budget_exhaustion(self):
        """Agent should escalate when token budget is exhausted (INV-04)."""
        llm = MockLLMClient(
            default_response=_invalid_output(),
            tokens_per_response=30_000,
        )
        agent = FabricAgent(agent_id="fabric-tok-1", llm_client=llm)
        ctx = _make_context(token_budget=50_000)

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is False
        assert "Token budget exhausted" in result.error or "ESCALATE" in result.error


# ── LLM Error Handling Tests ───────────────────────────────────────────


class TestFabricAgentLLMError:
    async def test_llm_failure_escalates(self):
        """Agent should escalate on LLM client errors."""
        class FailingLLM(MockLLMClient):
            async def complete(self, prompt, model=None, max_tokens=4096):
                raise RuntimeError("Fabric LLM unavailable")

        agent = FabricAgent(agent_id="fabric-err-1", llm_client=FailingLLM())
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is False
        assert "ESCALATE" in result.error
        assert "LLM call failed" in result.error


# ── Agent Lifecycle Tests ──────────────────────────────────────────────


class TestFabricAgentLifecycle:
    async def test_agent_type_is_fabric(self):
        """Agent type should be 'fabric'."""
        llm = MockLLMClient(default_response=_valid_fabric_python_output())
        agent = FabricAgent(agent_id="fabric-lc-1", llm_client=llm)
        assert agent._agent_type == "fabric"

    async def test_agent_starts_idle(self):
        """Agent should start in IDLE state."""
        llm = MockLLMClient(default_response=_valid_fabric_python_output())
        agent = FabricAgent(agent_id="fabric-lc-2", llm_client=llm)
        assert agent._state == AgentState.IDLE

    async def test_agent_transitions_through_lifecycle(self):
        """Agent should go IDLE → ACCEPTING → EXECUTING → COMPLETED."""
        llm = MockLLMClient(default_response=_valid_fabric_python_output())
        agent = FabricAgent(agent_id="fabric-lc-3", llm_client=llm)
        ctx = _make_context()

        assert agent._state == AgentState.IDLE

        await agent.accept_task(ctx)
        assert agent._state == AgentState.ACCEPTING

        result = await agent.execute(ctx)
        assert result.success is True
        # Agent should be back to IDLE after execution
        assert agent._state == AgentState.IDLE

    async def test_default_language_parameter(self):
        """default_language should be respected."""
        llm = MockLLMClient(default_response=_valid_fabric_scala_output())
        agent = FabricAgent(
            agent_id="fabric-dl-1",
            llm_client=llm,
            default_language="scala",
        )
        assert agent._default_language == "scala"


# ── Fabric Execution (generate + submit) Tests ────────────────────────


class TestFabricAgentExecution:
    """Tests for the generate-and-execute flow (Phase 2 in _do_execute)."""

    async def test_generate_and_execute_success(self):
        """When fabric_client is set, agent generates code AND submits to Fabric."""
        llm = MockLLMClient(default_response=_valid_fabric_python_output())
        fabric = MockFabricClient(
            default_output="Rows printed successfully.",
            default_status=JobStatus.SUCCESS,
            default_duration_ms=1500,
        )
        agent = FabricAgent(
            agent_id="fabric-exec-1",
            llm_client=llm,
            fabric_client=fabric,
        )
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        # Should have 2 artifacts: generated_code + execution_result
        assert len(result.artifacts) == 2
        assert result.artifacts[0]["type"] == "generated_code"
        assert result.artifacts[1]["type"] == "execution_result"
        assert result.artifacts[1]["status"] == "SUCCESS"
        assert result.artifacts[1]["output"] == "Rows printed successfully."
        assert result.artifacts[1]["job_id"] is not None

    async def test_generate_and_execute_has_execution_in_output(self):
        """Output dict should contain both code fields AND execution dict."""
        llm = MockLLMClient(default_response=_valid_fabric_python_output())
        fabric = MockFabricClient()
        agent = FabricAgent(
            agent_id="fabric-exec-2",
            llm_client=llm,
            fabric_client=fabric,
        )
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert "code" in result.output
        assert "execution" in result.output
        assert result.output["execution"]["status"] == "SUCCESS"
        assert result.output["execution"]["job_id"] is not None

    async def test_generate_only_when_no_client(self):
        """Without fabric_client, only code generation happens (1 artifact)."""
        llm = MockLLMClient(default_response=_valid_fabric_python_output())
        agent = FabricAgent(
            agent_id="fabric-gen-only",
            llm_client=llm,
            fabric_client=None,
        )
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert len(result.artifacts) == 1
        assert result.artifacts[0]["type"] == "generated_code"
        assert "execution" not in result.output

    async def test_execution_failure_returns_both_artifacts(self):
        """When Fabric job fails, result should include both artifacts and mark failure."""
        llm = MockLLMClient(default_response=_valid_fabric_python_output())
        fabric = MockFabricClient(
            default_status=JobStatus.FAILED,
            default_duration_ms=3000,
        )
        agent = FabricAgent(
            agent_id="fabric-fail-1",
            llm_client=llm,
            fabric_client=fabric,
        )
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is False
        assert "Fabric execution failed" in result.error
        assert len(result.artifacts) == 2
        assert result.artifacts[0]["type"] == "generated_code"
        assert result.artifacts[1]["type"] == "execution_result"
        assert result.artifacts[1]["status"] == "FAILED"
        # Even on failure, output should contain both generated code and execution info
        assert "generated_code" in result.output
        assert "execution" in result.output

    async def test_execution_with_scala(self):
        """Execution should work for Scala language."""
        llm = MockLLMClient(default_response=_valid_fabric_scala_output())
        fabric = MockFabricClient(
            default_output="Scala output OK",
            default_status=JobStatus.SUCCESS,
        )
        agent = FabricAgent(
            agent_id="fabric-scala-exec",
            llm_client=llm,
            default_language="scala",
            fabric_client=fabric,
        )
        ctx = _make_context(language="scala")

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert len(result.artifacts) == 2
        assert result.artifacts[1]["output"] == "Scala output OK"

    async def test_execution_with_sql(self):
        """Execution should work for SQL language."""
        llm = MockLLMClient(default_response=_valid_fabric_sql_output())
        fabric = MockFabricClient(
            default_output="100 rows returned.",
            default_status=JobStatus.SUCCESS,
        )
        agent = FabricAgent(
            agent_id="fabric-sql-exec",
            llm_client=llm,
            default_language="sql",
            fabric_client=fabric,
        )
        ctx = _make_context(language="sql")

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert len(result.artifacts) == 2
        assert result.artifacts[1]["output"] == "100 rows returned."

    async def test_fabric_client_exception_handled(self):
        """When FabricClient raises, agent returns failure with error details."""

        class ExplodingClient(MockFabricClient):
            async def submit_job(self, task_id, code, environment, correlation_id=None, language="python"):
                raise ConnectionError("Fabric workspace unreachable")

        llm = MockLLMClient(default_response=_valid_fabric_python_output())
        agent = FabricAgent(
            agent_id="fabric-exc-1",
            llm_client=llm,
            fabric_client=ExplodingClient(),
        )
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is False
        assert "Fabric execution failed" in result.error
        assert "Fabric workspace unreachable" in result.error
        # Should still have the generated_code artifact + failed execution_result
        assert len(result.artifacts) == 2

    async def test_execution_duration_recorded(self):
        """Execution duration_ms from Fabric should appear in artifacts."""
        llm = MockLLMClient(default_response=_valid_fabric_python_output())
        fabric = MockFabricClient(default_duration_ms=4567)
        agent = FabricAgent(
            agent_id="fabric-dur-1",
            llm_client=llm,
            fabric_client=fabric,
        )
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.artifacts[1]["duration_ms"] == 4567

    async def test_lifecycle_correct_with_execution(self):
        """Agent lifecycle should go IDLE → ACCEPTING → EXECUTING → IDLE even with execution."""
        llm = MockLLMClient(default_response=_valid_fabric_python_output())
        fabric = MockFabricClient()
        agent = FabricAgent(
            agent_id="fabric-lc-exec",
            llm_client=llm,
            fabric_client=fabric,
        )
        ctx = _make_context()

        assert agent._state == AgentState.IDLE
        await agent.accept_task(ctx)
        assert agent._state == AgentState.ACCEPTING
        result = await agent.execute(ctx)
        assert result.success is True
        assert agent._state == AgentState.IDLE
