"""
AADAP — ETL Pipeline Agent Prompt Templates
===============================================
Structured-output prompt definitions for the ETL Pipeline agent.

Supports three pipeline flavours:
- **DLT**: Delta Live Tables (Databricks)
- **Data Factory**: Data Factory pipelines (Fabric)
- **Transformation**: Pure transformation logic (platform-agnostic notebooks)

Each prompt produces a JSON artefact describing the full ETL pipeline:
transformations, pipeline definition, notebook code, data quality rules,
and optional schedule.
"""

from __future__ import annotations

from aadap.agents.prompts.base import PromptTemplate, StructuredOutput


# ── ETL Pipeline Output Schema ─────────────────────────────────────────

ETL_PIPELINE_SCHEMA = StructuredOutput(
    fields={
        "platform": "str — target platform: databricks | fabric",
        "pipeline_type": "str — dlt | workflow | datafactory",
        "transformations": "list[dict] — ordered transformation steps",
        "pipeline_definition": "dict — full pipeline / workflow definition",
        "notebooks": "list[dict] — notebook code artefacts (name, language, code)",
        "data_quality_rules": "list[dict] — expectations / quality checks",
        "code": "str — primary generated code",
        "language": "str — python | sql | scala",
        "explanation": "str — brief explanation of the pipeline",
        "schedule": "dict — scheduling configuration (cron, trigger, etc.)",
    },
    required={
        "platform",
        "pipeline_type",
        "transformations",
        "pipeline_definition",
        "code",
        "language",
        "explanation",
    },
)


# ── Shared constraints ─────────────────────────────────────────────────

_BASE_CONSTRAINTS: list[str] = [
    "Output ONLY a single valid JSON object — no surrounding text.",
    "Include error handling and structured logging in all generated code.",
    "Use idempotent patterns; re-runs must not corrupt data.",
    "Document any assumptions in the 'explanation' field.",
]


# ── DLT Pipeline Prompt (Databricks) ───────────────────────────────────

DLT_PIPELINE_PROMPT = PromptTemplate(
    name="dlt_pipeline",
    system_role=(
        "You are an expert Azure Databricks data engineer specialising in "
        "Delta Live Tables (DLT). Generate production-quality DLT pipeline "
        "definitions and notebook code that implement medallion-architecture "
        "transformations with built-in data quality expectations."
    ),
    constraints=[
        *_BASE_CONSTRAINTS,
        "Use @dlt.table and @dlt.view decorators for DLT definitions.",
        "Add @dlt.expect / @dlt.expect_or_drop / @dlt.expect_or_fail for data quality.",
        "Follow bronze → silver → gold medallion architecture where appropriate.",
        "Use spark.readStream for incremental processing when possible.",
        "Include DLT pipeline JSON definition in 'pipeline_definition'.",
    ],
    output_schema=ETL_PIPELINE_SCHEMA,
    task_instruction=(
        "Generate a Delta Live Tables pipeline for the following task:\n\n"
        "Task: {task_description}\n"
        "Platform: Azure Databricks\n"
        "Source Tables: {source_tables}\n"
        "Target Tables: {target_tables}\n"
        "Environment: {environment}\n"
        "Additional Context: {context}\n\n"
        "Provide the complete implementation including DLT notebook code "
        "and pipeline definition."
    ),
)


# ── Data Factory Pipeline Prompt (Fabric) ──────────────────────────────

FABRIC_PIPELINE_PROMPT = PromptTemplate(
    name="fabric_pipeline",
    system_role=(
        "You are an expert Microsoft Fabric data engineer specialising in "
        "Data Factory pipelines. Generate production-quality pipeline "
        "definitions that orchestrate data movement and transformation "
        "activities across Fabric lakehouses, warehouses, and notebooks."
    ),
    constraints=[
        *_BASE_CONSTRAINTS,
        "Use Fabric Data Factory activity types: Copy, Notebook, Dataflow, ForEach, If.",
        "Reference Fabric items by workspace and item name.",
        "Use parameterised pipelines for reusability.",
        "Include error handling activities (On Failure paths).",
        "Use Fabric-native connectors and linked services where available.",
    ],
    output_schema=ETL_PIPELINE_SCHEMA,
    task_instruction=(
        "Generate a Data Factory pipeline for the following task:\n\n"
        "Task: {task_description}\n"
        "Platform: Microsoft Fabric\n"
        "Source Tables: {source_tables}\n"
        "Target Tables: {target_tables}\n"
        "Environment: {environment}\n"
        "Additional Context: {context}\n\n"
        "Provide the complete implementation including pipeline JSON "
        "definition and any supporting notebook code."
    ),
)


# ── Transformation Prompt (platform-agnostic) ──────────────────────────

TRANSFORMATION_PROMPT = PromptTemplate(
    name="transformation",
    system_role=(
        "You are an expert data engineer specialising in PySpark and SQL "
        "transformations. Generate production-quality transformation code "
        "that can run on both Azure Databricks and Microsoft Fabric Spark. "
        "Focus on clean, testable transformation logic with data quality "
        "checks."
    ),
    constraints=[
        *_BASE_CONSTRAINTS,
        "Use PySpark DataFrame API for complex transformations.",
        "Use SQL for simple aggregation / filtering where clearer.",
        "Include column-level lineage comments.",
        "Add null / schema checks before and after transformation.",
        "Keep transformation logic separate from I/O (read/write).",
    ],
    output_schema=ETL_PIPELINE_SCHEMA,
    task_instruction=(
        "Generate transformation logic for the following task:\n\n"
        "Task: {task_description}\n"
        "Platform: {platform}\n"
        "Source Tables: {source_tables}\n"
        "Target Tables: {target_tables}\n"
        "Environment: {environment}\n"
        "Additional Context: {context}\n\n"
        "Provide the complete transformation implementation."
    ),
)


# ── Prompt Selection ────────────────────────────────────────────────────

_ETL_PIPELINE_PROMPTS: dict[str, PromptTemplate] = {
    "dlt": DLT_PIPELINE_PROMPT,
    "workflow": DLT_PIPELINE_PROMPT,        # Databricks workflow reuses DLT prompt
    "datafactory": FABRIC_PIPELINE_PROMPT,
    "transformation": TRANSFORMATION_PROMPT,
}


def get_etl_pipeline_prompt(pipeline_type: str) -> PromptTemplate:
    """Return the appropriate ETL pipeline prompt for the given type.

    Falls back to ``TRANSFORMATION_PROMPT`` for unrecognised types.
    """
    return _ETL_PIPELINE_PROMPTS.get(
        pipeline_type.lower(), TRANSFORMATION_PROMPT,
    )
