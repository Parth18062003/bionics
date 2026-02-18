"""
AADAP — Ingestion Agent Prompt Templates
============================================
Structured-output prompt definitions for the Ingestion agent.

Supports three ingestion modes:
- **Batch**: Auto Loader, Copy Activity, bulk file loads
- **Streaming**: Kafka, Event Hubs, streaming tables
- **CDC**: Change Data Capture patterns (Debezium, CDF, etc.)

Each prompt targets either Azure Databricks or Microsoft Fabric and
produces a JSON artefact describing the full ingestion pipeline:
source, target, generated code, resource configuration, and schedule.
"""

from __future__ import annotations

from aadap.agents.prompts.base import PromptTemplate, StructuredOutput


# ── Ingestion Output Schema ────────────────────────────────────────────

INGESTION_SCHEMA = StructuredOutput(
    fields={
        "platform": "str — target platform: databricks | fabric",
        "ingestion_type": "str — batch | streaming | cdc",
        "source": "dict — source configuration (type, location, format, options)",
        "target": "dict — target configuration (table, schema, format, mode)",
        "code": "str — generated ingestion code",
        "language": "str — python | sql | scala",
        "explanation": "str — brief explanation of the ingestion pipeline",
        "resource_config": "dict — compute/resource configuration",
        "checkpoint_location": "str — checkpoint path for exactly-once semantics",
        "schedule": "dict — scheduling configuration (cron, trigger, etc.)",
    },
    required={
        "platform",
        "ingestion_type",
        "source",
        "target",
        "code",
        "language",
        "explanation",
    },
)


# ── Shared constraints ─────────────────────────────────────────────────

_BASE_CONSTRAINTS: list[str] = [
    "Output ONLY a single valid JSON object — no surrounding text.",
    "Include error handling and structured logging in all generated code.",
    "Use idempotent patterns; re-runs must not duplicate data.",
    "Document any assumptions in the 'explanation' field.",
]


# ── Batch Ingestion Prompt ──────────────────────────────────────────────

BATCH_INGESTION_PROMPT = PromptTemplate(
    name="batch_ingestion",
    system_role=(
        "You are an expert data engineer specialising in batch data "
        "ingestion on Azure Databricks and Microsoft Fabric. "
        "Generate production-quality code that loads data from files, "
        "APIs, or databases into a lakehouse table using best practices "
        "such as Auto Loader (Databricks) or Copy Activity (Fabric)."
    ),
    constraints=[
        *_BASE_CONSTRAINTS,
        "Prefer Auto Loader (cloudFiles) on Databricks for incremental file ingestion.",
        "Prefer Copy Activity or Dataflow Gen2 on Fabric for bulk loads.",
        "Always specify a checkpoint_location for restartable loads.",
        "Use MERGE/upsert when the write mode is 'merge'.",
        "Partition large tables by date or another high-cardinality column when appropriate.",
    ],
    output_schema=INGESTION_SCHEMA,
    task_instruction=(
        "Generate a batch ingestion pipeline for the following task:\n\n"
        "Task: {task_description}\n"
        "Platform: {platform}\n"
        "Source: {source_description}\n"
        "Target: {target_description}\n"
        "Environment: {environment}\n"
        "Additional Context: {context}\n\n"
        "Provide the complete implementation."
    ),
)


# ── Streaming Ingestion Prompt ──────────────────────────────────────────

STREAMING_INGESTION_PROMPT = PromptTemplate(
    name="streaming_ingestion",
    system_role=(
        "You are an expert data engineer specialising in real-time "
        "streaming ingestion on Azure Databricks and Microsoft Fabric. "
        "Generate production-quality code that consumes events from "
        "Kafka, Azure Event Hubs, or other streaming sources and writes "
        "them to a Delta table with exactly-once semantics."
    ),
    constraints=[
        *_BASE_CONSTRAINTS,
        "Use Structured Streaming (readStream/writeStream) on Databricks.",
        "Use Event Streams or Spark Structured Streaming on Fabric.",
        "Always configure a checkpoint_location for fault tolerance.",
        "Include watermarking for late-arriving data when relevant.",
        "Prefer trigger(availableNow=True) for micro-batch catch-up unless "
        "continuous processing is requested.",
    ],
    output_schema=INGESTION_SCHEMA,
    task_instruction=(
        "Generate a streaming ingestion pipeline for the following task:\n\n"
        "Task: {task_description}\n"
        "Platform: {platform}\n"
        "Source: {source_description}\n"
        "Target: {target_description}\n"
        "Environment: {environment}\n"
        "Additional Context: {context}\n\n"
        "Provide the complete implementation."
    ),
)


# ── CDC Ingestion Prompt ────────────────────────────────────────────────

CDC_INGESTION_PROMPT = PromptTemplate(
    name="cdc_ingestion",
    system_role=(
        "You are an expert data engineer specialising in Change Data "
        "Capture (CDC) pipelines on Azure Databricks and Microsoft Fabric. "
        "Generate production-quality code that captures inserts, updates, "
        "and deletes from a source system and applies them to a target "
        "Delta table using SCD Type 1 or Type 2 patterns."
    ),
    constraints=[
        *_BASE_CONSTRAINTS,
        "Use Delta Change Data Feed (CDF) on Databricks when the source is a Delta table.",
        "Use Debezium or equivalent CDC connectors for database sources.",
        "Apply changes via MERGE INTO with proper match conditions.",
        "Support SCD Type 1 (overwrite) and Type 2 (historical tracking) patterns.",
        "Include a '_cdc_operation' or similar audit column to track change type.",
    ],
    output_schema=INGESTION_SCHEMA,
    task_instruction=(
        "Generate a CDC ingestion pipeline for the following task:\n\n"
        "Task: {task_description}\n"
        "Platform: {platform}\n"
        "Source: {source_description}\n"
        "Target: {target_description}\n"
        "Environment: {environment}\n"
        "Additional Context: {context}\n\n"
        "Provide the complete implementation."
    ),
)


# ── Prompt Selection ────────────────────────────────────────────────────

_INGESTION_PROMPTS: dict[str, PromptTemplate] = {
    "batch": BATCH_INGESTION_PROMPT,
    "streaming": STREAMING_INGESTION_PROMPT,
    "cdc": CDC_INGESTION_PROMPT,
}


def get_ingestion_prompt(ingestion_type: str) -> PromptTemplate:
    """Return the appropriate ingestion prompt for the given type.

    Falls back to ``BATCH_INGESTION_PROMPT`` for unrecognised types.
    """
    return _INGESTION_PROMPTS.get(ingestion_type.lower(), BATCH_INGESTION_PROMPT)
