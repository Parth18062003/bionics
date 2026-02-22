"""
AADAP — Fabric Platform Adapter
================================
Adapter implementation for Microsoft Fabric capability operations.

The adapter wraps ``BaseFabricClient`` and delegates execution operations
through integration-client interfaces. Resource metadata is persisted to
database for tracking across service restarts.
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
from aadap.integrations.fabric_client import BaseFabricClient

logger = get_logger(__name__)


class FabricAdapter(PlatformAdapter):
    """Platform adapter for Microsoft Fabric operations with database persistence."""

    def __init__(
        self,
        client: BaseFabricClient,
        default_environment: str = "SANDBOX",
        task_id: uuid.UUID | None = None,
        session_factory: Callable[..., Any] | None = None,
    ) -> None:
        super().__init__(platform_name="fabric")
        self._client = client
        self._default_environment = default_environment
        self._task_id = task_id
        self._session_factory = session_factory or get_db_session
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
            return

        async with self._session_factory() as session:
            resource = PlatformResource(
                id=uuid.uuid4(),
                task_id=self._task_id,
                platform="fabric",
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
        """Create a Fabric pipeline metadata record."""
        pipeline_id = f"fabric-pipeline-{uuid.uuid4().hex[:12]}"
        self._resource_cache[pipeline_id] = dict(definition)
        await self._persist_resource("pipeline", pipeline_id, definition)
        logger.info(
            "fabric_adapter.pipeline_created",
            pipeline_id=pipeline_id,
            definition_keys=sorted(definition.keys()),
        )
        return pipeline_id

    async def execute_pipeline(self, pipeline_id: str) -> dict[str, Any]:
        """Execute a Fabric pipeline if known by this adapter."""
        definition = await self._load_resource(pipeline_id)
        if definition is None:
            definition = self._resource_cache.get(pipeline_id)
        if definition is None:
            raise PlatformExecutionError(
                f"Fabric pipeline '{pipeline_id}' is not registered."
            )

        logger.info(
            "fabric_adapter.pipeline_execute_requested",
            pipeline_id=pipeline_id,
        )

        return {
            "pipeline_id": pipeline_id,
            "status": "QUEUED",
            "platform": "fabric",
            "definition": definition,
        }

    async def create_job(self, definition: dict[str, Any]) -> str:
        """Create a Fabric job definition within adapter metadata."""
        job_id = f"fabric-job-{uuid.uuid4().hex[:12]}"
        self._resource_cache[job_id] = dict(definition)
        await self._persist_resource("job", job_id, definition)
        logger.info(
            "fabric_adapter.job_created",
            job_id=job_id,
            definition_keys=sorted(definition.keys()),
        )
        return job_id

    async def execute_job(
        self,
        job_id: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a Fabric job through the wrapped Fabric client."""
        merged_params = params or {}
        definition = await self._load_resource(job_id) or {}
        if not definition:
            definition = self._resource_cache.get(job_id, {})

        code = str(merged_params.get("code") or definition.get("code") or "")
        if not code.strip():
            raise PlatformExecutionError(
                f"Fabric job '{job_id}' does not contain executable code."
            )

        language = str(
            merged_params.get("language")
            or definition.get("language")
            or "python"
        )
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
                "fabric_adapter.job_submitted",
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
                "platform": "fabric",
            }
        except Exception as exc:
            logger.error(
                "fabric_adapter.job_execution_failed",
                adapter_job_id=job_id,
                error=str(exc),
            )
            raise PlatformExecutionError(
                f"Fabric job execution failed: {exc}"
            ) from exc

    async def get_job_status(self, job_id: str) -> dict[str, Any]:
        """Fetch Fabric job status via wrapped client."""
        try:
            status = await self._client.get_job_status(job_id)
            return {
                "job_id": job_id,
                "status": status.value,
                "platform": "fabric",
            }
        except Exception as exc:
            logger.error(
                "fabric_adapter.job_status_failed",
                job_id=job_id,
                error=str(exc),
            )
            raise PlatformExecutionError(
                f"Fabric get job status failed: {exc}"
            ) from exc

    async def create_table(self, schema: dict[str, Any]) -> str:
        """Create table metadata record for Fabric table operations."""
        table_id = str(
            schema.get("table_id")
            or schema.get("name")
            or f"fabric-table-{uuid.uuid4().hex[:12]}"
        )
        self._resource_cache[table_id] = dict(schema)
        await self._persist_resource("table", table_id, schema)
        logger.info(
            "fabric_adapter.table_created",
            table_id=table_id,
            schema_keys=sorted(schema.keys()),
        )
        return table_id

    async def list_tables(self) -> list[dict[str, Any]]:
        """List Fabric table metadata known by adapter."""
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
        """Create shortcut metadata record for OneLake shortcuts."""
        shortcut_id = str(
            config.get(
                "shortcut_id") or f"fabric-shortcut-{uuid.uuid4().hex[:12]}"
        )
        self._resource_cache[shortcut_id] = dict(config)
        await self._persist_resource("shortcut", shortcut_id, config)
        logger.info(
            "fabric_adapter.shortcut_created",
            shortcut_id=shortcut_id,
            config_keys=sorted(config.keys()),
        )
        return shortcut_id

    async def execute_sql(self, sql: str) -> dict[str, Any]:
        """Execute SQL through Fabric job submission path."""
        if not sql.strip():
            raise PlatformExecutionError(
                "Fabric SQL execution requires non-empty SQL.")

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
                "platform": "fabric",
            }
        except Exception as exc:
            logger.error(
                "fabric_adapter.sql_execution_failed",
                error=str(exc),
            )
            raise PlatformExecutionError(
                f"Fabric SQL execution failed: {exc}"
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
