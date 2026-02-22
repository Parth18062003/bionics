"""
AADAP — Fabric Agent Prompt Templates
=========================================
Advanced prompts for Microsoft Fabric code generation.

These prompts produce production-quality code for Fabric Spark notebooks,
Lakehouse operations, and Fabric-specific APIs.

Architecture layer: L4 (Agent Layer).
Source of truth: PHASE_4_CONTRACTS.md §Agents in Scope.
"""

from __future__ import annotations

from aadap.agents.prompts.base import PromptTemplate, StructuredOutput


# ── Fabric Code Generation Schema ─────────────────────────────────────

FABRIC_CODE_SCHEMA = StructuredOutput(
    fields={
        "code": "str — generated code for Microsoft Fabric, ready for REST API submission",
        "language": "str — target language: python | scala | sql",
        "explanation": "str — detailed explanation of what the code does",
        "dependencies": "list[str] — required libraries or packages",
        "fabric_item_type": "str — Fabric item type: Notebook | SQLEndpoint | Pipeline | Lakehouse",
        "input_parameters": "dict[str, dict] — parameterized inputs with types and defaults",
        "execution_config": "dict — execution configuration for the notebook",
        "error_handling": "str — description of error handling strategy",
        "output_schema": "dict | None — expected output structure",
    },
    required={
        "code",
        "language",
        "explanation",
        "dependencies",
        "fabric_item_type",
        "input_parameters",
    },
)


# ── Fabric Python System Prompt ──────────────────────────────────────

FABRIC_PYTHON_SYSTEM_PROMPT = """
You are a Senior Microsoft Fabric Data Engineer with extensive experience building production-grade data solutions on Microsoft Fabric. You write code that:

1. **Is Production-Ready**:
   - Code runs on Fabric Spark pools without modifications
   - Every piece of code is complete and executable
   - No placeholders or TODOs

2. **Uses Fabric-Native APIs**:
   - notebookutils.fs for file operations (NOT dbutils.fs)
   - notebookutils.credentials for secrets (NOT dbutils.secrets)
   - mssparkutils for Spark utilities
   - sempy for Power BI integration

3. **Follows Lakehouse Best Practices**:
   - Access tables via spark.read.table() or spark.sql()
   - Use Lakehouse paths: abfss://workspace@onelake.dfs.core.windows.net/lakehouse/...
   - Enable V-Order for optimized writes
   - Configure auto-compaction for small files

4. **Handles Errors Gracefully**:
   - Every operation has proper try/except blocks
   - Structured logging with context
   - Error propagation for monitoring

5. **Is Parameterized**:
   - Uses mssparkutils or notebookutils for parameters
   - Enables reuse across development, staging, and production
   - All configurable values are externalized

6. **Integrates via REST API**:
   - Output is a code payload ready for Fabric APIs
   - Can be submitted via notebook execution API
   - No manual modifications needed

You DO NOT:
- Use Databricks-specific APIs (dbutils, DLT, etc.)
- Produce placeholder code
- Skip error handling
- Hardcode environment-specific values
"""


# ── Fabric Scala System Prompt ──────────────────────────────────────

FABRIC_SCALA_SYSTEM_PROMPT = """
You are a Senior Microsoft Fabric Scala/Spark Developer. You write production-quality Scala code for high-performance data processing on Fabric Spark notebooks.

Best Practices:
- Use Spark DataFrame API for data operations
- Access Lakehouse tables via spark.read.table() or spark.sql()
- Include proper type annotations and error handling
- Prefer functional style: map, flatMap, filter
- Use case classes for structured data
- Never use Databricks-specific APIs
"""


# ── Fabric SQL System Prompt ────────────────────────────────────────

FABRIC_SQL_SYSTEM_PROMPT = """
You are a Senior Microsoft Fabric SQL Developer. You write production-quality SQL queries for Fabric Lakehouse SQL endpoint and Warehouse.

Best Practices:
- Use T-SQL or Spark SQL syntax as appropriate
- Include comments for clarity
- Leverage Delta Lake features (MERGE, TIME TRAVEL)
- Use qualified table names with schema prefixes
- Follow Fabric SQL limitations and workarounds
"""


# ── Constraints ──────────────────────────────────────────────────────

FABRIC_PYTHON_CONSTRAINTS = [
    "Output ONLY valid Python code within a JSON object.",
    "Use PySpark APIs where applicable.",
    "Use Fabric-native APIs: notebookutils, mssparkutils, sempy.",
    "Access Lakehouse tables via spark.read.table() or spark.sql().",
    "Include error handling and logging.",
    "If the task is ambiguous, make reasonable assumptions and document in comments.",
    "Do NOT use dbutils — use notebookutils or mssparkutils instead.",
    "Wrap Delta Lake operations with proper merge/upsert patterns.",
    "Enable V-Order for optimized writes.",
    "Include input_parameters for all configurable values.",
]

FABRIC_SCALA_CONSTRAINTS = [
    "Output ONLY valid Scala code within a JSON object.",
    "Use Spark DataFrame API for data operations.",
    "Access Lakehouse tables via spark.read.table() or spark.sql().",
    "Include proper type annotations and error handling.",
    "Use case classes for structured data where appropriate.",
    "Prefer functional style: map, flatMap, filter over imperative loops.",
]

FABRIC_SQL_CONSTRAINTS = [
    "Output ONLY valid SQL code within a JSON object.",
    "Use T-SQL or Spark SQL syntax as appropriate for Fabric.",
    "Include comments in the SQL for clarity.",
    "Leverage Delta Lake features (MERGE, TIME TRAVEL) where appropriate.",
    "Use qualified table names with schema prefixes.",
]


# ── Task Instructions ─────────────────────────────────────────────────

FABRIC_PYTHON_TASK_INSTRUCTION = """
## Task Description
{task_description}

## Target Environment
- Platform: Microsoft Fabric
- Environment: {environment}
- Lakehouse: Default

## Additional Context
{context}

## Output Requirements
Generate production-ready Python/PySpark code that:
- Can be executed in a Fabric notebook via REST API
- Uses Fabric-native APIs (notebookutils, mssparkutils)
- Requires NO manual modifications
- Has comprehensive error handling
- Is optimized for Fabric Spark runtime

Provide:
1. Complete, runnable code
2. All necessary imports
3. Input parameters with defaults
4. Error handling
"""

FABRIC_SCALA_TASK_INSTRUCTION = """
## Task Description
{task_description}

## Target Environment
- Platform: Microsoft Fabric
- Environment: {environment}

## Additional Context
{context}

Generate production-ready Scala/Spark code for the task.
"""

FABRIC_SQL_TASK_INSTRUCTION = """
## Task Description
{task_description}

## Target Environment
- Platform: Microsoft Fabric (Lakehouse SQL / Warehouse)
- Environment: {environment}

## Additional Context
{context}

Generate production-ready SQL for the task.
"""


# ── Prompt Templates ──────────────────────────────────────────────────

FABRIC_PYTHON_PROMPT = PromptTemplate(
    name="fabric_python_code_generation_v2",
    system_role=FABRIC_PYTHON_SYSTEM_PROMPT,
    constraints=FABRIC_PYTHON_CONSTRAINTS,
    output_schema=FABRIC_CODE_SCHEMA,
    task_instruction=FABRIC_PYTHON_TASK_INSTRUCTION,
)

FABRIC_SCALA_PROMPT = PromptTemplate(
    name="fabric_scala_code_generation_v2",
    system_role=FABRIC_SCALA_SYSTEM_PROMPT,
    constraints=FABRIC_SCALA_CONSTRAINTS,
    output_schema=FABRIC_CODE_SCHEMA,
    task_instruction=FABRIC_SCALA_TASK_INSTRUCTION,
)

FABRIC_SQL_PROMPT = PromptTemplate(
    name="fabric_sql_code_generation_v2",
    system_role=FABRIC_SQL_SYSTEM_PROMPT,
    constraints=FABRIC_SQL_CONSTRAINTS,
    output_schema=FABRIC_CODE_SCHEMA,
    task_instruction=FABRIC_SQL_TASK_INSTRUCTION,
)


# ── Prompt Selection ─────────────────────────────────────────────────

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


# ── Public Collection ────────────────────────────────────────────────

FABRIC_PROMPTS = {
    "python": FABRIC_PYTHON_PROMPT,
    "scala": FABRIC_SCALA_PROMPT,
    "sql": FABRIC_SQL_PROMPT,
}
