"""
AADAP — Databricks Platform Adapter
===================================
Adapter implementation for Databricks capability operations.

The adapter wraps ``BaseDatabricksClient`` and only delegates through
integration-client methods. Resource metadata is persisted to database
for tracking across service restarts.
"""

from __future__ import annotations

import uuid
from typing import Any, Callable

from aadap.agents.adapters.base import (
    PlatformAdapter,
    PlatformExecutionError,
)
from aadap.core.logging import get_logger
from aadap.db.models import PlatformResource
from aadap.db.session import get_db_session
from aadap.integrations.databricks_client import BaseDatabricksClient

logger = get_logger(__name__)


class DatabricksAdapter(PlatformAdapter):
    """Platform adapter for Databricks operations with database persistence."""

    def __init__(
        self,
        client: BaseDatabricksClient,
        default_environment: str = "SANDBOX",
        task_id: uuid.UUID | None = None,
        session_factory: Callable[..., Any] | None = None,
    ) -> None:
        super().__init__(platform_name="databricks")
        self._client = client
        self._default_environment = default_environment
        self._task_id = task_id
        self._session_factory = session_factory or get_db_session
        # In-memory cache for the current session (backed by database)
        self._resource_cache: dict[str, dict[str, Any]] = {}

    async def _persist_resource(
        self,
        resource_type: str,
        resource_id: str,
        definition: dict[str, Any],
        status: str = "CREATED",
    ) -> None:
        """Persist a resource to the database."""
        if not self._task_id:
            return  # No task context, skip persistence

        async with self._session_factory() as session:
            resource = PlatformResource(
                id=uuid.uuid4(),
                task_id=self._task_id,
                platform="databricks",
                resource_type=resource_type,
                platform_resource_id=resource_id,
                definition=definition,
                status=status,
            )
            session.add(resource)

    async def _load_resource(self, resource_id: str) -> dict[str, Any] | None:
        """Load a resource from the database."""
        if not self._task_id:
            return self._resource_cache.get(resource_id)

        async with self._session_factory() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(PlatformResource).where(
                    PlatformResource.platform_resource_id == resource_id,
                    PlatformResource.task_id == self._task_id,
                )
            )
            resource = result.scalar_one_or_none()
            if resource:
                return resource.definition or {}
        return None

    async def create_pipeline(self, definition: dict[str, Any]) -> str:
        """Create a Databricks pipeline metadata record."""
        pipeline_id = f"dbx-pipeline-{uuid.uuid4().hex[:12]}"
        self._resource_cache[pipeline_id] = dict(definition)
        await self._persist_resource("pipeline", pipeline_id, definition)
        logger.info(
            "databricks_adapter.pipeline_created",
            pipeline_id=pipeline_id,
            definition_keys=sorted(definition.keys()),
        )
        return pipeline_id

    async def execute_pipeline(self, pipeline_id: str) -> dict[str, Any]:
        """Execute a Databricks pipeline if known by this adapter."""
        definition = await self._load_resource(pipeline_id)
        if definition is None:
            definition = self._resource_cache.get(pipeline_id)
        if definition is None:
            raise PlatformExecutionError(
                f"Databricks pipeline '{pipeline_id}' is not registered."
            )

        logger.info(
            "databricks_adapter.pipeline_execute_requested",
            pipeline_id=pipeline_id,
        )

        return {
            "pipeline_id": pipeline_id,
            "status": "QUEUED",
            "platform": "databricks",
            "definition": definition,
        }

    async def create_job(self, definition: dict[str, Any]) -> str:
        """Create a Databricks job definition within adapter metadata."""
        job_id = f"dbx-job-{uuid.uuid4().hex[:12]}"
        self._resource_cache[job_id] = dict(definition)
        await self._persist_resource("job", job_id, definition)
        logger.info(
            "databricks_adapter.job_created",
            job_id=job_id,
            definition_keys=sorted(definition.keys()),
        )
        return job_id

    async def execute_job(
        self,
        job_id: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a Databricks job through the wrapped Databricks client."""
        merged_params = params or {}
        definition = await self._load_resource(job_id) or {}
        if not definition:
            definition = self._resource_cache.get(job_id, {})

        code = str(merged_params.get("code") or definition.get("code") or "")
        if not code.strip():
            raise PlatformExecutionError(
                f"Databricks job '{job_id}' does not contain executable code."
            )

        language = str(merged_params.get("language")
                       or definition.get("language") or "sql")
        environment = str(
            merged_params.get("environment")
            or definition.get("environment")
            or self._default_environment
        )
        task_id = self._coerce_task_id(merged_params.get("task_id"))

        try:
            submission = await self._client.submit_job(
                task_id=task_id,
                code=code,
                environment=environment,
                correlation_id=merged_params.get("correlation_id"),
                language=language,
            )
            logger.info(
                "databricks_adapter.job_submitted",
                adapter_job_id=job_id,
                execution_job_id=submission.job_id,
                environment=environment,
                language=language,
            )
            return {
                "job_id": submission.job_id,
                "adapter_job_id": job_id,
                "status": submission.status.value,
                "environment": submission.environment,
                "platform": "databricks",
            }
        except Exception as exc:
            logger.error(
                "databricks_adapter.job_execution_failed",
                adapter_job_id=job_id,
                error=str(exc),
            )
            raise PlatformExecutionError(
                f"Databricks job execution failed: {exc}"
            ) from exc

    async def get_job_status(self, job_id: str) -> dict[str, Any]:
        """Fetch Databricks job status via wrapped client."""
        try:
            status = await self._client.get_job_status(job_id)
            return {
                "job_id": job_id,
                "status": status.value,
                "platform": "databricks",
            }
        except Exception as exc:
            logger.error(
                "databricks_adapter.job_status_failed",
                job_id=job_id,
                error=str(exc),
            )
            raise PlatformExecutionError(
                f"Databricks get job status failed: {exc}"
            ) from exc

    async def create_table(self, schema: dict[str, Any]) -> str:
        """Create table metadata record for Databricks table operations."""
        table_id = str(
            schema.get("table_id") or schema.get(
                "name") or f"dbx-table-{uuid.uuid4().hex[:12]}"
        )
        self._resource_cache[table_id] = dict(schema)
        await self._persist_resource("table", table_id, schema)
        logger.info(
            "databricks_adapter.table_created",
            table_id=table_id,
            schema_keys=sorted(schema.keys()),
        )
        return table_id

    async def list_tables(self) -> list[dict[str, Any]]:
        """List Databricks table metadata known by adapter."""
        if not self._task_id:
            return [
                {"table_id": table_id, "definition": definition}
                for table_id, definition in self._resource_cache.items()
                if definition.get("_type") == "table"
            ]

        async with self._session_factory() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(PlatformResource).where(
                    PlatformResource.task_id == self._task_id,
                    PlatformResource.resource_type == "table",
                )
            )
            resources = result.scalars().all()
            return [
                {"table_id": r.platform_resource_id, "definition": r.definition or {}}
                for r in resources
            ]

    async def create_shortcut(self, config: dict[str, Any]) -> str:
        """Create shortcut metadata record for Databricks external links."""
        shortcut_id = str(config.get("shortcut_id")
                          or f"dbx-shortcut-{uuid.uuid4().hex[:12]}")
        self._resource_cache[shortcut_id] = dict(config)
        await self._persist_resource("shortcut", shortcut_id, config)
        logger.info(
            "databricks_adapter.shortcut_created",
            shortcut_id=shortcut_id,
            config_keys=sorted(config.keys()),
        )
        return shortcut_id

    async def execute_sql(self, sql: str) -> dict[str, Any]:
        """Execute SQL through Databricks statement execution path."""
        if not sql.strip():
            raise PlatformExecutionError(
                "Databricks SQL execution requires non-empty SQL.")

        task_id = uuid.uuid4()
        try:
            submission = await self._client.submit_job(
                task_id=task_id,
                code=sql,
                environment=self._default_environment,
                language="sql",
            )
            output = await self._client.get_job_output(submission.job_id)
            return {
                "job_id": output.job_id,
                "status": output.status.value,
                "output": output.output,
                "error": output.error,
                "duration_ms": output.duration_ms,
                "metadata": output.metadata,
                "platform": "databricks",
            }
        except Exception as exc:
            logger.error(
                "databricks_adapter.sql_execution_failed",
                error=str(exc),
            )
            raise PlatformExecutionError(
                f"Databricks SQL execution failed: {exc}"
            ) from exc

    @staticmethod
    def _coerce_task_id(raw_task_id: Any) -> uuid.UUID:
        """Convert incoming task ID value to UUID."""
        if isinstance(raw_task_id, uuid.UUID):
            return raw_task_id

        if isinstance(raw_task_id, str) and raw_task_id.strip():
            try:
                return uuid.UUID(raw_task_id)
            except ValueError:
                logger.debug(
                    "adapter.invalid_task_id_format",
                    raw_task_id=str(raw_task_id)[:36],
                    fallback="generating_uuid",
                )

        return uuid.uuid4()
