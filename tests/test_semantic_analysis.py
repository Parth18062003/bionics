"""
AADAP — Gate 3: Semantic Analysis & Pipeline Tests
=====================================================
Phase 5 tests for semantic risk scoring and pipeline.
"""

from __future__ import annotations

import pytest

from aadap.safety.pattern_matcher import PatternMatcher
from aadap.safety.semantic_analysis import (
    PipelineResult,
    SafetyPipeline,
    SemanticAnalyzer,
)
from aadap.safety.static_analysis import (
    RiskLevel,
    RiskResult,
    StaticAnalyzer,
)


@pytest.fixture
def pipeline() -> SafetyPipeline:
    return SafetyPipeline()


@pytest.fixture
def semantic() -> SemanticAnalyzer:
    return SemanticAnalyzer()


# ── Semantic Analyzer Tests ─────────────────────────────────────────────


class TestSemanticAnalyzer:
    def test_clean_results_pass(self, semantic: SemanticAnalyzer) -> None:
        gate1 = RiskResult.safe("static_analysis")
        gate2 = RiskResult.safe("pattern_matcher")
        result = semantic.evaluate("x = 1", "python", gate1, gate2)
        assert result.passed
        assert result.risk_level == RiskLevel.NONE

    def test_aggregates_max_severity(self, semantic: SemanticAnalyzer) -> None:
        """Highest severity from any gate dominates the result."""
        analyzer = StaticAnalyzer()
        matcher = PatternMatcher()

        code = "DROP TABLE users;"
        gate1 = analyzer.evaluate(code, "sql")
        gate2 = matcher.evaluate(code, "sql")

        result = semantic.evaluate(code, "sql", gate1, gate2)
        assert result.risk_level == RiskLevel.CRITICAL
        assert not result.passed


# ── Safety Pipeline Tests ───────────────────────────────────────────────


class TestSafetyPipeline:
    def test_pipeline_runs_all_gates(self, pipeline: SafetyPipeline) -> None:
        """All 3 gates must run — no bypass allowed."""
        result = pipeline.evaluate("SELECT 1;", language="sql")
        assert len(result.gate_results) == 3
        gates = [r.gate for r in result.gate_results]
        assert "static_analysis" in gates
        assert "pattern_matcher" in gates
        assert "semantic_analysis" in gates

    def test_safe_code_passes_pipeline(self, pipeline: SafetyPipeline) -> None:
        result = pipeline.evaluate(
            "SELECT id, name FROM users WHERE active = true;",
            language="sql",
        )
        assert result.passed
        assert result.overall_risk == RiskLevel.NONE
        assert not result.requires_approval

    def test_drop_table_fails_pipeline(self, pipeline: SafetyPipeline) -> None:
        """Definition of Done: DROP TABLE blocked."""
        result = pipeline.evaluate("DROP TABLE users;", language="sql")
        assert not result.passed
        assert result.overall_risk == RiskLevel.CRITICAL
        assert result.requires_approval

    def test_destructive_python_fails(self, pipeline: SafetyPipeline) -> None:
        code = "exec('import os; os.system(\"rm -rf /\")')"
        result = pipeline.evaluate(code, language="python")
        assert not result.passed
        assert result.requires_approval

    def test_requires_approval_high_risk(self, pipeline: SafetyPipeline) -> None:
        code = "DELETE FROM users WHERE id = 1;"
        result = pipeline.evaluate(code, language="sql")
        assert result.requires_approval
        assert result.overall_risk in (RiskLevel.HIGH, RiskLevel.CRITICAL)

    def test_requires_approval_flag_for_safe(self, pipeline: SafetyPipeline) -> None:
        result = pipeline.evaluate("x = 1 + 2", language="python")
        assert not result.requires_approval

    def test_all_findings_property(self, pipeline: SafetyPipeline) -> None:
        result = pipeline.evaluate("DROP TABLE users;", language="sql")
        assert len(result.all_findings) > 0

    def test_pipeline_summary_contains_gates(self, pipeline: SafetyPipeline) -> None:
        result = pipeline.evaluate("SELECT 1;", language="sql")
        assert "static_analysis" in result.summary
        assert "pattern_matcher" in result.summary
        assert "semantic_analysis" in result.summary
