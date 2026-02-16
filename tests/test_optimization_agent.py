"""
AADAP — Optimization Agent Tests (Phase 4)
==============================================
Tests for OptimizationAgent: optimization output, self-correction,
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
from aadap.agents.optimization_agent import MAX_SELF_CORRECTIONS, OptimizationAgent
from aadap.integrations.llm_client import LLMResponse, MockLLMClient


# ── Helpers ─────────────────────────────────────────────────────────────


def _valid_optimization() -> str:
    return json.dumps({
        "optimized_code": (
            "df = spark.read.csv('/data/input.csv')\n"
            "df = df.cache()\n"
            "df.show()"
        ),
        "changes": [
            {
                "description": "Added cache() after read",
                "rationale": "DataFrame is used multiple times downstream",
            }
        ],
        "expected_improvement": "~30% reduction in I/O by caching intermediate DataFrame",
    })


def _invalid_optimization() -> str:
    return json.dumps({"optimized_code": "df.show()"})


def _make_context(**overrides) -> AgentContext:
    defaults = {
        "task_id": uuid.uuid4(),
        "task_data": {
            "code": "df = spark.read.csv('/data/input.csv')\ndf.show()",
            "context": "DataFrame used in 3 downstream joins",
            "environment": "SANDBOX",
        },
        "token_budget": 50_000,
        "allowed_tools": set(),
    }
    defaults.update(overrides)
    return AgentContext(**defaults)


# ── Tests ───────────────────────────────────────────────────────────────


class TestOptimizationAgentSuccess:
    async def test_successful_optimization(self):
        llm = MockLLMClient(default_response=_valid_optimization())
        agent = OptimizationAgent(agent_id="opt-1", llm_client=llm)
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert "cache()" in result.output["optimized_code"]
        assert len(result.output["changes"]) == 1
        assert result.tokens_used > 0

    async def test_produces_optimization_artifact(self):
        llm = MockLLMClient(default_response=_valid_optimization())
        agent = OptimizationAgent(agent_id="opt-2", llm_client=llm)
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert len(result.artifacts) == 1
        assert result.artifacts[0]["type"] == "optimized_code"

    async def test_resets_to_idle(self):
        llm = MockLLMClient(default_response=_valid_optimization())
        agent = OptimizationAgent(agent_id="opt-3", llm_client=llm)
        ctx = _make_context()

        await agent.accept_task(ctx)
        await agent.execute(ctx)
        assert agent.state == AgentState.IDLE


class TestOptimizationAgentSelfCorrection:
    async def test_self_corrects_on_schema_violation(self):
        responses = [
            LLMResponse(content=_invalid_optimization(), tokens_used=55,
                        model="gpt-4o"),
            LLMResponse(content=_valid_optimization(), tokens_used=75,
                        model="gpt-4o"),
        ]
        call_count = 0

        class CorrectingLLM(MockLLMClient):
            async def complete(self, prompt, model=None, max_tokens=4096):
                nonlocal call_count
                resp = responses[min(call_count, len(responses) - 1)]
                call_count += 1
                return resp

        agent = OptimizationAgent(
            agent_id="opt-sc", llm_client=CorrectingLLM()
        )
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert call_count == 2
        assert result.tokens_used == 130


class TestOptimizationAgentEscalation:
    async def test_escalates_after_max_retries(self):
        llm = MockLLMClient(default_response=_invalid_optimization())
        agent = OptimizationAgent(agent_id="opt-esc", llm_client=llm)
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is False
        assert "ESCALATE" in result.error
        assert "INV-03" in result.error

    async def test_escalates_on_llm_error(self):
        class FailingLLM(MockLLMClient):
            async def complete(self, prompt, model=None, max_tokens=4096):
                raise OSError("Network unreachable")

        agent = OptimizationAgent(
            agent_id="opt-fail", llm_client=FailingLLM()
        )
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is False
        assert "ESCALATE" in result.error


class TestOptimizationAgentTokenBudget:
    async def test_escalates_on_token_exhaustion(self):
        llm = MockLLMClient(
            default_response=_invalid_optimization(),
            tokens_per_response=30_000,
        )
        agent = OptimizationAgent(agent_id="opt-tok", llm_client=llm)
        ctx = _make_context(token_budget=50_000)

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is False
        assert "Token budget exhausted" in result.error or "ESCALATE" in result.error
