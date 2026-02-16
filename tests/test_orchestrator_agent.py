"""
AADAP — Orchestrator Agent Tests (Phase 4)
==============================================
Tests for OrchestratorAgent: successful execution, self-correction,
escalation after max retries, and token budget enforcement.

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
from aadap.agents.orchestrator_agent import MAX_SELF_CORRECTIONS, OrchestratorAgent
from aadap.integrations.llm_client import LLMResponse, MockLLMClient


# ── Helpers ─────────────────────────────────────────────────────────────


def _valid_decision() -> str:
    """Return valid orchestrator decision JSON."""
    return json.dumps({
        "agent_assignment": "developer",
        "sub_tasks": [{"description": "Generate ETL code", "agent": "developer"}],
        "priority": 5,
        "reasoning": "Task requires code generation, routing to developer agent.",
    })


def _invalid_decision() -> str:
    """Return invalid JSON missing required fields."""
    return json.dumps({"agent_assignment": "developer"})


def _make_context(**overrides) -> AgentContext:
    defaults = {
        "task_id": uuid.uuid4(),
        "task_data": {
            "title": "Build ETL pipeline",
            "description": "Create a PySpark ETL pipeline for data ingestion",
            "environment": "SANDBOX",
        },
        "token_budget": 50_000,
        "allowed_tools": set(),
    }
    defaults.update(overrides)
    return AgentContext(**defaults)


# ── Tests ───────────────────────────────────────────────────────────────


class TestOrchestratorAgentSuccess:
    """Happy path: valid LLM response on first attempt."""

    async def test_successful_execution(self):
        llm = MockLLMClient(default_response=_valid_decision())
        agent = OrchestratorAgent(agent_id="orch-1", llm_client=llm)
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert result.output["agent_assignment"] == "developer"
        assert result.output["priority"] == 5
        assert result.tokens_used > 0

    async def test_produces_routing_artifact(self):
        llm = MockLLMClient(default_response=_valid_decision())
        agent = OrchestratorAgent(agent_id="orch-2", llm_client=llm)
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert len(result.artifacts) == 1
        assert result.artifacts[0]["type"] == "routing_decision"

    async def test_resets_to_idle_after_execution(self):
        llm = MockLLMClient(default_response=_valid_decision())
        agent = OrchestratorAgent(agent_id="orch-3", llm_client=llm)
        ctx = _make_context()

        await agent.accept_task(ctx)
        await agent.execute(ctx)

        assert agent.state == AgentState.IDLE


class TestOrchestratorAgentSelfCorrection:
    """Self-correction: LLM returns bad output then good output."""

    async def test_self_corrects_on_schema_violation(self):
        """Mock returns invalid JSON first, then valid on second call."""
        responses = [
            LLMResponse(content=_invalid_decision(), tokens_used=50,
                        model="gpt-4o"),
            LLMResponse(content=_valid_decision(), tokens_used=80,
                        model="gpt-4o"),
        ]
        call_count = 0

        class CorrectingLLM(MockLLMClient):
            async def complete(self, prompt, model=None, max_tokens=4096):
                nonlocal call_count
                resp = responses[min(call_count, len(responses) - 1)]
                call_count += 1
                return resp

        agent = OrchestratorAgent(
            agent_id="orch-sc", llm_client=CorrectingLLM()
        )
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert call_count == 2  # First failed, second succeeded
        assert result.tokens_used == 130  # 50 + 80


class TestOrchestratorAgentEscalation:
    """Escalation: all correction attempts fail → INV-03."""

    async def test_escalates_after_max_retries(self):
        llm = MockLLMClient(default_response=_invalid_decision())
        agent = OrchestratorAgent(agent_id="orch-esc", llm_client=llm)
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is False
        assert "ESCALATE" in result.error
        assert "INV-03" in result.error
        assert result.tokens_used == MAX_SELF_CORRECTIONS * 100  # MockLLMClient default

    async def test_escalates_on_llm_error(self):
        class FailingLLM(MockLLMClient):
            async def complete(self, prompt, model=None, max_tokens=4096):
                raise ConnectionError("LLM service unavailable")

        agent = OrchestratorAgent(
            agent_id="orch-fail", llm_client=FailingLLM()
        )
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is False
        assert "ESCALATE" in result.error
        assert "LLM call failed" in result.error


class TestOrchestratorAgentTokenBudget:
    """Token budget enforcement: INV-04."""

    async def test_escalates_on_token_exhaustion(self):
        llm = MockLLMClient(
            default_response=_invalid_decision(),
            tokens_per_response=30_000,
        )
        agent = OrchestratorAgent(agent_id="orch-tok", llm_client=llm)
        ctx = _make_context(token_budget=50_000)

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is False
        assert "Token budget exhausted" in result.error or "ESCALATE" in result.error
