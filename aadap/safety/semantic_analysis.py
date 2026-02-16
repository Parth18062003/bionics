"""
AADAP — Gate 3: Semantic Risk Scoring + Safety Pipeline
==========================================================
Aggregates findings from Gate 1 (static analysis) and Gate 2 (pattern
matching) into a composite risk score, then orchestrates the full
3-gate safety pipeline.

Architecture layer: L5 (Orchestration) — Safety Architecture.
Enforces:
- No gate may be bypassed (ARCHITECTURE.md)
- All 3 gates always run (unless CRITICAL short-circuit)

Usage:
    pipeline = SafetyPipeline()
    result = pipeline.evaluate(code, language="sql")
"""

from __future__ import annotations

from dataclasses import dataclass, field

from aadap.core.logging import get_logger
from aadap.safety.static_analysis import (
    Finding,
    RiskLevel,
    RiskResult,
    StaticAnalyzer,
    max_risk,
    _RISK_ORDER,
)
from aadap.safety.pattern_matcher import PatternMatcher

logger = get_logger(__name__)


# ── Pipeline Result ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class PipelineResult:
    """Aggregated result from the full safety pipeline (Gates 1–3)."""

    gate_results: tuple[RiskResult, ...]
    overall_risk: RiskLevel
    requires_approval: bool
    summary: str

    @property
    def passed(self) -> bool:
        """Pipeline passes if overall risk is below HIGH."""
        return self.overall_risk not in (RiskLevel.HIGH, RiskLevel.CRITICAL)

    @property
    def all_findings(self) -> tuple[Finding, ...]:
        """Flatten all findings from all gates."""
        findings: list[Finding] = []
        for r in self.gate_results:
            findings.extend(r.findings)
        return tuple(findings)


# ── Semantic Analyzer (Gate 3) ──────────────────────────────────────────

class SemanticAnalyzer:
    """
    Gate 3: Semantic risk scoring.

    Combines findings from Gate 1 and Gate 2 to compute an aggregate
    risk level.  Considers the density of findings and the maximum
    severity to determine overall risk.
    """

    GATE_NAME = "semantic_analysis"

    def evaluate(
        self,
        code: str,
        language: str,
        gate1_result: RiskResult,
        gate2_result: RiskResult,
    ) -> RiskResult:
        """
        Compute aggregate risk from Gate 1 and Gate 2 results.

        Parameters
        ----------
        code
            The original source code (for line count context).
        language
            ``"python"`` or ``"sql"``.
        gate1_result
            Result from StaticAnalyzer.
        gate2_result
            Result from PatternMatcher.

        Returns
        -------
        RiskResult
            Gate 3 aggregated result.
        """
        all_findings = list(gate1_result.findings) + list(gate2_result.findings)

        if not all_findings:
            return RiskResult.safe(self.GATE_NAME)

        # Determine the maximum severity across all findings
        highest_risk = RiskLevel.NONE
        for f in all_findings:
            highest_risk = max_risk(highest_risk, f.severity)

        # Density scoring: many findings suggest systematic risk
        line_count = max(code.count("\n") + 1, 1)
        finding_density = len(all_findings) / line_count

        # Escalate risk if high density of findings
        if finding_density > 0.5 and _RISK_ORDER[highest_risk] < _RISK_ORDER[RiskLevel.HIGH]:
            highest_risk = RiskLevel.HIGH

        # If multiple CRITICAL findings, keep CRITICAL
        critical_count = sum(
            1 for f in all_findings if f.severity == RiskLevel.CRITICAL
        )

        # Build semantic finding
        semantic_finding = Finding(
            line=0,
            pattern="aggregate_risk",
            description=(
                f"Semantic analysis: {len(all_findings)} finding(s), "
                f"density={finding_density:.2f}, "
                f"critical_count={critical_count}, "
                f"max_severity={highest_risk.value}"
            ),
            severity=highest_risk,
        )

        passed = highest_risk not in (RiskLevel.HIGH, RiskLevel.CRITICAL)

        logger.info(
            "semantic_analysis.result",
            total_findings=len(all_findings),
            density=round(finding_density, 2),
            critical_count=critical_count,
            risk_level=highest_risk.value,
            passed=passed,
        )

        return RiskResult(
            passed=passed,
            risk_level=highest_risk,
            findings=tuple(all_findings) + (semantic_finding,),
            gate=self.GATE_NAME,
        )


# ── Safety Pipeline ─────────────────────────────────────────────────────

class SafetyPipeline:
    """
    Orchestrates the full 3-gate safety pipeline.

    Contract: No gate may be bypassed (ARCHITECTURE.md).
    All 3 gates always execute.  If Gate 1 or Gate 2 returns CRITICAL,
    the pipeline still runs remaining gates but marks the result
    as requiring approval.
    """

    def __init__(
        self,
        static_analyzer: StaticAnalyzer | None = None,
        pattern_matcher: PatternMatcher | None = None,
        semantic_analyzer: SemanticAnalyzer | None = None,
    ) -> None:
        self._static = static_analyzer or StaticAnalyzer()
        self._pattern = pattern_matcher or PatternMatcher()
        self._semantic = semantic_analyzer or SemanticAnalyzer()

    def evaluate(self, code: str, language: str = "python") -> PipelineResult:
        """
        Run all 3 safety gates sequentially.

        Parameters
        ----------
        code
            The source code to evaluate.
        language
            ``"python"`` or ``"sql"``.

        Returns
        -------
        PipelineResult
            Aggregated result from all gates.
        """
        logger.info(
            "safety_pipeline.start",
            language=language,
            code_length=len(code),
        )

        # Gate 1: Static analysis — always runs
        gate1 = self._static.evaluate(code, language)

        # Gate 2: Pattern matching — always runs (no bypass)
        gate2 = self._pattern.evaluate(code, language)

        # Gate 3: Semantic analysis — always runs (no bypass)
        gate3 = self._semantic.evaluate(code, language, gate1, gate2)

        # Compute overall risk as the maximum across all gates
        overall = RiskLevel.NONE
        for result in (gate1, gate2, gate3):
            overall = max_risk(overall, result.risk_level)

        # Determine if approval is required
        requires_approval = overall in (RiskLevel.HIGH, RiskLevel.CRITICAL)

        # Build summary
        summary_parts = []
        for result in (gate1, gate2, gate3):
            status = "PASS" if result.passed else "FAIL"
            summary_parts.append(
                f"{result.gate}: {status} ({result.risk_level.value}, "
                f"{len(result.findings)} finding(s))"
            )
        summary = " | ".join(summary_parts)

        logger.info(
            "safety_pipeline.complete",
            overall_risk=overall.value,
            requires_approval=requires_approval,
            summary=summary,
        )

        return PipelineResult(
            gate_results=(gate1, gate2, gate3),
            overall_risk=overall,
            requires_approval=requires_approval,
            summary=summary,
        )
