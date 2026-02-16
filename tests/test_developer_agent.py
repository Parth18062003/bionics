"""
AADAP — Developer Agent Tests (Phase 4)
===========================================
Tests for DeveloperAgent: code generation, self-correction,
escalation after retries, and token budget enforcement.

Covers required tests from PHASE_4_CONTRACTS.md:
- Prompt format compliance
- Error recovery paths
- Escalation after retries
"""

from __future__ import annotations

import json
import uuid

import pytest

from aadap.agents.base import AgentContext, AgentState
from aadap.agents.developer_agent import MAX_SELF_CORRECTIONS, DeveloperAgent
from aadap.integrations.llm_client import LLMResponse, MockLLMClient


# ── Helpers ─────────────────────────────────────────────────────────────


def _valid_code_output() -> str:
    return json.dumps({
        "code": "df = spark.read.csv('/data/input.csv')\ndf.show()",
        "language": "pyspark",
        "explanation": "Reads a CSV file from DBFS and displays the first 20 rows.",
        "dependencies": ["pyspark"],
    })


def _invalid_code_output() -> str:
    return json.dumps({"code": "print('hello')"})


def _make_context(**overrides) -> AgentContext:
    defaults = {
        "task_id": uuid.uuid4(),
        "task_data": {
            "description": "Read a CSV file and display it",
            "environment": "SANDBOX",
            "context": "Databricks workspace",
        },
        "token_budget": 50_000,
        "allowed_tools": set(),
    }
    defaults.update(overrides)
    return AgentContext(**defaults)


# ── Tests ───────────────────────────────────────────────────────────────


class TestDeveloperAgentSuccess:
    async def test_successful_code_generation(self):
        llm = MockLLMClient(default_response=_valid_code_output())
        agent = DeveloperAgent(agent_id="dev-1", llm_client=llm)
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert result.output["language"] == "pyspark"
        assert "spark.read.csv" in result.output["code"]
        assert result.tokens_used > 0

    async def test_produces_code_artifact(self):
        llm = MockLLMClient(default_response=_valid_code_output())
        agent = DeveloperAgent(agent_id="dev-2", llm_client=llm)
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert len(result.artifacts) == 1
        assert result.artifacts[0]["type"] == "generated_code"

    async def test_resets_to_idle_after_execution(self):
        llm = MockLLMClient(default_response=_valid_code_output())
        agent = DeveloperAgent(agent_id="dev-3", llm_client=llm)
        ctx = _make_context()

        await agent.accept_task(ctx)
        await agent.execute(ctx)
        assert agent.state == AgentState.IDLE


class TestDeveloperAgentSelfCorrection:
    async def test_self_corrects_on_schema_violation(self):
        responses = [
            LLMResponse(content=_invalid_code_output(), tokens_used=60,
                        model="gpt-4o"),
            LLMResponse(content=_valid_code_output(), tokens_used=90,
                        model="gpt-4o"),
        ]
        call_count = 0

        class CorrectingLLM(MockLLMClient):
            async def complete(self, prompt, model=None, max_tokens=4096):
                nonlocal call_count
                resp = responses[min(call_count, len(responses) - 1)]
                call_count += 1
                return resp

        agent = DeveloperAgent(agent_id="dev-sc", llm_client=CorrectingLLM())
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert call_count == 2
        assert result.tokens_used == 150


class TestDeveloperAgentEscalation:
    async def test_escalates_after_max_retries(self):
        llm = MockLLMClient(default_response=_invalid_code_output())
        agent = DeveloperAgent(agent_id="dev-esc", llm_client=llm)
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is False
        assert "ESCALATE" in result.error
        assert "INV-03" in result.error

    async def test_escalates_on_llm_error(self):
        class FailingLLM(MockLLMClient):
            async def complete(self, prompt, model=None, max_tokens=4096):
                raise RuntimeError("Model overloaded")

        agent = DeveloperAgent(agent_id="dev-fail", llm_client=FailingLLM())
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is False
        assert "ESCALATE" in result.error


class TestDeveloperAgentTokenBudget:
    async def test_escalates_on_token_exhaustion(self):
        llm = MockLLMClient(
            default_response=_invalid_code_output(),
            tokens_per_response=30_000,
        )
        agent = DeveloperAgent(agent_id="dev-tok", llm_client=llm)
        ctx = _make_context(token_budget=50_000)

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is False
        assert "Token budget exhausted" in result.error or "ESCALATE" in result.error
