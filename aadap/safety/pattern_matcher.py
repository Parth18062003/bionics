"""
AADAP — Gate 2: Pattern Matching
===================================
Regex-based pattern matching for known dangerous patterns.

Architecture layer: L5 (Orchestration) — Safety Architecture.
Enforces:
- No destructive operation executes without detection
- No safety gate bypass (ARCHITECTURE.md)

Usage:
    matcher = PatternMatcher()
    result = matcher.evaluate(code, language="python")
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from aadap.core.logging import get_logger
from aadap.safety.static_analysis import (
    Finding,
    RiskLevel,
    RiskResult,
    max_risk,
)

logger = get_logger(__name__)


# ── Pattern Definition ──────────────────────────────────────────────────

@dataclass(frozen=True)
class DangerPattern:
    """A single dangerous pattern to match against code."""

    name: str
    regex: str
    description: str
    severity: RiskLevel
    language: str = "any"  # "any", "python", "sql"


# ── Built-in Pattern Registry ──────────────────────────────────────────

_BUILTIN_PATTERNS: list[DangerPattern] = [
    # Credential exposure
    DangerPattern(
        name="hardcoded_password",
        regex=r"""(?:password|passwd|pwd)\s*=\s*['"][^'"]{3,}['"]""",
        description="Hardcoded password detected",
        severity=RiskLevel.HIGH,
        language="any",
    ),
    DangerPattern(
        name="hardcoded_secret",
        regex=r"""(?:secret|api_key|apikey|token|auth_token)\s*=\s*['"][^'"]{8,}['"]""",
        description="Hardcoded secret/API key detected",
        severity=RiskLevel.HIGH,
        language="any",
    ),
    DangerPattern(
        name="connection_string",
        regex=r"""(?:jdbc:|Server=|Data Source=|mongodb://|postgresql://|mysql://)""",
        description="Database connection string detected",
        severity=RiskLevel.MEDIUM,
        language="any",
    ),
    DangerPattern(
        name="production_host",
        regex=r"""(?:prod(?:uction)?[\-_.](?:db|server|host|api)|\.prod\.)""",
        description="Production environment reference detected",
        severity=RiskLevel.HIGH,
        language="any",
    ),

    # Shell / filesystem destruction
    DangerPattern(
        name="rm_rf",
        regex=r"""rm\s+-(?:rf|fr)\s+/""",
        description="Recursive force-delete from root detected",
        severity=RiskLevel.CRITICAL,
        language="any",
    ),
    DangerPattern(
        name="format_command",
        regex=r"""\bFORMAT\s+[A-Z]:\b""",
        description="Disk FORMAT command detected",
        severity=RiskLevel.CRITICAL,
        language="any",
    ),

    # SQL-specific dangerous patterns
    DangerPattern(
        name="disable_trigger",
        regex=r"""\bDISABLE\s+TRIGGER\b""",
        description="DISABLE TRIGGER detected — safety control bypass",
        severity=RiskLevel.CRITICAL,
        language="sql",
    ),
    DangerPattern(
        name="grant_all",
        regex=r"""\bGRANT\s+ALL\b""",
        description="GRANT ALL detected — excessive privilege escalation",
        severity=RiskLevel.HIGH,
        language="sql",
    ),
    DangerPattern(
        name="no_where_delete",
        regex=r"""\bDELETE\s+FROM\s+\w+\s*;""",
        description="DELETE without WHERE clause — full table wipe",
        severity=RiskLevel.CRITICAL,
        language="sql",
    ),
    DangerPattern(
        name="drop_if_exists",
        regex=r"""\bDROP\s+\w+\s+IF\s+EXISTS\b""",
        description="DROP IF EXISTS detected — silent destruction",
        severity=RiskLevel.HIGH,
        language="sql",
    ),

    # Python-specific patterns
    DangerPattern(
        name="pickle_load",
        regex=r"""\bpickle\.loads?\b""",
        description="pickle.load() detected — arbitrary code execution risk",
        severity=RiskLevel.HIGH,
        language="python",
    ),
    DangerPattern(
        name="yaml_unsafe_load",
        regex=r"""\byaml\.(?:unsafe_)?load\b""",
        description="yaml.load() detected — potential code execution",
        severity=RiskLevel.MEDIUM,
        language="python",
    ),
]


# ── Pattern Matcher ─────────────────────────────────────────────────────

class PatternMatcher:
    """
    Gate 2: Regex-based pattern matching.

    Scans code against a registry of known dangerous patterns.
    Supports built-in patterns and custom pattern registration.
    """

    GATE_NAME = "pattern_matcher"

    def __init__(self) -> None:
        self._patterns: list[DangerPattern] = list(_BUILTIN_PATTERNS)

    @property
    def pattern_count(self) -> int:
        """Number of registered patterns."""
        return len(self._patterns)

    def add_pattern(self, pattern: DangerPattern) -> None:
        """Register an additional danger pattern."""
        self._patterns.append(pattern)
        logger.info(
            "pattern_matcher.pattern_added",
            name=pattern.name,
            severity=pattern.severity.value,
        )

    def remove_pattern(self, name: str) -> bool:
        """
        Remove a pattern by name.

        Returns ``True`` if a pattern was removed, ``False`` if not found.
        """
        before = len(self._patterns)
        self._patterns = [p for p in self._patterns if p.name != name]
        removed = len(self._patterns) < before
        if removed:
            logger.info("pattern_matcher.pattern_removed", name=name)
        return removed

    def evaluate(self, code: str, language: str = "python") -> RiskResult:
        """
        Evaluate code against all applicable patterns.

        Parameters
        ----------
        code
            The source code to scan.
        language
            ``"python"`` or ``"sql"``.

        Returns
        -------
        RiskResult
            Gate 2 result with all findings.
        """
        if not code or not code.strip():
            return RiskResult.safe(self.GATE_NAME)

        language = language.lower()
        findings: list[Finding] = []

        for pattern in self._patterns:
            # Apply patterns that match the language or are universal
            if pattern.language not in ("any", language):
                continue

            for match in re.finditer(pattern.regex, code, re.IGNORECASE):
                line_num = code[:match.start()].count("\n") + 1
                findings.append(
                    Finding(
                        line=line_num,
                        pattern=pattern.name,
                        description=pattern.description,
                        severity=pattern.severity,
                    )
                )

        return self._build_result(findings)

    def _build_result(self, findings: list[Finding]) -> RiskResult:
        """Build a RiskResult from findings."""
        if not findings:
            return RiskResult.safe(self.GATE_NAME)

        overall = RiskLevel.NONE
        for f in findings:
            overall = max_risk(overall, f.severity)

        passed = overall not in (RiskLevel.HIGH, RiskLevel.CRITICAL)

        logger.info(
            "pattern_matcher.result",
            finding_count=len(findings),
            risk_level=overall.value,
            passed=passed,
        )

        return RiskResult(
            passed=passed,
            risk_level=overall,
            findings=tuple(findings),
            gate=self.GATE_NAME,
        )
