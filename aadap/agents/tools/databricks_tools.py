"""
AADAP — Databricks-Specific Tool Definitions
============================================
Pre-defined tool definitions for Databricks agents.

Architecture layer: L3 (Integration) / L4 (Agent Layer).
Phase 2 contract: Databricks orchestration tool registration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aadap.agents.adapters import DatabricksAdapter
from aadap.agents.adapters.base import PlatformCapabilityError
from aadap.agents.tools.registry import ToolDefinition, ToolRegistry
from aadap.core.logging import get_logger

if TYPE_CHECKING:
    from aadap.integrations.databricks_client import BaseDatabricksClient

logger = get_logger(__name__)


def _make_create_job_handler(adapter: DatabricksAdapter):
    """Create a Databricks job definition."""

    async def _handler(*, definition: dict[str, Any]) -> dict[str, Any]:
        job_id = await adapter.create_job(definition)
        return {"job_id": job_id, "platform": "databricks"}

    return _handler


def _make_run_job_handler(adapter: DatabricksAdapter):
    """Execute a Databricks job definition."""

    async def _handler(
        *,
        job_id: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await adapter.execute_job(job_id=job_id, params=params or {})

    return _handler


def _make_get_job_status_handler(adapter: DatabricksAdapter):
    """Fetch Databricks job status."""

    async def _handler(*, job_id: str) -> dict[str, Any]:
        return await adapter.get_job_status(job_id)

    return _handler


def _make_cancel_job_handler():
    """Raise capability error because cancellation is not yet client-supported."""

    async def _handler(*, job_id: str) -> dict[str, Any]:
        raise PlatformCapabilityError(
            "Databricks job cancellation is not yet supported by BaseDatabricksClient. "
            f"job_id='{job_id}'"
        )

    return _handler


def _make_create_pipeline_handler(adapter: DatabricksAdapter):
    """Create a Databricks pipeline definition."""

    async def _handler(*, definition: dict[str, Any]) -> dict[str, Any]:
        pipeline_id = await adapter.create_pipeline(definition)
        return {"pipeline_id": pipeline_id, "platform": "databricks"}

    return _handler


def _make_start_pipeline_handler(adapter: DatabricksAdapter):
    """Execute a Databricks pipeline definition."""

    async def _handler(*, pipeline_id: str) -> dict[str, Any]:
        return await adapter.execute_pipeline(pipeline_id)

    return _handler


def _make_create_catalog_handler(adapter: DatabricksAdapter):
    """Create Databricks catalog metadata via adapter table abstraction."""

    async def _handler(*, catalog: dict[str, Any]) -> dict[str, Any]:
        payload = {"resource_type": "catalog", **catalog}
        catalog_id = await adapter.create_table(payload)
        return {
            "catalog_id": catalog_id,
            "resource_type": "catalog",
            "platform": "databricks",
        }

    return _handler


def _make_create_schema_handler(adapter: DatabricksAdapter):
    """Create Databricks schema metadata via adapter table abstraction."""

    async def _handler(*, schema: dict[str, Any]) -> dict[str, Any]:
        payload = {"resource_type": "schema", **schema}
        schema_id = await adapter.create_table(payload)
        return {
            "schema_id": schema_id,
            "resource_type": "schema",
            "platform": "databricks",
        }

    return _handler


def _make_grant_permissions_handler(adapter: DatabricksAdapter):
    """Execute Databricks GRANT statements via SQL execution."""

    async def _handler(*, sql: str) -> dict[str, Any]:
        return await adapter.execute_sql(sql)

    return _handler


def _make_execute_sql_handler(adapter: DatabricksAdapter):
    """Execute Databricks SQL through the adapter."""

    async def _handler(*, sql: str) -> dict[str, Any]:
        return await adapter.execute_sql(sql)

    return _handler


DATABRICKS_TOOL_NAMES = frozenset({
    "databricks_create_job",
    "databricks_run_job",
    "databricks_get_job_status",
    "databricks_cancel_job",
    "databricks_create_pipeline",
    "databricks_start_pipeline",
    "databricks_create_catalog",
    "databricks_create_schema",
    "databricks_grant_permissions",
    "databricks_execute_sql",
})
"""Set of all Databricks tool names."""


def build_databricks_tools(client: BaseDatabricksClient) -> list[ToolDefinition]:
    """Build the full set of Databricks tool definitions bound to *client*."""
    adapter = DatabricksAdapter(client=client)

    return [
        ToolDefinition(
            name="databricks_create_job",
            description="Create a Databricks multi-task job definition.",
            handler=_make_create_job_handler(adapter),
            requires_approval=True,
            is_destructive=False,
        ),
        ToolDefinition(
            name="databricks_run_job",
            description="Execute a Databricks job by ID.",
            handler=_make_run_job_handler(adapter),
            requires_approval=True,
            is_destructive=False,
        ),
        ToolDefinition(
            name="databricks_get_job_status",
            description="Poll status for a Databricks job execution.",
            handler=_make_get_job_status_handler(adapter),
            requires_approval=False,
            is_destructive=False,
        ),
        ToolDefinition(
            name="databricks_cancel_job",
            description="Cancel a running Databricks job (capability-gated).",
            handler=_make_cancel_job_handler(),
            requires_approval=True,
            is_destructive=True,
        ),
        ToolDefinition(
            name="databricks_create_pipeline",
            description="Create a Databricks DLT pipeline definition.",
            handler=_make_create_pipeline_handler(adapter),
            requires_approval=True,
            is_destructive=False,
        ),
        ToolDefinition(
            name="databricks_start_pipeline",
            description="Start a Databricks DLT pipeline execution.",
            handler=_make_start_pipeline_handler(adapter),
            requires_approval=True,
            is_destructive=False,
        ),
        ToolDefinition(
            name="databricks_create_catalog",
            description="Create Databricks Unity Catalog metadata.",
            handler=_make_create_catalog_handler(adapter),
            requires_approval=True,
            is_destructive=False,
        ),
        ToolDefinition(
            name="databricks_create_schema",
            description="Create Databricks schema metadata.",
            handler=_make_create_schema_handler(adapter),
            requires_approval=True,
            is_destructive=False,
        ),
        ToolDefinition(
            name="databricks_grant_permissions",
            description="Apply Databricks GRANT statements via SQL execution.",
            handler=_make_grant_permissions_handler(adapter),
            requires_approval=True,
            is_destructive=True,
        ),
        ToolDefinition(
            name="databricks_execute_sql",
            description="Run SQL on Databricks SQL execution path.",
            handler=_make_execute_sql_handler(adapter),
            requires_approval=True,
            is_destructive=False,
        ),
    ]


def register_databricks_tools(
    registry: ToolRegistry,
    client: BaseDatabricksClient,
) -> None:
    """Register all Databricks tools in *registry*, bound to *client*."""
    tools = build_databricks_tools(client)
    for tool in tools:
        try:
            registry.register(tool)
            logger.info(
                "databricks_tools.registered",
                tool_name=tool.name,
            )
        except ValueError:
            logger.debug(
                "databricks_tools.already_registered",
                tool_name=tool.name,
            )
