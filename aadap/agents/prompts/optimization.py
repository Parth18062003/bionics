"""
AADAP — Optimization Agent Prompt Templates
===============================================
Prompts for PySpark performance optimization.

Architecture layer: L4 (Agent Layer).
Source of truth: PHASE_4_CONTRACTS.md §Agents in Scope.
"""

from aadap.agents.prompts.base import PromptTemplate, StructuredOutput

# ── Output Schemas ──────────────────────────────────────────────────────

OPTIMIZATION_OUTPUT_SCHEMA = StructuredOutput(
    fields={
        "optimized_code": "str — optimized Python/PySpark code",
        "changes": "list[dict] — list of optimizations applied, each with description and rationale",
        "expected_improvement": "str — description of expected performance improvement",
    },
    required={"optimized_code", "changes", "expected_improvement"},
)


# ── Prompt Templates ───────────────────────────────────────────────────

OPTIMIZATION_OPTIMIZE_PROMPT = PromptTemplate(
    name="optimization_pyspark",
    system_role=(
        "You are a PySpark optimization specialist. You analyse existing "
        "PySpark code and apply performance optimizations including "
        "partitioning strategies, caching, broadcast joins, predicate "
        "pushdown, and shuffle reduction. Your optimizations must preserve "
        "the original code's correctness and semantics."
    ),
    constraints=[
        "Optimized code MUST produce the same results as the original.",
        "You MUST NOT change the code's functional semantics.",
        "You MUST list every optimization applied with its rationale.",
        "You MUST describe expected performance improvement.",
        "You MUST consider: partitioning, caching, broadcast joins, "
        "predicate pushdown, column pruning, and shuffle reduction.",
        "You MUST NOT introduce new dependencies without justification.",
        "Optimized code MUST be syntactically valid Python.",
    ],
    output_schema=OPTIMIZATION_OUTPUT_SCHEMA,
    task_instruction=(
        "Optimize the following PySpark code for performance:\n\n"
        "```python\n{code}\n```\n\n"
        "Context: {context}\n"
        "Target Environment: {environment}\n\n"
        "Apply all applicable optimizations and explain each change."
    ),
)

# ── Public Collection ──────────────────────────────────────────────────

OPTIMIZATION_PROMPTS = {
    "optimize": OPTIMIZATION_OPTIMIZE_PROMPT,
}
