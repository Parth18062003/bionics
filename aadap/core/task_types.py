"""
AADAP — Task Types and Operation Modes
==========================================
Enumerations for task modes, operation types, and task categories.

Task Modes:
- GENERATE_CODE: Generate code without execution
- EXECUTE_CODE: Generate and execute code
- READ: Read operations (preview table, get schema)
- LIST: List operations (list tables, schemas, files)
- MANAGE: Management operations (grant, create, drop)

Operation Types:
- Code generation: code_generate
- Execution: execute_query, execute_notebook
- Read: preview_table, get_schema, get_table_stats
- List: list_tables, list_schemas, list_catalogs, list_files, list_notebooks
- Manage: grant_permission, create_table, create_schema
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class TaskMode(StrEnum):
    """High-level task execution mode."""

    GENERATE_CODE = "generate_code"      # Generate code only, no execution
    EXECUTE_CODE = "execute_code"        # Generate and execute code
    READ = "read"                        # Read operations (no code gen)
    LIST = "list"                        # List operations (no code gen)
    MANAGE = "manage"                    # Management operations (DDL, grants)


class OperationType(StrEnum):
    """Specific operation types within each mode."""

    # Code operations
    CODE_GENERATE = "code_generate"
    CODE_EXECUTE = "code_execute"
    EXECUTE_QUERY = "execute_query"
    EXECUTE_NOTEBOOK = "execute_notebook"

    # Read operations
    PREVIEW_TABLE = "preview_table"
    GET_SCHEMA = "get_schema"
    GET_TABLE_STATS = "get_table_stats"
    GET_TABLE_DDL = "get_table_ddl"
    READ_FILE = "read_file"

    # List operations
    LIST_CATALOGS = "list_catalogs"
    LIST_SCHEMAS = "list_schemas"
    LIST_TABLES = "list_tables"
    LIST_FILES = "list_files"
    LIST_NOTEBOOKS = "list_notebooks"
    LIST_PIPELINES = "list_pipelines"
    LIST_JOBS = "list_jobs"
    LIST_LAKEHOUSES = "list_lakehouses"
    LIST_WORKSPACES = "list_workspaces"
    LIST_SHORTCUTS = "list_shortcuts"

    # Manage operations
    CREATE_TABLE = "create_table"
    CREATE_SCHEMA = "create_schema"
    CREATE_NOTEBOOK = "create_notebook"
    CREATE_PIPELINE = "create_pipeline"
    CREATE_JOB = "create_job"
    CREATE_SHORTCUT = "create_shortcut"
    GRANT_PERMISSION = "grant_permission"
    REVOKE_PERMISSION = "revoke_permission"
    DROP_TABLE = "drop_table"
    DROP_SCHEMA = "drop_schema"


# Operation to mode mapping
OPERATION_MODE_MAP: dict[OperationType, TaskMode] = {
    # Code
    OperationType.CODE_GENERATE: TaskMode.GENERATE_CODE,
    OperationType.CODE_EXECUTE: TaskMode.EXECUTE_CODE,
    OperationType.EXECUTE_QUERY: TaskMode.EXECUTE_CODE,
    OperationType.EXECUTE_NOTEBOOK: TaskMode.EXECUTE_CODE,

    # Read
    OperationType.PREVIEW_TABLE: TaskMode.READ,
    OperationType.GET_SCHEMA: TaskMode.READ,
    OperationType.GET_TABLE_STATS: TaskMode.READ,
    OperationType.GET_TABLE_DDL: TaskMode.READ,
    OperationType.READ_FILE: TaskMode.READ,

    # List
    OperationType.LIST_CATALOGS: TaskMode.LIST,
    OperationType.LIST_SCHEMAS: TaskMode.LIST,
    OperationType.LIST_TABLES: TaskMode.LIST,
    OperationType.LIST_FILES: TaskMode.LIST,
    OperationType.LIST_NOTEBOOKS: TaskMode.LIST,
    OperationType.LIST_PIPELINES: TaskMode.LIST,
    OperationType.LIST_JOBS: TaskMode.LIST,
    OperationType.LIST_LAKEHOUSES: TaskMode.LIST,
    OperationType.LIST_WORKSPACES: TaskMode.LIST,
    OperationType.LIST_SHORTCUTS: TaskMode.LIST,

    # Manage
    OperationType.CREATE_TABLE: TaskMode.MANAGE,
    OperationType.CREATE_SCHEMA: TaskMode.MANAGE,
    OperationType.CREATE_NOTEBOOK: TaskMode.MANAGE,
    OperationType.CREATE_PIPELINE: TaskMode.MANAGE,
    OperationType.CREATE_JOB: TaskMode.MANAGE,
    OperationType.CREATE_SHORTCUT: TaskMode.MANAGE,
    OperationType.GRANT_PERMISSION: TaskMode.MANAGE,
    OperationType.REVOKE_PERMISSION: TaskMode.MANAGE,
    OperationType.DROP_TABLE: TaskMode.MANAGE,
    OperationType.DROP_SCHEMA: TaskMode.MANAGE,
}


# Operations that require approval
OPERATIONS_REQUIRING_APPROVAL: set[OperationType] = {
    OperationType.CREATE_TABLE,
    OperationType.CREATE_SCHEMA,
    OperationType.CREATE_NOTEBOOK,
    OperationType.CREATE_PIPELINE,
    OperationType.CREATE_JOB,
    OperationType.CREATE_SHORTCUT,
    OperationType.GRANT_PERMISSION,
    OperationType.REVOKE_PERMISSION,
    OperationType.DROP_TABLE,
    OperationType.DROP_SCHEMA,
    OperationType.CODE_EXECUTE,
    OperationType.EXECUTE_QUERY,
    OperationType.EXECUTE_NOTEBOOK,
}


# Operations that bypass code generation
DIRECT_EXECUTION_OPERATIONS: set[OperationType] = {
    OperationType.PREVIEW_TABLE,
    OperationType.GET_SCHEMA,
    OperationType.GET_TABLE_STATS,
    OperationType.GET_TABLE_DDL,
    OperationType.READ_FILE,
    OperationType.LIST_CATALOGS,
    OperationType.LIST_SCHEMAS,
    OperationType.LIST_TABLES,
    OperationType.LIST_FILES,
    OperationType.LIST_NOTEBOOKS,
    OperationType.LIST_PIPELINES,
    OperationType.LIST_JOBS,
    OperationType.LIST_LAKEHOUSES,
    OperationType.LIST_WORKSPACES,
    OperationType.LIST_SHORTCUTS,
}


def get_task_mode(operation: OperationType | str) -> TaskMode:
    """Get the task mode for an operation type."""
    if isinstance(operation, str):
        try:
            operation = OperationType(operation)
        except ValueError:
            return TaskMode.GENERATE_CODE
    return OPERATION_MODE_MAP.get(operation, TaskMode.GENERATE_CODE)


def requires_code_generation(operation: OperationType | str) -> bool:
    """Check if an operation requires code generation."""
    if isinstance(operation, str):
        try:
            operation = OperationType(operation)
        except ValueError:
            return True
    return operation not in DIRECT_EXECUTION_OPERATIONS


def is_direct_execution(task_mode: TaskMode | str | None, operation_type: OperationType | str | None) -> bool:
    """Check if the task should execute directly without code generation."""
    if isinstance(task_mode, str):
        try:
            task_mode = TaskMode(task_mode)
        except ValueError:
            task_mode = None
    
    if isinstance(operation_type, str):
        try:
            operation_type = OperationType(operation_type)
        except ValueError:
            operation_type = None
    
    if task_mode in (TaskMode.READ, TaskMode.LIST):
        return True
    
    if operation_type and operation_type in DIRECT_EXECUTION_OPERATIONS:
        return True
    
    return False


def requires_approval(operation: OperationType | str, environment: str) -> bool:
    """Check if an operation requires human approval."""
    if isinstance(operation, str):
        try:
            operation = OperationType(operation)
        except ValueError:
            return False

    if operation in OPERATIONS_REQUIRING_APPROVAL:
        return environment.upper() == "PRODUCTION"
    return False


# Quick action definitions for frontend
QUICK_ACTIONS: list[dict[str, Any]] = [
    {
        "id": "list_tables",
        "label": "List Tables",
        "description": "List all tables in a schema",
        "icon": "📋",
        "operation_type": OperationType.LIST_TABLES.value,
        "task_mode": TaskMode.LIST.value,
        "requires_selection": "schema",
        "platforms": ["databricks", "fabric"],
    },
    {
        "id": "list_schemas",
        "label": "List Schemas",
        "description": "List all schemas in a catalog",
        "icon": "📁",
        "operation_type": OperationType.LIST_SCHEMAS.value,
        "task_mode": TaskMode.LIST.value,
        "requires_selection": "catalog",
        "platforms": ["databricks", "fabric"],
    },
    {
        "id": "list_catalogs",
        "label": "List Catalogs",
        "description": "List all catalogs/workspaces",
        "icon": "🗄️",
        "operation_type": OperationType.LIST_CATALOGS.value,
        "task_mode": TaskMode.LIST.value,
        "requires_selection": "none",
        "platforms": ["databricks", "fabric"],
    },
    {
        "id": "preview_table",
        "label": "Preview Table",
        "description": "Preview first 100 rows of a table",
        "icon": "👁️",
        "operation_type": OperationType.PREVIEW_TABLE.value,
        "task_mode": TaskMode.READ.value,
        "requires_selection": "table",
        "platforms": ["databricks", "fabric"],
    },
    {
        "id": "get_schema",
        "label": "Get Table Schema",
        "description": "Get column definitions for a table",
        "icon": "📝",
        "operation_type": OperationType.GET_SCHEMA.value,
        "task_mode": TaskMode.READ.value,
        "requires_selection": "table",
        "platforms": ["databricks", "fabric"],
    },
    {
        "id": "list_files",
        "label": "List Files",
        "description": "List files in lakehouse/workspace",
        "icon": "📄",
        "operation_type": OperationType.LIST_FILES.value,
        "task_mode": TaskMode.LIST.value,
        "requires_selection": "path",
        "platforms": ["fabric"],
    },
    {
        "id": "list_lakehouses",
        "label": "List Lakehouses",
        "description": "List all lakehouses in workspace",
        "icon": "🏠",
        "operation_type": OperationType.LIST_LAKEHOUSES.value,
        "task_mode": TaskMode.LIST.value,
        "requires_selection": "none",
        "platforms": ["fabric"],
    },
    {
        "id": "list_notebooks",
        "label": "List Notebooks",
        "description": "List all notebooks in workspace",
        "icon": "📓",
        "operation_type": OperationType.LIST_NOTEBOOKS.value,
        "task_mode": TaskMode.LIST.value,
        "requires_selection": "none",
        "platforms": ["databricks", "fabric"],
    },
    {
        "id": "list_jobs",
        "label": "List Jobs",
        "description": "List all jobs/pipelines",
        "icon": "⚡",
        "operation_type": OperationType.LIST_JOBS.value,
        "task_mode": TaskMode.LIST.value,
        "requires_selection": "none",
        "platforms": ["databricks", "fabric"],
    },
    {
        "id": "run_query",
        "label": "Run SQL Query",
        "description": "Execute a SQL query directly",
        "icon": "🔍",
        "operation_type": OperationType.EXECUTE_QUERY.value,
        "task_mode": TaskMode.EXECUTE_CODE.value,
        "requires_selection": "none",
        "platforms": ["databricks", "fabric"],
    },
]
