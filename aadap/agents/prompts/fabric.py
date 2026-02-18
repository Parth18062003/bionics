"""
AADAP — Fabric Agent Prompt Templates
=========================================
Structured-output prompt definitions for the Fabric agent.

Mirrors the developer.py pattern but targets Microsoft Fabric workloads:
- Python/PySpark notebooks on Fabric Spark
- Scala/Spark notebooks on Fabric
- SQL queries on Fabric Lakehouse SQL endpoint
"""

from __future__ import annotations

from aadap.agents.prompts.base import PromptTemplate, StructuredOutput


# ── Fabric Code Generation Schema ─────────────────────────────────────

FABRIC_CODE_SCHEMA = StructuredOutput(
    fields={
        "code": "str — generated code for Microsoft Fabric",
        "language": "str — target language: python | scala | sql",
        "explanation": "str — brief explanation of what the code does",
        "dependencies": "list[str] — required libraries or packages",
        "fabric_item_type": "str — Fabric item type: Notebook | SQLEndpoint | Pipeline",
    },
    required={"code", "language", "explanation",
              "dependencies", "fabric_item_type"},
)


# ── Fabric Python Prompt ──────────────────────────────────────────────

FABRIC_PYTHON_PROMPT = PromptTemplate(
    name="fabric_python_code_generation",
    system_role=(
        "You are an expert Microsoft Fabric Python/PySpark developer. "
        "Generate production-quality Python code for data engineering tasks "
        "on Microsoft Fabric Spark notebooks."
    ),
    constraints=[
        "Output ONLY valid Python code within a JSON object.",
        "Use PySpark APIs where applicable.",
        "Use Fabric-native APIs: notebookutils, mssparkutils, sempy.",
        "Access Lakehouse tables via spark.read.table() or spark.sql().",
        "Include error handling and logging.",
        "If the task is ambiguous, make reasonable assumptions and document in comments.",
        "Do NOT use dbutils — use notebookutils or mssparkutils instead.",
        "Wrap Delta Lake operations with proper merge/upsert patterns.",
    ],
    output_schema=FABRIC_CODE_SCHEMA,
    task_instruction=(
        "Generate code for the following task:\n\n"
        "Task: {task_description}\n"
        "Target Environment: {environment}\n"
        "Platform: Microsoft Fabric\n"
        "Additional Context: {context}\n\n"
        "Provide the complete implementation."
    ),
)


# ── Fabric Scala Prompt ──────────────────────────────────────────────

FABRIC_SCALA_PROMPT = PromptTemplate(
    name="fabric_scala_code_generation",
    system_role=(
        "You are an expert Microsoft Fabric Scala/Spark developer. "
        "Generate production-quality Scala code for high-performance data "
        "processing tasks on Microsoft Fabric Spark notebooks."
    ),
    constraints=[
        "Output ONLY valid Scala code within a JSON object.",
        "Use Spark DataFrame API for data operations.",
        "Access Lakehouse tables via spark.read.table() or spark.sql().",
        "Include proper type annotations and error handling.",
        "Use case classes for structured data where appropriate.",
        "If the task is ambiguous, make reasonable assumptions and document in comments.",
        "Prefer functional style: map, flatMap, filter over imperative loops.",
    ],
    output_schema=FABRIC_CODE_SCHEMA,
    task_instruction=(
        "Generate code for the following task:\n\n"
        "Task: {task_description}\n"
        "Target Environment: {environment}\n"
        "Platform: Microsoft Fabric\n"
        "Additional Context: {context}\n\n"
        "Provide the complete implementation."
    ),
)


# ── Fabric SQL Prompt ────────────────────────────────────────────────

FABRIC_SQL_PROMPT = PromptTemplate(
    name="fabric_sql_code_generation",
    system_role=(
        "You are an expert Microsoft Fabric SQL developer. "
        "Generate production-quality SQL queries for data engineering tasks "
        "on Fabric Lakehouse SQL endpoint or Warehouse."
    ),
    constraints=[
        "Output ONLY valid SQL code within a JSON object.",
        "Use T-SQL or Spark SQL syntax as appropriate for Fabric.",
        "Include comments in the SQL for clarity.",
        "Leverage Delta Lake features (MERGE, TIME TRAVEL) where appropriate.",
        "If the task is ambiguous, make reasonable assumptions and document in comments.",
        "Use qualified table names with schema prefixes.",
    ],
    output_schema=FABRIC_CODE_SCHEMA,
    task_instruction=(
        "Generate code for the following task:\n\n"
        "Task: {task_description}\n"
        "Target Environment: {environment}\n"
        "Platform: Microsoft Fabric (Lakehouse SQL / Warehouse)\n"
        "Additional Context: {context}\n\n"
        "Provide the complete implementation."
    ),
)


def get_fabric_prompt(language: str) -> PromptTemplate:
    """Return the appropriate Fabric prompt template for the given language."""
    prompts = {
        "python": FABRIC_PYTHON_PROMPT,
        "scala": FABRIC_SCALA_PROMPT,
        "sql": FABRIC_SQL_PROMPT,
    }
    return prompts.get(language.lower(), FABRIC_PYTHON_PROMPT)


def build_fabric_code_gen_prompt(
    title: str,
    description: str | None,
    environment: str,
    language: str,
) -> str:
    """Build a complete code-generation prompt for Fabric tasks."""
    template = get_fabric_prompt(language)

    task_description = title
    if description:
        task_description += f"\n\nDetails:\n{description}"

    context = f"Language: {language}, Lakehouse-backed data access"

    return template.render({
        "task_description": task_description,
        "environment": environment,
        "context": context,
    })
