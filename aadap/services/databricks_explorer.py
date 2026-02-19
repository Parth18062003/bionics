"""
AADAP — Databricks Explorer Service
=======================================
Service for exploring Databricks resources via REST API.
Supports listing and reading operations without code generation.

Operations:
- List catalogs, schemas, tables
- List files, notebooks, jobs, pipelines
- Preview table data
- Get table schema/DDL

Uses Databricks SDK with CLI authentication.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from aadap.core.logging import get_logger
from aadap.integrations.databricks_client import DatabricksClient

logger = get_logger(__name__)


# ── Data Models ────────────────────────────────────────────────────────────


@dataclass
class CatalogSummary:
    """Summary of a catalog."""

    id: str
    name: str
    type: str = "catalog"
    description: str | None = None
    owner: str | None = None


@dataclass
class SchemaSummary:
    """Summary of a schema."""

    id: str
    name: str
    catalog_name: str
    type: str = "schema"
    description: str | None = None
    owner: str | None = None


@dataclass
class TableSummary:
    """Summary of a table."""

    id: str
    name: str
    schema_name: str
    catalog_name: str
    full_name: str
    type: str = "table"
    table_type: str = "MANAGED"
    row_count: int | None = None
    size_bytes: int | None = None
    created_at: str | None = None


@dataclass
class ColumnInfo:
    """Column information."""

    name: str
    data_type: str
    nullable: bool = True
    comment: str | None = None


@dataclass
class TableDetail:
    """Detailed table information."""

    id: str
    name: str
    schema_name: str
    catalog_name: str
    full_name: str
    columns: list[ColumnInfo] = field(default_factory=list)
    table_type: str = "MANAGED"
    row_count: int | None = None
    size_bytes: int | None = None
    created_at: str | None = None
    last_modified: str | None = None
    comment: str | None = None
    properties: dict[str, str] = field(default_factory=dict)


@dataclass
class TablePreview:
    """Table data preview."""

    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool = False
    schema: list[dict[str, str]] = field(default_factory=list)


@dataclass
class FileSummary:
    """File/folder summary."""

    name: str
    path: str
    type: str  # "file" | "directory"
    size: int | None = None
    last_modified: str | None = None


@dataclass
class NotebookSummary:
    """Notebook summary."""

    id: str
    name: str
    path: str
    language: str | None = None
    created_at: str | None = None
    last_modified: str | None = None


@dataclass
class JobSummary:
    """Job summary."""

    id: str
    name: str
    status: str | None = None
    created_at: str | None = None
    last_run: str | None = None


@dataclass
class PipelineSummary:
    """DLT Pipeline summary."""

    id: str
    name: str
    status: str | None = None
    created_at: str | None = None
    last_modified: str | None = None


# ── Databricks Explorer Service ────────────────────────────────────────────


class DatabricksExplorerService:
    """
    Service for exploring Databricks resources via REST API.

    Uses the DatabricksClient for authentication and API calls.
    All operations are read-only and don't generate code.
    """

    def __init__(self, client: DatabricksClient) -> None:
        self._client = client
        self._workspace_client = None

    def _get_workspace_client(self):
        """Get or create the workspace client."""
        if self._workspace_client is None:
            self._workspace_client = self._client._get_workspace_client()
        return self._workspace_client

    # ── Catalog Operations (Unity Catalog) ────────────────────────────────

    async def list_catalogs(self) -> list[CatalogSummary]:
        """List all catalogs."""
        w = self._get_workspace_client()

        def _list():
            catalogs = []
            for cat in w.catalogs.list():
                catalogs.append(CatalogSummary(
                    id=cat.name or "",
                    name=cat.name or "",
                    type="catalog",
                    description=cat.comment,
                    owner=cat.owner,
                ))
            return catalogs

        result = await asyncio.to_thread(_list)
        logger.info("databricks.list_catalogs", count=len(result))
        return result

    async def list_schemas(self, catalog_name: str) -> list[SchemaSummary]:
        """List all schemas in a catalog."""
        w = self._get_workspace_client()

        def _list():
            schemas = []
            for sch in w.schemas.list(catalog_name=catalog_name):
                schemas.append(SchemaSummary(
                    id=sch.full_name or sch.name or "",
                    name=sch.name or "",
                    catalog_name=catalog_name,
                    type="schema",
                    description=sch.comment,
                    owner=sch.owner,
                ))
            return schemas

        result = await asyncio.to_thread(_list)
        logger.info("databricks.list_schemas", catalog=catalog_name, count=len(result))
        return result

    async def list_tables(
        self,
        catalog_name: str,
        schema_name: str,
    ) -> list[TableSummary]:
        """List all tables in a schema."""
        w = self._get_workspace_client()

        def _list():
            tables = []
            for tbl in w.tables.list(
                catalog_name=catalog_name,
                schema_name=schema_name,
            ):
                full_name = f"{catalog_name}.{schema_name}.{tbl.name}" if tbl.name else ""
                tables.append(TableSummary(
                    id=tbl.table_id or full_name,
                    name=tbl.name or "",
                    schema_name=schema_name,
                    catalog_name=catalog_name,
                    full_name=full_name,
                    type="table",
                    table_type=tbl.table_type.value if tbl.table_type else "MANAGED",
                    row_count=None,
                    size_bytes=None,
                    created_at=str(tbl.created_at) if tbl.created_at else None,
                ))
            return tables

        result = await asyncio.to_thread(_list)
        logger.info("databricks.list_tables", catalog=catalog_name, schema=schema_name, count=len(result))
        return result

    async def get_table_schema(
        self,
        catalog_name: str,
        schema_name: str,
        table_name: str,
    ) -> TableDetail | None:
        """Get detailed table schema."""
        w = self._get_workspace_client()
        full_name = f"{catalog_name}.{schema_name}.{table_name}"

        def _get():
            try:
                tbl = w.tables.get(full_name)
                columns = []

                for col in (tbl.columns or []):
                    columns.append(ColumnInfo(
                        name=col.name or "",
                        data_type=col.type_text or col.type_json or "unknown",
                        nullable=col.nullable if col.nullable is not None else True,
                        comment=col.comment,
                    ))

                return TableDetail(
                    id=tbl.table_id or full_name,
                    name=tbl.name or table_name,
                    schema_name=schema_name,
                    catalog_name=catalog_name,
                    full_name=full_name,
                    columns=columns,
                    table_type=tbl.table_type.value if tbl.table_type else "MANAGED",
                    row_count=None,
                    size_bytes=None,
                    created_at=str(tbl.created_at) if tbl.created_at else None,
                    last_modified=str(tbl.updated_at) if tbl.updated_at else None,
                    comment=tbl.comment,
                    properties=tbl.properties or {},
                )
            except Exception as e:
                logger.warning("databricks.get_table_schema_failed", error=str(e))
                return None

        result = await asyncio.to_thread(_get)
        if result:
            logger.info("databricks.get_table_schema", table=full_name, columns=len(result.columns))
        return result

    async def preview_table(
        self,
        catalog_name: str,
        schema_name: str,
        table_name: str,
        limit: int = 100,
    ) -> TablePreview | None:
        """Preview table data using SQL statement execution."""
        full_name = f"{catalog_name}.{schema_name}.{table_name}"
        query = f"SELECT * FROM {full_name} LIMIT {limit}"

        from databricks.sdk.service.sql import ExecuteStatementRequestOnWaitTimeout as TimeoutAction
        w = self._get_workspace_client()

        if not self._client._warehouse_id:
            logger.warning("databricks.preview_table_no_warehouse")
            return None

        def _execute():
            try:
                response = w.statement_execution.execute_statement(
                    statement=query,
                    warehouse_id=self._client._warehouse_id,
                    catalog=catalog_name,
                    schema=schema_name,
                    wait_timeout="50s",
                    on_wait_timeout=TimeoutAction.CANCEL,
                )

                if not response.status or response.status.state != "SUCCEEDED":
                    return None

                columns = [c.name for c in (response.manifest.schema.columns or [])]
                rows = []

                if response.result and response.result.data_array:
                    for row in response.result.data_array:
                        rows.append(list(row) if row else [])

                return TablePreview(
                    columns=columns,
                    rows=rows,
                    row_count=len(rows),
                    truncated=len(rows) >= limit,
                    schema=[{"name": c.name, "type": c.type_text} for c in (response.manifest.schema.columns or [])],
                )
            except Exception as e:
                logger.warning("databricks.preview_table_failed", error=str(e))
                return None

        result = await asyncio.to_thread(_execute)
        if result:
            logger.info("databricks.preview_table", table=full_name, rows=result.row_count)
        return result

    # ── Workspace Operations ─────────────────────────────────────────────

    async def list_files(self, path: str = "/") -> list[FileSummary]:
        """List files and directories in workspace."""
        w = self._get_workspace_client()

        def _list():
            files = []
            try:
                for item in w.workspace.list(path):
                    files.append(FileSummary(
                        name=item.path.split("/")[-1] if item.path else "",
                        path=item.path or "",
                        type="directory" if item.object_type and item.object_type.value == "DIRECTORY" else "file",
                        size=None,
                        last_modified=None,
                    ))
            except Exception as e:
                logger.warning("databricks.list_files_failed", error=str(e))
            return files

        result = await asyncio.to_thread(_list)
        logger.info("databricks.list_files", path=path, count=len(result))
        return result

    async def list_notebooks(self, path: str = "/") -> list[NotebookSummary]:
        """List all notebooks in workspace."""
        w = self._get_workspace_client()

        def _list():
            notebooks = []
            try:
                for item in w.workspace.list(path):
                    if item.object_type and item.object_type.value == "NOTEBOOK":
                        notebooks.append(NotebookSummary(
                            id=str(item.object_id) if item.object_id else "",
                            name=item.path.split("/")[-1] if item.path else "",
                            path=item.path or "",
                            language=item.language.value if item.language else None,
                            created_at=None,
                            last_modified=None,
                        ))
            except Exception as e:
                logger.warning("databricks.list_notebooks_failed", error=str(e))
            return notebooks

        result = await asyncio.to_thread(_list)
        logger.info("databricks.list_notebooks", path=path, count=len(result))
        return result

    # ── Job Operations ───────────────────────────────────────────────────

    async def list_jobs(self) -> list[JobSummary]:
        """List all jobs."""
        w = self._get_workspace_client()

        def _list():
            jobs = []
            try:
                for job in w.jobs.list():
                    jobs.append(JobSummary(
                        id=str(job.job_id) if job.job_id else "",
                        name=job.settings.name if job.settings else "",
                        status=None,
                        created_at=str(job.created_time) if job.created_time else None,
                        last_run=None,
                    ))
            except Exception as e:
                logger.warning("databricks.list_jobs_failed", error=str(e))
            return jobs

        result = await asyncio.to_thread(_list)
        logger.info("databricks.list_jobs", count=len(result))
        return result

    # ── Pipeline Operations (DLT) ────────────────────────────────────────

    async def list_pipelines(self) -> list[PipelineSummary]:
        """List all DLT pipelines."""
        w = self._get_workspace_client()

        def _list():
            pipelines = []
            try:
                for pipe in w.pipelines.list_pipelines():
                    pipelines.append(PipelineSummary(
                        id=pipe.pipeline_id or "",
                        name=pipe.name or "",
                        status=pipe.state.value if pipe.state else None,
                        created_at=str(pipe.created_at) if pipe.created_at else None,
                        last_modified=str(pipe.last_modified) if pipe.last_modified else None,
                    ))
            except Exception as e:
                logger.warning("databricks.list_pipelines_failed", error=str(e))
            return pipelines

        result = await asyncio.to_thread(_list)
        logger.info("databricks.list_pipelines", count=len(result))
        return result


import asyncio
