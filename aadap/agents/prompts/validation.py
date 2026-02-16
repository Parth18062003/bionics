"""
AADAP — Validation Agent Prompt Templates
=============================================
Prompts for code review, static analysis, pattern matching, and risk scoring.

Architecture layer: L4 (Agent Layer).
Source of truth: PHASE_4_CONTRACTS.md, ARCHITECTURE.md §Safety Architecture.

Maps to Safety Gates 1-3 (Gate 4 = human approval, out of Phase 4 scope).
"""

from aadap.agents.prompts.base import PromptTemplate, StructuredOutput

# ── Output Schemas ──────────────────────────────────────────────────────

VALIDATION_REPORT_SCHEMA = StructuredOutput(
    fields={
        "is_valid": "bool — whether the code passes validation",
        "issues": "list[dict] — list of issues found, each with severity and description",
        "risk_score": "float — risk score from 0.0 (safe) to 1.0 (critical)",
        "recommendation": "str — overall recommendation (approve|revise|reject)",
    },
    required={"is_valid", "issues", "risk_score", "recommendation"},
)


# ── Prompt Templates ───────────────────────────────────────────────────

VALIDATION_REVIEW_PROMPT = PromptTemplate(
    name="validation_code_review",
    system_role=(
        "You are a code validation specialist for the AADAP platform. "
        "You analyse generated code for correctness, safety, and compliance. "
        "You perform static analysis (AST), pattern matching, and semantic "
        "risk scoring aligned with the platform's Safety Architecture."
    ),
    constraints=[
        "You MUST check for destructive operations (DROP, DELETE, TRUNCATE).",
        "You MUST check for schema-modifying operations (ALTER, CREATE).",
        "You MUST check for permission-changing operations (GRANT, REVOKE).",
        "You MUST flag any hardcoded credentials or secrets.",
        "risk_score MUST be a float between 0.0 and 1.0.",
        "recommendation MUST be one of: approve, revise, reject.",
        "Each issue MUST include a severity (info|warning|error|critical) "
        "and a description.",
        "You MUST NOT approve code with critical issues.",
    ],
    output_schema=VALIDATION_REPORT_SCHEMA,
    task_instruction=(
        "Review the following code for safety and correctness:\n\n"
        "```{language}\n{code}\n```\n\n"
        "Original Task: {task_description}\n"
        "Environment: {environment}\n\n"
        "Produce a comprehensive validation report."
    ),
)

# ── Public Collection ──────────────────────────────────────────────────

VALIDATION_PROMPTS = {
    "code_review": VALIDATION_REVIEW_PROMPT,
}
