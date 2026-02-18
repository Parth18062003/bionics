"""
AADAP — Fabric-Specific Tool Definitions
=============================================
Pre-defined tool definitions for Microsoft Fabric agents.

Architecture layer: L3 (Integration) / L4 (Agent Layer).
Phase 7 contract: Microsoft Fabric tool registration.

Tools:
- fabric_submit_notebook     — Submit a notebook for execution on Fabric Spark
- fabric_get_job_status      — Poll the status of a running Fabric job
- fabric_get_job_output      — Retrieve output/results of a completed Fabric job
- fabric_query_lakehouse     — Execute a SQL query on a Fabric Lakehouse endpoint
- fabric_list_lakehouse_tables — List tables available in the Lakehouse

Usage:
    from aadap.agents.tools.fabric_tools import register_fabric_tools

    registry = ToolRegistry()
    register_fabric_tools(registry, fabric_client)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aadap.agents.tools.registry import ToolDefinition, ToolRegistry
from aadap.core.logging import get_logger

if TYPE_CHECKING:
    import uuid

    from aadap.integrations.fabric_client import BaseFabricClient

logger = get_logger(__name__)


# ── Tool handler factories ─────────────────────────────────────────────
# Each factory returns a closure bound to the given Fabric client so
# that tool handlers are stateless from the registry's perspective.


def _make_submit_notebook_handler(client: BaseFabricClient):
    """Create a handler that submits a notebook job to Fabric."""

    async def _handler(
        *,
        task_id: str,
        code: str,
        environment: str = "SANDBOX",
        language: str = "python",
    ) -> dict[str, Any]:
        import uuid as _uuid

        tid = _uuid.UUID(task_id) if isinstance(task_id, str) else task_id
        submission = await client.submit_job(
            task_id=tid,
            code=code,
            environment=environment,
            language=language,
        )
        return {
            "job_id": submission.job_id,
            "status": submission.status.value,
            "environment": submission.environment,
        }

    return _handler


def _make_get_job_status_handler(client: BaseFabricClient):
    """Create a handler that polls Fabric job status."""

    async def _handler(*, job_id: str) -> dict[str, Any]:
        status = await client.get_job_status(job_id)
        return {"job_id": job_id, "status": status.value}

    return _handler


def _make_get_job_output_handler(client: BaseFabricClient):
    """Create a handler that retrieves output from a completed Fabric job."""

    async def _handler(*, job_id: str) -> dict[str, Any]:
        result = await client.get_job_output(job_id)
        return {
            "job_id": result.job_id,
            "status": result.status.value,
            "output": result.output,
            "error": result.error,
        }

    return _handler


def _make_query_lakehouse_handler(client: BaseFabricClient):
    """Create a handler that executes SQL on the Fabric Lakehouse endpoint."""

    async def _handler(
        *,
        task_id: str,
        sql: str,
        environment: str = "SANDBOX",
    ) -> dict[str, Any]:
        import uuid as _uuid

        tid = _uuid.UUID(task_id) if isinstance(task_id, str) else task_id
        submission = await client.submit_job(
            task_id=tid,
            code=sql,
            environment=environment,
            language="sql",
        )
        # For SQL the mock client completes immediately; real client would
        # require polling via get_job_status / get_job_output.
        return {
            "job_id": submission.job_id,
            "status": submission.status.value,
        }

    return _handler


def _make_list_tables_handler(client: BaseFabricClient):
    """Create a handler that lists tables by submitting SHOW TABLES."""

    async def _handler(
        *,
        task_id: str,
        environment: str = "SANDBOX",
    ) -> dict[str, Any]:
        import uuid as _uuid

        tid = _uuid.UUID(task_id) if isinstance(task_id, str) else task_id
        submission = await client.submit_job(
            task_id=tid,
            code="SHOW TABLES",
            environment=environment,
            language="sql",
        )
        return {
            "job_id": submission.job_id,
            "status": submission.status.value,
        }

    return _handler


# ── Fabric Tool Definitions ────────────────────────────────────────────

FABRIC_TOOL_NAMES = frozenset({
    "fabric_submit_notebook",
    "fabric_get_job_status",
    "fabric_get_job_output",
    "fabric_query_lakehouse",
    "fabric_list_lakehouse_tables",
})
"""Set of all Fabric tool names — useful for building agent permission sets."""


def build_fabric_tools(client: BaseFabricClient) -> list[ToolDefinition]:
    """
    Build the full set of Fabric tool definitions bound to *client*.

    Returns a list ready for ``ToolRegistry.register()``.
    """
    return [
        ToolDefinition(
            name="fabric_submit_notebook",
            description=(
                "Submit Python, Scala, or SQL code for execution on a "
                "Microsoft Fabric Spark notebook."
            ),
            handler=_make_submit_notebook_handler(client),
            requires_approval=True,
            is_destructive=False,
        ),
        ToolDefinition(
            name="fabric_get_job_status",
            description="Poll the current status of a Fabric job by job ID.",
            handler=_make_get_job_status_handler(client),
            requires_approval=False,
            is_destructive=False,
        ),
        ToolDefinition(
            name="fabric_get_job_output",
            description=(
                "Retrieve the output / results of a completed Fabric job."
            ),
            handler=_make_get_job_output_handler(client),
            requires_approval=False,
            is_destructive=False,
        ),
        ToolDefinition(
            name="fabric_query_lakehouse",
            description=(
                "Execute a SQL query on the Fabric Lakehouse SQL endpoint."
            ),
            handler=_make_query_lakehouse_handler(client),
            requires_approval=True,
            is_destructive=False,
        ),
        ToolDefinition(
            name="fabric_list_lakehouse_tables",
            description=(
                "List tables available in the current Fabric Lakehouse."
            ),
            handler=_make_list_tables_handler(client),
            requires_approval=False,
            is_destructive=False,
        ),
    ]


def register_fabric_tools(
    registry: ToolRegistry,
    client: BaseFabricClient,
) -> None:
    """
    Register all Fabric tools in *registry*, bound to *client*.

    Safe to call multiple times — skips tools already registered.
    """
    tools = build_fabric_tools(client)
    for tool in tools:
        try:
            registry.register(tool)
            logger.info(
                "fabric_tools.registered",
                tool_name=tool.name,
            )
        except ValueError:
            logger.debug(
                "fabric_tools.already_registered",
                tool_name=tool.name,
            )
