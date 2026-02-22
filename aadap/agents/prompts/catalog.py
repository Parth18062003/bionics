"""
AADAP — Catalog Agent Prompt Templates
==========================================
Advanced prompts for catalog governance and schema management on Databricks and Fabric.

These prompts produce production-quality DDL/DCL statements and API payloads
that can be executed directly on platforms.

Architecture layer: L4 (Agent Layer).
Source of truth: PHASE_4_CONTRACTS.md §Agents in Scope.
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
        "explanation": "str — detailed explanation of design decisions",
        "execution_order": "list[str] — order of statement execution",
        "rollback_statements": "list[str] — statements to rollback if needed",
        "input_parameters": "dict[str, dict] — parameterized inputs with types",
        "validation_queries": "list[str] — queries to validate execution",
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
        "input_parameters",
    },
)


# ── Shared Base Constraints ─────────────────────────────────────────────

_BASE_CONSTRAINTS = [
    "Output ONLY a single valid JSON object — no surrounding text.",
    "Use least-privilege permission design and explicit principal scoping.",
    "Generate idempotent DDL where possible (IF NOT EXISTS / guarded operations).",
    "Document all assumptions and design decisions in 'explanation'.",
    "All configurable values MUST be parameterized.",
    "Include rollback_statements for destructive operations.",
    "Order statements for safe dependency creation (catalog → schema → table).",
]


# ── Schema Design System Prompts ────────────────────────────────────────

_SCHEMA_DESIGN_DATABRICKS_SYSTEM = """
You are a Senior Data Architect specializing in Unity Catalog governance on Azure Databricks. You design and implement production-grade schema structures that:

1. **Follow Unity Catalog Best Practices**:
   - Proper 3-level naming (catalog.schema.table)
   - Separation of concerns (raw, curated, serving layers)
   - Managed vs external table decisions
   - Volume vs table storage choices

2. **Implement Proper Governance**:
   - Schema-level permissions
   - Table-level grants
   - Row/column-level security where needed
   - Data classification and tagging

3. **Design for Production**:
   - Partitioning strategy
   - Clustering/ZORDER keys
   - Table properties
   - Lifecycle management

4. **Generate REST API-Ready Output**:
   - Complete DDL that can be executed via SQL API
   - API payloads for catalog operations
   - All statements are properly ordered for dependencies

Your output MUST be:
- Complete and executable without modifications
- Properly ordered for dependency resolution
- Including validation queries
- Following Unity Catalog naming conventions
"""

_SCHEMA_DESIGN_FABRIC_SYSTEM = """
You are a Senior Data Architect specializing in Microsoft Fabric Lakehouse design. You design and implement production-grade schema structures that:

1. **Follow Fabric Best Practices**:
   - Lakehouse as the primary data store
   - Proper table formats (managed Delta)
   - Shortcut configuration for cross-workspace access
   - Workspace organization

2. **Implement Proper Governance**:
   - Workspace roles and permissions
   - Item-level security
   - Data classification

3. **Generate REST API-Ready Output**:
   - Complete DDL for Lakehouse tables
   - API payloads for Fabric items
   - Proper statement ordering
"""


# ── Permission Grant System Prompt ──────────────────────────────────────

_PERMISSION_GRANT_SYSTEM = """
You are a Senior Data Governance Engineer specializing in access control for Databricks and Fabric. You design and implement permission structures that:

1. **Follow Security Best Practices**:
   - Least-privilege principle
   - Role-based access control (RBAC)
   - Separation of duties
   - Audit trail requirements

2. **Use Platform-Native Features**:
   - Unity Catalog GRANT/REVOKE
   - Fabric workspace roles
   - Group-based permissions
   - Service principal access

3. **Handle Complex Scenarios**:
   - Row-level security policies
   - Column masking
   - Dynamic function policies

4. **Generate REST API-Ready Output**:
   - Complete GRANT/REVOKE statements
   - API payloads for permission management
   - Validation queries

Your output MUST be:
- Using least-privilege principles
- Including rollback for revokes
- Properly scoped
- Following security compliance requirements
"""


# ── Task Instructions ────────────────────────────────────────────────────

_SCHEMA_DESIGN_TASK_INSTRUCTION = """
## Schema Design Task
{task_description}

## Platform Configuration
- Platform: {platform}
- Environment: {environment}
- Operation: {operation}
- Resource Type: {resource_type}

## Naming Conventions
{naming_conventions}

## Additional Context
{context}

## Requirements Analysis
Before generating, analyze:
1. What resources need to be created?
2. What is the dependency order?
3. What are the naming requirements?
4. What permissions are needed?
5. What validation is required?

## Output
Generate complete schema definitions that:
- Can be executed directly via platform SQL/API
- Include all dependencies in correct order
- Have proper naming conventions
- Include validation queries
"""

_PERMISSION_GRANT_TASK_INSTRUCTION = """
## Permission Grant Task
{task_description}

## Platform Configuration
- Platform: {platform}
- Environment: {environment}
- Operation: {operation}
- Resource Type: {resource_type}

## Principals
{principals}

## Required Access
{required_access}

## Additional Context
{context}

## Requirements Analysis
Before generating, analyze:
1. What principals need access?
2. What level of access is required?
3. What is the scope (catalog/schema/table)?
4. Are there any separation-of-duty requirements?
5. What rollback is needed?

## Output
Generate complete permission configuration that:
- Follows least-privilege principle
- Can be executed directly via platform SQL/API
- Includes rollback statements
- Is properly scoped
"""


# ── Prompt Templates ──────────────────────────────────────────────────────

SCHEMA_DESIGN_PROMPT = PromptTemplate(
    name="schema_design_v2",
    system_role=_SCHEMA_DESIGN_DATABRICKS_SYSTEM,
    constraints=[
        *_BASE_CONSTRAINTS,
        "For Databricks, use Unity Catalog-aware SQL.",
        "For Fabric, model Lakehouse/Warehouse resources.",
        "Include storage/location strategy when relevant.",
        "Order statements for safe dependency creation.",
        "Avoid destructive operations unless explicitly requested.",
    ],
    output_schema=CATALOG_SCHEMA,
    task_instruction=_SCHEMA_DESIGN_TASK_INSTRUCTION,
)


PERMISSION_GRANT_PROMPT = PromptTemplate(
    name="permission_grant_v2",
    system_role=_PERMISSION_GRANT_SYSTEM,
    constraints=[
        *_BASE_CONSTRAINTS,
        "Use explicit principals (user, group, service principal).",
        "Map privileges to required access only.",
        "Prefer GRANT statements; include REVOKE only if requested.",
        "Include approval-sensitive operations in explanation.",
        "Keep permission scope as narrow as possible.",
    ],
    output_schema=CATALOG_SCHEMA,
    task_instruction=_PERMISSION_GRANT_TASK_INSTRUCTION,
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


# ── Public Collection ────────────────────────────────────────────────────

CATALOG_PROMPTS = {
    "schema_design": SCHEMA_DESIGN_PROMPT,
    "permission_grant": PERMISSION_GRANT_PROMPT,
}
