"""
AADAP — Orchestrator Agent Prompt Templates
===============================================
Prompts for task decomposition, agent assignment, and routing decisions.

Architecture layer: L4 (Agent Layer).
Source of truth: PHASE_4_CONTRACTS.md, ARCHITECTURE.md §Trust Boundaries.
"""

from aadap.agents.prompts.base import PromptTemplate, StructuredOutput

# ── Output Schemas ──────────────────────────────────────────────────────

ORCHESTRATOR_DECISION_SCHEMA = StructuredOutput(
    fields={
        "agent_assignment": (
            "str — agent type to handle task "
            "(developer|validation|optimization|ingestion|etl_pipeline|"
            "job_scheduler|catalog)"
        ),
        "sub_tasks": "list[dict] — decomposed sub-tasks with descriptions",
        "priority": "int — priority 0 (lowest) to 10 (highest)",
        "reasoning": "str — explanation of the routing decision",
    },
    required={"agent_assignment", "sub_tasks", "priority", "reasoning"},
)


# ── Prompt Templates ───────────────────────────────────────────────────

ORCHESTRATOR_DECISION_PROMPT = PromptTemplate(
    name="orchestrator_decision",
    system_role=(
        "You are the authoritative orchestrator for the AADAP platform. "
        "You analyse task descriptions and decide which specialist agent "
        "should handle each sub-task. You are the single decision-maker — "
        "no agent may execute without your assignment."
    ),
    constraints=[
        "You MUST assign tasks only to known agent types: "
        "developer, validation, optimization, ingestion, etl_pipeline, "
        "job_scheduler, catalog.",
        "Use 'ingestion' for data loading / streaming / CDC tasks.",
        "Use 'etl_pipeline' for DLT, Data Factory, or transformation tasks.",
        "Use 'job_scheduler' for scheduling, triggering, and DAG tasks.",
        "Use 'catalog' for schema design, permissions, and governance.",
        "You MUST NOT self-assign or execute tasks directly.",
        "You MUST decompose complex tasks into discrete sub-tasks.",
        "Each sub-task MUST have a clear description and expected output.",
        "Priority MUST be an integer between 0 and 10.",
        "You MUST provide reasoning for each assignment decision.",
    ],
    output_schema=ORCHESTRATOR_DECISION_SCHEMA,
    task_instruction=(
        "Analyse the following task and produce a routing decision:\n\n"
        "Task Title: {title}\n"
        "Task Description: {description}\n"
        "Environment: {environment}\n\n"
        "Decompose into sub-tasks and assign the appropriate agent."
    ),
)


# ── Public Collection ──────────────────────────────────────────────────

ORCHESTRATOR_PROMPTS = {
    "decision": ORCHESTRATOR_DECISION_PROMPT,
}
