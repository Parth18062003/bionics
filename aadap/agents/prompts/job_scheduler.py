"""
AADAP — Job Scheduler Agent Prompt Templates
================================================
Structured-output prompt definitions for the Job Scheduler agent.

Supports three scheduling concerns:
- **Job creation**: Multi-task job / workflow definitions
- **Schedule config**: Cron expressions, event triggers, retry policies
- **DAG building**: Task dependency graphs with parallelism

Each prompt targets either Azure Databricks or Microsoft Fabric and
produces a JSON artefact with the full job definition, schedule, and
optional job ID from platform creation.
"""

from __future__ import annotations

from aadap.agents.prompts.base import PromptTemplate, StructuredOutput


# ── Job Scheduler Output Schema ────────────────────────────────────────

JOB_SCHEDULER_SCHEMA = StructuredOutput(
    fields={
        "platform": "str — target platform: databricks | fabric",
        "job_type": "str — notebook | spark | pipeline | dbt",
        "job_definition": (
            "dict — full job definition including name, tasks, schedule, "
            "triggers, cluster_spec"
        ),
        "code": "str — generated code or JSON definition",
        "language": "str — python | sql | json",
        "explanation": "str — brief explanation of the job / schedule",
        "job_id": "str | None — platform job ID if created",
        "created": "bool — whether the job was created on the platform",
    },
    required={
        "platform",
        "job_type",
        "job_definition",
        "code",
        "language",
        "explanation",
    },
)


# ── Shared constraints ─────────────────────────────────────────────────

_BASE_CONSTRAINTS: list[str] = [
    "Output ONLY a single valid JSON object — no surrounding text.",
    "Include error handling and retry logic in all job definitions.",
    "Use idempotent task configurations; re-runs must be safe.",
    "Document any assumptions in the 'explanation' field.",
]


# ── Job Creation Prompt ─────────────────────────────────────────────────

JOB_CREATION_PROMPT = PromptTemplate(
    name="job_creation",
    system_role=(
        "You are an expert data platform engineer specialising in "
        "multi-task job orchestration on Azure Databricks and Microsoft "
        "Fabric.  Generate production-quality job definitions with "
        "proper task dependencies, cluster sizing, retry policies, and "
        "notification settings."
    ),
    constraints=[
        *_BASE_CONSTRAINTS,
        "Use Databricks Jobs API v2.1 JSON format for Databricks jobs.",
        "Use Fabric Data Factory pipeline JSON for Fabric jobs.",
        "Define task dependencies explicitly (depends_on / precedence).",
        "Include cluster_spec with auto-scaling where appropriate.",
        "Set max_retries and timeout_seconds on each task.",
        "Add email/webhook notifications for failure and SLA breach.",
    ],
    output_schema=JOB_SCHEDULER_SCHEMA,
    task_instruction=(
        "Generate a multi-task job definition for the following:\n\n"
        "Task: {task_description}\n"
        "Platform: {platform}\n"
        "Job Type: {job_type}\n"
        "Tasks / Steps: {tasks_description}\n"
        "Environment: {environment}\n"
        "Additional Context: {context}\n\n"
        "Provide the complete job definition."
    ),
)


# ── Schedule Configuration Prompt ──────────────────────────────────────

SCHEDULE_CONFIG_PROMPT = PromptTemplate(
    name="schedule_config",
    system_role=(
        "You are an expert in job scheduling for Azure Databricks and "
        "Microsoft Fabric.  Generate cron schedules, event-based "
        "triggers, and retry / timeout policies that balance freshness "
        "requirements with cost efficiency."
    ),
    constraints=[
        *_BASE_CONSTRAINTS,
        "Use Quartz cron syntax for Databricks schedules.",
        "Use Data Factory trigger definitions for Fabric.",
        "Include timezone specification (default UTC).",
        "Add retry policies with exponential back-off where appropriate.",
        "Consider maintenance windows and SLA requirements.",
    ],
    output_schema=JOB_SCHEDULER_SCHEMA,
    task_instruction=(
        "Generate a schedule / trigger configuration for the following:\n\n"
        "Task: {task_description}\n"
        "Platform: {platform}\n"
        "Freshness Requirement: {freshness}\n"
        "Tasks / Steps: {tasks_description}\n"
        "Environment: {environment}\n"
        "Additional Context: {context}\n\n"
        "Provide the complete schedule configuration."
    ),
)


# ── DAG Builder Prompt ──────────────────────────────────────────────────

DAG_BUILDER_PROMPT = PromptTemplate(
    name="dag_builder",
    system_role=(
        "You are an expert in building task dependency graphs (DAGs) for "
        "data platform jobs on Azure Databricks and Microsoft Fabric. "
        "Generate optimal DAGs that maximise parallelism while respecting "
        "data dependencies and resource constraints."
    ),
    constraints=[
        *_BASE_CONSTRAINTS,
        "Represent tasks as a list with explicit depends_on references.",
        "Maximise parallelism: independent tasks should run concurrently.",
        "Include resource constraints (max concurrent tasks, cluster pools).",
        "Add checkpoint / gate tasks for critical validation steps.",
        "Use clear, descriptive task_key / activity names.",
    ],
    output_schema=JOB_SCHEDULER_SCHEMA,
    task_instruction=(
        "Generate a task DAG for the following workflow:\n\n"
        "Task: {task_description}\n"
        "Platform: {platform}\n"
        "Tasks / Steps: {tasks_description}\n"
        "Dependencies: {dependencies}\n"
        "Environment: {environment}\n"
        "Additional Context: {context}\n\n"
        "Provide the complete DAG definition with dependencies."
    ),
)


# ── Prompt Selection ────────────────────────────────────────────────────

_JOB_SCHEDULER_PROMPTS: dict[str, PromptTemplate] = {
    "job_creation": JOB_CREATION_PROMPT,
    "schedule": SCHEDULE_CONFIG_PROMPT,
    "dag": DAG_BUILDER_PROMPT,
}


def get_job_scheduler_prompt(scheduler_mode: str) -> PromptTemplate:
    """Return the appropriate job scheduler prompt for the given mode.

    Falls back to ``JOB_CREATION_PROMPT`` for unrecognised modes.
    """
    return _JOB_SCHEDULER_PROMPTS.get(
        scheduler_mode.lower(), JOB_CREATION_PROMPT,
    )
