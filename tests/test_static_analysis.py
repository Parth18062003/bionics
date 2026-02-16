"""
AADAP — Gate 1: Static Analysis Tests
========================================
Phase 5 required tests: Destructive op detection.
"""

from __future__ import annotations

import pytest

from aadap.safety.static_analysis import (
    Finding,
    RiskLevel,
    RiskResult,
    StaticAnalyzer,
    max_risk,
)


@pytest.fixture
def analyzer() -> StaticAnalyzer:
    return StaticAnalyzer()


# ── SQL Destructive Op Detection ────────────────────────────────────────


class TestSQLAnalysis:
    """Definition of Done: DROP TABLE blocked."""

    def test_drop_table_detected(self, analyzer: StaticAnalyzer) -> None:
        """DROP TABLE must be detected as CRITICAL risk."""
        result = analyzer.evaluate("DROP TABLE users;", language="sql")
        assert not result.passed
        assert result.risk_level == RiskLevel.CRITICAL
        assert result.gate == "static_analysis"
        assert any("DROP TABLE" in f.description for f in result.findings)

    def test_drop_database_detected(self, analyzer: StaticAnalyzer) -> None:
        result = analyzer.evaluate("DROP DATABASE production;", language="sql")
        assert not result.passed
        assert result.risk_level == RiskLevel.CRITICAL

    def test_truncate_detected(self, analyzer: StaticAnalyzer) -> None:
        result = analyzer.evaluate("TRUNCATE TABLE orders;", language="sql")
        assert not result.passed
        assert result.risk_level == RiskLevel.CRITICAL

    def test_delete_from_detected(self, analyzer: StaticAnalyzer) -> None:
        result = analyzer.evaluate(
            "DELETE FROM users WHERE id = 1;", language="sql"
        )
        assert not result.passed
        assert result.risk_level == RiskLevel.HIGH

    def test_alter_table_detected(self, analyzer: StaticAnalyzer) -> None:
        result = analyzer.evaluate(
            "ALTER TABLE users ADD COLUMN age INT;", language="sql"
        )
        assert not result.passed
        assert result.risk_level == RiskLevel.HIGH

    def test_safe_select_passes(self, analyzer: StaticAnalyzer) -> None:
        result = analyzer.evaluate(
            "SELECT * FROM users WHERE active = true;", language="sql"
        )
        assert result.passed
        assert result.risk_level == RiskLevel.NONE
        assert len(result.findings) == 0

    def test_insert_detected_low(self, analyzer: StaticAnalyzer) -> None:
        result = analyzer.evaluate(
            "INSERT INTO logs (msg) VALUES ('test');", language="sql"
        )
        assert result.passed  # LOW risk still passes gate
        assert result.risk_level == RiskLevel.LOW

    def test_multiple_findings_aggregated(self, analyzer: StaticAnalyzer) -> None:
        code = "DROP TABLE users;\nDELETE FROM orders;"
        result = analyzer.evaluate(code, language="sql")
        assert not result.passed
        assert result.risk_level == RiskLevel.CRITICAL
        assert len(result.findings) >= 2


# ── Python AST Analysis ────────────────────────────────────────────────


class TestPythonAnalysis:
    def test_exec_detected(self, analyzer: StaticAnalyzer) -> None:
        result = analyzer.evaluate("exec('print(1)')")
        assert not result.passed
        assert result.risk_level == RiskLevel.CRITICAL

    def test_eval_detected(self, analyzer: StaticAnalyzer) -> None:
        result = analyzer.evaluate("x = eval(user_input)")
        assert not result.passed
        assert result.risk_level == RiskLevel.CRITICAL

    def test_os_system_detected(self, analyzer: StaticAnalyzer) -> None:
        result = analyzer.evaluate("import os\nos.system('rm -rf /')")
        assert not result.passed
        assert result.risk_level == RiskLevel.CRITICAL

    def test_subprocess_detected(self, analyzer: StaticAnalyzer) -> None:
        result = analyzer.evaluate(
            "import subprocess\nsubprocess.call(['ls'])"
        )
        assert not result.passed
        assert result.risk_level == RiskLevel.CRITICAL

    def test_shutil_rmtree_detected(self, analyzer: StaticAnalyzer) -> None:
        result = analyzer.evaluate(
            "import shutil\nshutil.rmtree('/data')"
        )
        assert not result.passed
        assert result.risk_level == RiskLevel.CRITICAL

    def test_safe_python_passes(self, analyzer: StaticAnalyzer) -> None:
        code = "def hello():\n    return 'world'"
        result = analyzer.evaluate(code)
        assert result.passed
        assert result.risk_level == RiskLevel.NONE

    def test_syntax_error_flagged(self, analyzer: StaticAnalyzer) -> None:
        result = analyzer.evaluate("def (broken:")
        assert result.risk_level == RiskLevel.MEDIUM

    def test_empty_code_passes(self, analyzer: StaticAnalyzer) -> None:
        result = analyzer.evaluate("")
        assert result.passed
        assert result.risk_level == RiskLevel.NONE


# ── RiskLevel Utilities ─────────────────────────────────────────────────


class TestMaxRisk:
    def test_critical_wins(self) -> None:
        assert max_risk(RiskLevel.LOW, RiskLevel.CRITICAL) == RiskLevel.CRITICAL

    def test_same_level(self) -> None:
        assert max_risk(RiskLevel.HIGH, RiskLevel.HIGH) == RiskLevel.HIGH

    def test_none_vs_low(self) -> None:
        assert max_risk(RiskLevel.NONE, RiskLevel.LOW) == RiskLevel.LOW


# ── RiskResult Factory ──────────────────────────────────────────────────


class TestRiskResult:
    def test_safe_factory(self) -> None:
        r = RiskResult.safe("test_gate")
        assert r.passed is True
        assert r.risk_level == RiskLevel.NONE
        assert r.gate == "test_gate"
        assert len(r.findings) == 0
