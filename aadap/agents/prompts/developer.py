"""
AADAP — Developer Agent Prompt Templates
============================================
Prompts for Databricks Python / PySpark code generation.

Architecture layer: L4 (Agent Layer).
Source of truth: PHASE_4_CONTRACTS.md §Agents in Scope.
"""

from aadap.agents.prompts.base import PromptTemplate, StructuredOutput

# ── Output Schemas ──────────────────────────────────────────────────────

DEVELOPER_CODE_SCHEMA = StructuredOutput(
    fields={
        "code": "str — generated Python/PySpark code",
        "language": "str — language identifier (python|pyspark)",
        "explanation": "str — explanation of the code logic",
        "dependencies": "list[str] — required packages or imports",
    },
    required={"code", "language", "explanation", "dependencies"},
)


# ── Prompt Templates ───────────────────────────────────────────────────

DEVELOPER_CODE_PROMPT = PromptTemplate(
    name="developer_code_generation",
    system_role=(
        "You are an expert Databricks Python developer. You generate "
        "production-quality PySpark and Python code for data engineering "
        "tasks on the Databricks platform. Your code must be correct, "
        "efficient, and follow Databricks best practices."
    ),
    constraints=[
        "Generated code MUST be syntactically valid Python.",
        "You MUST use PySpark APIs where applicable.",
        "You MUST list ALL required dependencies and imports.",
        "Code MUST NOT contain destructive operations (DROP, DELETE) "
        "unless explicitly requested in the task description.",
        "You MUST include error handling in generated code.",
        "Code MUST follow PEP 8 style conventions.",
        "You MUST explain your implementation approach.",
    ],
    output_schema=DEVELOPER_CODE_SCHEMA,
    task_instruction=(
        "Generate code for the following task:\n\n"
        "Task: {task_description}\n"
        "Target Environment: {environment}\n"
        "Additional Context: {context}\n\n"
        "Provide the complete implementation."
    ),
)


# ── Public Collection ──────────────────────────────────────────────────

DEVELOPER_PROMPTS = {
    "code_generation": DEVELOPER_CODE_PROMPT,
}
