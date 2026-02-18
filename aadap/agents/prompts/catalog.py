"""
AADAP — Catalog Agent Prompt Templates
==========================================
Structured-output prompt definitions for the Catalog agent.

Supports two catalog governance concerns:
- **Schema design**: Catalog/schema/table/lakehouse DDL planning
- **Permission grant**: Principals, privileges, and grant strategy

Each prompt targets Azure Databricks or Microsoft Fabric and returns a
JSON artifact with DDL statements, API payloads, and permission details.
"""

from __future__ import annotations

from aadap.agents.prompts.base import PromptTemplate, StructuredOutput


# ── Catalog Output Schema ──────────────────────────────────────────────

CATALOG_SCHEMA = StructuredOutput(
    fields={
        "platform": "str — target platform: databricks | fabric",
        "operation": "str — create | alter | grant | drop",
        "resource_type": "str — catalog | schema | table | volume | lakehouse",
        "ddl_statements": "list[str] — SQL DDL/DCL statements in execution order",
        "api_payloads": "list[dict] — optional platform API payload definitions",
        "permissions": "list[dict] — principals, privileges, and scope",
        "code": "str — generated SQL or API-oriented payload code",
        "language": "str — sql | json",
        "explanation": "str — brief explanation of design decisions",
    },
    required={
        "platform",
        "operation",
        "resource_type",
        "ddl_statements",
        "api_payloads",
        "permissions",
        "code",
        "language",
        "explanation",
    },
)


# ── Shared constraints ─────────────────────────────────────────────────

_BASE_CONSTRAINTS: list[str] = [
    "Output ONLY a single valid JSON object — no surrounding text.",
    "Use least-privilege permission design and explicit principal scoping.",
    "Generate idempotent DDL where possible (IF NOT EXISTS / guarded operations).",
    "Document all assumptions in the 'explanation' field.",
]


# ── Schema Design Prompt ───────────────────────────────────────────────

SCHEMA_DESIGN_PROMPT = PromptTemplate(
    name="schema_design",
    system_role=(
        "You are an expert data governance engineer specialising in Azure "
        "Databricks Unity Catalog and Microsoft Fabric Lakehouse metadata "
        "design. Generate production-ready schema designs and resource "
        "provisioning statements with clear naming conventions."
    ),
    constraints=[
        *_BASE_CONSTRAINTS,
        "For Databricks, use Unity Catalog-aware SQL (CREATE CATALOG/SCHEMA/TABLE/VOLUME).",
        "For Fabric, model Lakehouse/Warehouse resources using supported DDL or API payloads.",
        "Include storage/location strategy in api_payloads when relevant.",
        "Order statements for safe dependency creation (catalog → schema → table).",
        "Avoid destructive operations unless explicitly requested.",
    ],
    output_schema=CATALOG_SCHEMA,
    task_instruction=(
        "Design catalog and schema resources for the following:\n\n"
        "Task: {task_description}\n"
        "Platform: {platform}\n"
        "Operation: {operation}\n"
        "Resource Type: {resource_type}\n"
        "Naming Conventions: {naming_conventions}\n"
        "Environment: {environment}\n"
        "Additional Context: {context}\n\n"
        "Provide ordered DDL statements and any required API payloads."
    ),
)


# ── Permission Grant Prompt ────────────────────────────────────────────

PERMISSION_GRANT_PROMPT = PromptTemplate(
    name="permission_grant",
    system_role=(
        "You are an expert in enterprise data access governance for Azure "
        "Databricks Unity Catalog and Microsoft Fabric. Generate precise "
        "GRANT/REVOKE statements and permission payloads that follow "
        "least-privilege and separation-of-duties principles."
    ),
    constraints=[
        *_BASE_CONSTRAINTS,
        "Use explicit principals (user, group, service principal).",
        "Map privileges to required access only (SELECT, MODIFY, USE SCHEMA, etc.).",
        "Prefer GRANT statements; include REVOKE only if task explicitly asks.",
        "Include approval-sensitive operations in explanation with rationale.",
        "Keep permission scope as narrow as possible.",
    ],
    output_schema=CATALOG_SCHEMA,
    task_instruction=(
        "Generate permissions configuration for the following:\n\n"
        "Task: {task_description}\n"
        "Platform: {platform}\n"
        "Operation: {operation}\n"
        "Resource Type: {resource_type}\n"
        "Principals: {principals}\n"
        "Required Access: {required_access}\n"
        "Environment: {environment}\n"
        "Additional Context: {context}\n\n"
        "Provide GRANT statements and permission payloads."
    ),
)


# ── Prompt Selection ───────────────────────────────────────────────────

_CATALOG_PROMPTS: dict[str, PromptTemplate] = {
    "schema_design": SCHEMA_DESIGN_PROMPT,
    "permission_grant": PERMISSION_GRANT_PROMPT,
}


def get_catalog_prompt(catalog_mode: str) -> PromptTemplate:
    """Return the catalog prompt for the given mode.

    Falls back to ``SCHEMA_DESIGN_PROMPT`` for unrecognized modes.
    """
    return _CATALOG_PROMPTS.get(catalog_mode.lower(), SCHEMA_DESIGN_PROMPT)
