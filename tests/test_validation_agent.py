"""
AADAP — Validation Agent Tests (Phase 4)
============================================
Tests for ValidationAgent: validation reports, self-correction,
escalation, risk score bounds, and recommendation enforcement.

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
from aadap.agents.validation_agent import MAX_SELF_CORRECTIONS, ValidationAgent
from aadap.integrations.llm_client import LLMResponse, MockLLMClient


# ── Helpers ─────────────────────────────────────────────────────────────


def _valid_report() -> str:
    return json.dumps({
        "is_valid": True,
        "issues": [],
        "risk_score": 0.1,
        "recommendation": "approve",
    })


def _report_with_issues() -> str:
    return json.dumps({
        "is_valid": False,
        "issues": [
            {"severity": "warning", "description": "Unused import detected"},
            {"severity": "error", "description": "Missing error handling"},
        ],
        "risk_score": 0.6,
        "recommendation": "revise",
    })


def _invalid_report() -> str:
    return json.dumps({"is_valid": True})


def _bad_risk_score_report() -> str:
    return json.dumps({
        "is_valid": True,
        "issues": [],
        "risk_score": 1.5,  # Invalid: > 1.0
        "recommendation": "approve",
    })


def _bad_recommendation_report() -> str:
    return json.dumps({
        "is_valid": True,
        "issues": [],
        "risk_score": 0.2,
        "recommendation": "maybe",  # Invalid recommendation
    })


def _make_context(**overrides) -> AgentContext:
    defaults = {
        "task_id": uuid.uuid4(),
        "task_data": {
            "code": "df = spark.read.csv('/data/input.csv')",
            "language": "python",
            "description": "Read CSV data",
            "environment": "SANDBOX",
        },
        "token_budget": 50_000,
        "allowed_tools": set(),
    }
    defaults.update(overrides)
    return AgentContext(**defaults)


# ── Tests ───────────────────────────────────────────────────────────────


class TestValidationAgentSuccess:
    async def test_successful_validation(self):
        llm = MockLLMClient(default_response=_valid_report())
        agent = ValidationAgent(agent_id="val-1", llm_client=llm)
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert result.output["is_valid"] is True
        assert result.output["risk_score"] == 0.1
        assert result.output["recommendation"] == "approve"

    async def test_validation_with_issues(self):
        llm = MockLLMClient(default_response=_report_with_issues())
        agent = ValidationAgent(agent_id="val-2", llm_client=llm)
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert result.output["is_valid"] is False
        assert len(result.output["issues"]) == 2
        assert result.output["recommendation"] == "revise"

    async def test_produces_validation_artifact(self):
        llm = MockLLMClient(default_response=_valid_report())
        agent = ValidationAgent(agent_id="val-3", llm_client=llm)
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert len(result.artifacts) == 1
        assert result.artifacts[0]["type"] == "validation_report"

    async def test_resets_to_idle(self):
        llm = MockLLMClient(default_response=_valid_report())
        agent = ValidationAgent(agent_id="val-4", llm_client=llm)
        ctx = _make_context()

        await agent.accept_task(ctx)
        await agent.execute(ctx)
        assert agent.state == AgentState.IDLE


class TestValidationAgentDomainChecks:
    """Domain-specific validation: risk_score bounds, recommendation values."""

    async def test_rejects_out_of_bounds_risk_score(self):
        """risk_score > 1.0 should trigger self-correction, then escalate."""
        llm = MockLLMClient(default_response=_bad_risk_score_report())
        agent = ValidationAgent(agent_id="val-risk", llm_client=llm)
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        # All attempts fail with invalid risk_score → escalate
        assert result.success is False
        assert "ESCALATE" in result.error

    async def test_rejects_invalid_recommendation(self):
        """Invalid recommendation value should trigger self-correction."""
        llm = MockLLMClient(default_response=_bad_recommendation_report())
        agent = ValidationAgent(agent_id="val-rec", llm_client=llm)
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is False
        assert "ESCALATE" in result.error


class TestValidationAgentSelfCorrection:
    async def test_self_corrects_on_schema_violation(self):
        responses = [
            LLMResponse(content=_invalid_report(), tokens_used=40,
                        model="gpt-4o-mini"),
            LLMResponse(content=_valid_report(), tokens_used=60,
                        model="gpt-4o-mini"),
        ]
        call_count = 0

        class CorrectingLLM(MockLLMClient):
            async def complete(self, prompt, model=None, max_tokens=4096):
                nonlocal call_count
                resp = responses[min(call_count, len(responses) - 1)]
                call_count += 1
                return resp

        agent = ValidationAgent(
            agent_id="val-sc", llm_client=CorrectingLLM()
        )
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is True
        assert call_count == 2


class TestValidationAgentEscalation:
    async def test_escalates_after_max_retries(self):
        llm = MockLLMClient(default_response=_invalid_report())
        agent = ValidationAgent(agent_id="val-esc", llm_client=llm)
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is False
        assert "ESCALATE" in result.error
        assert "INV-03" in result.error

    async def test_escalates_on_llm_error(self):
        class FailingLLM(MockLLMClient):
            async def complete(self, prompt, model=None, max_tokens=4096):
                raise TimeoutError("LLM timeout")

        agent = ValidationAgent(
            agent_id="val-fail", llm_client=FailingLLM()
        )
        ctx = _make_context()

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is False
        assert "ESCALATE" in result.error


class TestValidationAgentTokenBudget:
    async def test_escalates_on_token_exhaustion(self):
        llm = MockLLMClient(
            default_response=_invalid_report(),
            tokens_per_response=30_000,
        )
        agent = ValidationAgent(agent_id="val-tok", llm_client=llm)
        ctx = _make_context(token_budget=50_000)

        await agent.accept_task(ctx)
        result = await agent.execute(ctx)

        assert result.success is False
        assert "Token budget exhausted" in result.error or "ESCALATE" in result.error
