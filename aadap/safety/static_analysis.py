"""
AADAP — Gate 1: Static Analysis
==================================
AST-based static analysis of generated Python and SQL code.

Architecture layer: L5 (Orchestration) — Safety Architecture.
Enforces:
- No destructive operation executes without detection
- No safety gate bypass (ARCHITECTURE.md)

Usage:
    analyzer = StaticAnalyzer()
    result = analyzer.evaluate(code, language="sql")
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from enum import StrEnum

from aadap.core.logging import get_logger

logger = get_logger(__name__)


# ── Risk Levels ─────────────────────────────────────────────────────────

class RiskLevel(StrEnum):
    """Risk severity levels for safety findings."""

    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# ── Risk ordering for comparison ────────────────────────────────────────

_RISK_ORDER: dict[RiskLevel, int] = {
    RiskLevel.NONE: 0,
    RiskLevel.LOW: 1,
    RiskLevel.MEDIUM: 2,
    RiskLevel.HIGH: 3,
    RiskLevel.CRITICAL: 4,
}


def max_risk(a: RiskLevel, b: RiskLevel) -> RiskLevel:
    """Return the higher of two risk levels."""
    return a if _RISK_ORDER[a] >= _RISK_ORDER[b] else b


# ── Data Objects ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Finding:
    """A single safety finding from analysis."""

    line: int
    pattern: str
    description: str
    severity: RiskLevel


@dataclass(frozen=True)
class RiskResult:
    """Result of a single safety gate evaluation."""

    passed: bool
    risk_level: RiskLevel
    findings: tuple[Finding, ...] = ()
    gate: str = ""

    @staticmethod
    def safe(gate: str) -> RiskResult:
        """Factory for a clean result."""
        return RiskResult(passed=True, risk_level=RiskLevel.NONE, gate=gate)


# ── SQL Destructive Patterns ───────────────────────────────────────────

_SQL_DESTRUCTIVE_PATTERNS: list[tuple[str, str, RiskLevel]] = [
    (r"\bDROP\s+TABLE\b", "DROP TABLE detected", RiskLevel.CRITICAL),
    (r"\bDROP\s+DATABASE\b", "DROP DATABASE detected", RiskLevel.CRITICAL),
    (r"\bDROP\s+SCHEMA\b", "DROP SCHEMA detected", RiskLevel.CRITICAL),
    (r"\bDROP\s+INDEX\b", "DROP INDEX detected", RiskLevel.HIGH),
    (r"\bTRUNCATE\b", "TRUNCATE detected", RiskLevel.CRITICAL),
    (r"\bDELETE\s+FROM\b", "DELETE FROM detected", RiskLevel.HIGH),
    (r"\bALTER\s+TABLE\b", "ALTER TABLE detected", RiskLevel.HIGH),
    (r"\bALTER\s+SCHEMA\b", "ALTER SCHEMA detected", RiskLevel.HIGH),
    (r"\bGRANT\s+", "GRANT statement detected", RiskLevel.HIGH),
    (r"\bREVOKE\s+", "REVOKE statement detected", RiskLevel.HIGH),
    (r"\bUPDATE\s+\S+\s+SET\b", "UPDATE SET detected", RiskLevel.MEDIUM),
    (r"\bINSERT\s+INTO\b", "INSERT INTO detected", RiskLevel.LOW),
]

# ── Python Dangerous Constructs ─────────────────────────────────────────

_PYTHON_DANGEROUS_CALLS: dict[str, tuple[str, RiskLevel]] = {
    "exec": ("exec() call detected — arbitrary code execution", RiskLevel.CRITICAL),
    "eval": ("eval() call detected — arbitrary code execution", RiskLevel.CRITICAL),
    "compile": ("compile() call detected — dynamic code compilation", RiskLevel.HIGH),
    "__import__": ("__import__() call detected — dynamic import", RiskLevel.HIGH),
}

_PYTHON_DANGEROUS_MODULES: dict[str, dict[str, tuple[str, RiskLevel]]] = {
    "os": {
        "system": ("os.system() call detected — shell execution", RiskLevel.CRITICAL),
        "popen": ("os.popen() call detected — shell execution", RiskLevel.CRITICAL),
        "remove": ("os.remove() call detected — file deletion", RiskLevel.HIGH),
        "unlink": ("os.unlink() call detected — file deletion", RiskLevel.HIGH),
        "rmdir": ("os.rmdir() call detected — directory deletion", RiskLevel.HIGH),
    },
    "subprocess": {
        "call": ("subprocess.call() detected — shell execution", RiskLevel.CRITICAL),
        "run": ("subprocess.run() detected — shell execution", RiskLevel.HIGH),
        "Popen": ("subprocess.Popen() detected — shell execution", RiskLevel.HIGH),
    },
    "shutil": {
        "rmtree": ("shutil.rmtree() detected — recursive deletion", RiskLevel.CRITICAL),
        "move": ("shutil.move() detected — file relocation", RiskLevel.MEDIUM),
    },
}


# ── Static Analyzer ────────────────────────────────────────────────────

class StaticAnalyzer:
    """
    Gate 1: AST-based static analysis.

    Detects destructive operations in Python code (via AST parsing)
    and SQL code (via keyword matching).
    """

    GATE_NAME = "static_analysis"

    def evaluate(self, code: str, language: str = "python") -> RiskResult:
        """
        Evaluate code for destructive operations.

        Parameters
        ----------
        code
            The source code to analyze.
        language
            ``"python"`` or ``"sql"``.

        Returns
        -------
        RiskResult
            Gate 1 result with all findings.
        """
        if not code or not code.strip():
            return RiskResult.safe(self.GATE_NAME)

        language = language.lower()
        if language == "python":
            return self._analyze_python(code)
        elif language == "sql":
            return self._analyze_sql(code)
        else:
            logger.warning(
                "static_analysis.unsupported_language",
                language=language,
            )
            return RiskResult.safe(self.GATE_NAME)

    # ── Python Analysis ─────────────────────────────────────────────

    def _analyze_python(self, code: str) -> RiskResult:
        """Parse Python code via AST and check for dangerous constructs."""
        findings: list[Finding] = []

        try:
            tree = ast.parse(code)
        except SyntaxError:
            # Unparseable code is suspicious but not necessarily destructive
            findings.append(
                Finding(
                    line=0,
                    pattern="SyntaxError",
                    description="Code could not be parsed — potential obfuscation",
                    severity=RiskLevel.MEDIUM,
                )
            )
            return self._build_result(findings)

        for node in ast.walk(tree):
            findings.extend(self._check_python_node(node))

        return self._build_result(findings)

    def _check_python_node(self, node: ast.AST) -> list[Finding]:
        """Check a single AST node for dangerous patterns."""
        findings: list[Finding] = []
        line = getattr(node, "lineno", 0)

        # Direct calls: exec(), eval(), etc.
        if isinstance(node, ast.Call):
            func = node.func

            # Simple name calls: exec(...)
            if isinstance(func, ast.Name) and func.id in _PYTHON_DANGEROUS_CALLS:
                desc, severity = _PYTHON_DANGEROUS_CALLS[func.id]
                findings.append(
                    Finding(line=line, pattern=func.id, description=desc, severity=severity)
                )

            # Attribute calls: os.system(...), subprocess.run(...)
            elif isinstance(func, ast.Attribute):
                if isinstance(func.value, ast.Name):
                    module = func.value.id
                    attr = func.attr
                    module_checks = _PYTHON_DANGEROUS_MODULES.get(module, {})
                    if attr in module_checks:
                        desc, severity = module_checks[attr]
                        findings.append(
                            Finding(line=line, pattern=f"{module}.{attr}", description=desc, severity=severity)
                        )

        # Import of dangerous modules
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in ("ctypes", "multiprocessing"):
                    findings.append(
                        Finding(
                            line=line,
                            pattern=f"import {alias.name}",
                            description=f"Import of sensitive module: {alias.name}",
                            severity=RiskLevel.MEDIUM,
                        )
                    )

        return findings

    # ── SQL Analysis ────────────────────────────────────────────────

    def _analyze_sql(self, code: str) -> RiskResult:
        """Check SQL code for destructive patterns via regex."""
        findings: list[Finding] = []
        upper_code = code.upper()

        for pattern, description, severity in _SQL_DESTRUCTIVE_PATTERNS:
            for match in re.finditer(pattern, upper_code, re.IGNORECASE):
                # Estimate line number
                line_num = code[:match.start()].count("\n") + 1
                findings.append(
                    Finding(
                        line=line_num,
                        pattern=pattern,
                        description=description,
                        severity=severity,
                    )
                )

        return self._build_result(findings)

    # ── Helpers ─────────────────────────────────────────────────────

    def _build_result(self, findings: list[Finding]) -> RiskResult:
        """Build a RiskResult from a list of findings."""
        if not findings:
            return RiskResult.safe(self.GATE_NAME)

        overall = RiskLevel.NONE
        for f in findings:
            overall = max_risk(overall, f.severity)

        passed = overall not in (RiskLevel.HIGH, RiskLevel.CRITICAL)

        logger.info(
            "static_analysis.result",
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
