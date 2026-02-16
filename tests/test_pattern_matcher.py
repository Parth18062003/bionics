"""
AADAP — Gate 2: Pattern Matcher Tests
========================================
Phase 5 tests for pattern matching gate.
"""

from __future__ import annotations

import pytest

from aadap.safety.pattern_matcher import DangerPattern, PatternMatcher
from aadap.safety.static_analysis import RiskLevel


@pytest.fixture
def matcher() -> PatternMatcher:
    return PatternMatcher()


# ── Built-in Pattern Detection ──────────────────────────────────────────


class TestBuiltinPatterns:
    def test_hardcoded_password_detected(self, matcher: PatternMatcher) -> None:
        code = "password = 'super_secret_123'"
        result = matcher.evaluate(code, language="python")
        assert not result.passed
        assert result.risk_level == RiskLevel.HIGH
        assert any("password" in f.pattern.lower() for f in result.findings)

    def test_hardcoded_api_key_detected(self, matcher: PatternMatcher) -> None:
        code = "api_key = 'sk-1234567890abcdef'"
        result = matcher.evaluate(code, language="python")
        assert not result.passed
        assert result.risk_level == RiskLevel.HIGH

    def test_production_host_detected(self, matcher: PatternMatcher) -> None:
        code = 'host = "prod-db.internal.com"'
        result = matcher.evaluate(code, language="python")
        assert not result.passed
        assert result.risk_level == RiskLevel.HIGH

    def test_connection_string_detected(self, matcher: PatternMatcher) -> None:
        code = 'conn = "postgresql://user:pass@host/db"'
        result = matcher.evaluate(code, language="python")
        assert result.risk_level >= RiskLevel.MEDIUM

    def test_rm_rf_detected(self, matcher: PatternMatcher) -> None:
        code = 'os.system("rm -rf /")'
        result = matcher.evaluate(code, language="python")
        assert not result.passed
        assert result.risk_level == RiskLevel.CRITICAL

    def test_disable_trigger_detected(self, matcher: PatternMatcher) -> None:
        code = "DISABLE TRIGGER ALL ON users;"
        result = matcher.evaluate(code, language="sql")
        assert not result.passed
        assert result.risk_level == RiskLevel.CRITICAL

    def test_grant_all_detected(self, matcher: PatternMatcher) -> None:
        code = "GRANT ALL PRIVILEGES ON *.* TO 'admin';"
        result = matcher.evaluate(code, language="sql")
        assert not result.passed
        assert result.risk_level == RiskLevel.HIGH

    def test_delete_without_where(self, matcher: PatternMatcher) -> None:
        code = "DELETE FROM users;"
        result = matcher.evaluate(code, language="sql")
        assert not result.passed
        assert result.risk_level == RiskLevel.CRITICAL

    def test_safe_code_passes(self, matcher: PatternMatcher) -> None:
        code = "def calculate(x, y):\n    return x + y"
        result = matcher.evaluate(code, language="python")
        assert result.passed
        assert result.risk_level == RiskLevel.NONE

    def test_empty_code_passes(self, matcher: PatternMatcher) -> None:
        result = matcher.evaluate("", language="python")
        assert result.passed
        assert result.risk_level == RiskLevel.NONE


# ── Custom Pattern Management ──────────────────────────────────────────


class TestCustomPatterns:
    def test_add_custom_pattern(self, matcher: PatternMatcher) -> None:
        before = matcher.pattern_count
        matcher.add_pattern(DangerPattern(
            name="custom_test",
            regex=r"DANGER_FUNCTION\(\)",
            description="Custom dangerous function",
            severity=RiskLevel.HIGH,
        ))
        assert matcher.pattern_count == before + 1

        result = matcher.evaluate("DANGER_FUNCTION()", language="python")
        assert not result.passed

    def test_remove_pattern(self, matcher: PatternMatcher) -> None:
        before = matcher.pattern_count
        removed = matcher.remove_pattern("hardcoded_password")
        assert removed is True
        assert matcher.pattern_count == before - 1

        # Should no longer detect hardcoded passwords
        result = matcher.evaluate("password = 'secret123'", language="python")
        # May still fail on other patterns, but the password one is gone
        password_findings = [
            f for f in result.findings if f.pattern == "hardcoded_password"
        ]
        assert len(password_findings) == 0

    def test_remove_nonexistent_pattern(self, matcher: PatternMatcher) -> None:
        removed = matcher.remove_pattern("nonexistent_pattern")
        assert removed is False

    def test_language_filtering(self, matcher: PatternMatcher) -> None:
        """SQL-only patterns should not match Python code."""
        matcher_fresh = PatternMatcher()
        # pickle_load is python-only
        code = "pickle.load(data)"
        sql_result = matcher_fresh.evaluate(code, language="sql")
        py_result = matcher_fresh.evaluate(code, language="python")

        pickle_in_sql = any(
            f.pattern == "pickle_load" for f in sql_result.findings
        )
        pickle_in_py = any(
            f.pattern == "pickle_load" for f in py_result.findings
        )
        assert not pickle_in_sql
        assert pickle_in_py
