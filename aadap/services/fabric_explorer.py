"""
AADAP — Microsoft Fabric Explorer Service
=============================================
Service for exploring Fabric resources via REST API.
Supports listing and reading operations without code generation.

Operations:
- List workspaces, lakehouses, schemas, tables
- List files, notebooks, pipelines, jobs
- Preview table data
- Get table schema/DDL

Uses Fabric REST API with Service Principal Authentication.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from aadap.core.logging import get_logger
from aadap.integrations.fabric_client import FabricClient

logger = get_logger(__name__)


# ── Data Models ────────────────────────────────────────────────────────────


@dataclass
class CatalogSummary:
    """Summary of a catalog/workspace."""

    id: str
    name: str
    type: str = "workspace"
    description: str | None = None
    created_at: str | None = None


@dataclass
class SchemaSummary:
    """Summary of a schema/lakehouse."""

    id: str
    name: str
    catalog_id: str
    type: str = "lakehouse"
    description: str | None = None


@dataclass
class TableSummary:
    """Summary of a table."""

    id: str
    name: str
    schema_name: str
    catalog_name: str
    full_name: str
    type: str = "table"
    row_count: int | None = None
    size_bytes: int | None = None
    created_at: str | None = None


@dataclass
class ColumnInfo:
    """Column information."""

    name: str
    data_type: str
    nullable: bool = True
    description: str | None = None


@dataclass
class TableDetail:
    """Detailed table information."""

    id: str
    name: str
    schema_name: str
    catalog_name: str
    full_name: str
    columns: list[ColumnInfo] = field(default_factory=list)
    row_count: int | None = None
    size_bytes: int | None = None
    created_at: str | None = None
    last_modified: str | None = None


@dataclass
class TablePreview:
    """Table data preview."""

    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool = False


@dataclass
class FileSummary:
    """File/folder summary."""

    name: str
    path: str
    type: str  # "file" | "folder"
    size: int | None = None
    last_modified: str | None = None


@dataclass
class NotebookSummary:
    """Notebook summary."""

    id: str
    name: str
    path: str | None = None
    created_at: str | None = None
    last_modified: str | None = None


@dataclass
class PipelineSummary:
    """Pipeline/Dataflow summary."""

    id: str
    name: str
    type: str  # "pipeline" | "dataflow"
    created_at: str | None = None
    last_modified: str | None = None


@dataclass
class JobSummary:
    """Job summary."""

    id: str
    name: str
    status: str
    last_run: str | None = None
    next_run: str | None = None


# ── Fabric Explorer Service ────────────────────────────────────────────────


class FabricExplorerService:
    """
    Service for exploring Microsoft Fabric resources via REST API.

    Uses the FabricClient for authentication and API calls.
    All operations are read-only and don't generate code.
    """

    FABRIC_API_BASE = "https://api.fabric.microsoft.com/v1"

    def __init__(self, client: FabricClient) -> None:
        self._client = client

    async def _get_headers(self, correlation_id: str | None = None) -> dict[str, str]:
        """Get authenticated headers."""
        token = await self._client._acquire_token()
        return self._client._build_headers(token, correlation_id)

    # ── Workspace Operations ──────────────────────────────────────────────

    async def list_workspaces(self) -> list[CatalogSummary]:
        """List all accessible workspaces."""
        import httpx

        headers = await self._get_headers()
        url = f"{self.FABRIC_API_BASE}/workspaces"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)

            if response.status_code != 200:
                logger.warning("fabric.list_workspaces_failed", status=response.status_code)
                return []

            data = response.json()
            workspaces = []

            for item in data.get("value", []):
                workspaces.append(CatalogSummary(
                    id=item.get("id", ""),
                    name=item.get("displayName", item.get("id", "")),
                    type="workspace",
                    description=item.get("description"),
                    created_at=item.get("createdDateTime"),
                ))

            logger.info("fabric.list_workspaces", count=len(workspaces))
            return workspaces

    # ── Lakehouse Operations ──────────────────────────────────────────────

    async def list_lakehouses(self, workspace_id: str) -> list[SchemaSummary]:
        """List all lakehouses in a workspace."""
        import httpx

        headers = await self._get_headers()
        url = f"{self.FABRIC_API_BASE}/workspaces/{workspace_id}/lakehouses"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)

            if response.status_code != 200:
                logger.warning("fabric.list_lakehouses_failed", status=response.status_code)
                return []

            data = response.json()
            lakehouses = []

            for item in data.get("value", []):
                lakehouses.append(SchemaSummary(
                    id=item.get("id", ""),
                    name=item.get("displayName", item.get("id", "")),
                    catalog_id=workspace_id,
                    type="lakehouse",
                    description=item.get("description"),
                ))

            logger.info("fabric.list_lakehouses", workspace_id=workspace_id, count=len(lakehouses))
            return lakehouses

    # ── Table Operations ──────────────────────────────────────────────────

    async def list_tables(
        self,
        workspace_id: str,
        lakehouse_id: str,
    ) -> list[TableSummary]:
        """List all tables in a lakehouse."""
        import httpx

        headers = await self._get_headers()
        url = f"{self.FABRIC_API_BASE}/workspaces/{workspace_id}/lakehouses/{lakehouse_id}/tables"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)

            if response.status_code != 200:
                logger.warning("fabric.list_tables_failed", status=response.status_code)
                return []

            data = response.json()
            tables = []

            for item in data.get("value", []):
                tables.append(TableSummary(
                    id=item.get("id", ""),
                    name=item.get("name", ""),
                    schema_name=item.get("schemaName", "dbo"),
                    catalog_name=lakehouse_id,
                    full_name=item.get("name", ""),
                    type=item.get("type", "table"),
                    row_count=item.get("rowCount"),
                    size_bytes=item.get("size"),
                    created_at=item.get("created"),
                ))

            logger.info("fabric.list_tables", workspace_id=workspace_id, lakehouse_id=lakehouse_id, count=len(tables))
            return tables

    async def get_table_schema(
        self,
        workspace_id: str,
        lakehouse_id: str,
        table_name: str,
    ) -> TableDetail | None:
        """Get table schema (column definitions)."""
        import httpx

        headers = await self._get_headers()
        url = f"{self.FABRIC_API_BASE}/workspaces/{workspace_id}/lakehouses/{lakehouse_id}/tables/{table_name}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)

            if response.status_code != 200:
                logger.warning("fabric.get_table_schema_failed", status=response.status_code)
                return None

            data = response.json()
            columns = []

            for col in data.get("columns", []):
                columns.append(ColumnInfo(
                    name=col.get("name", ""),
                    data_type=col.get("dataType", col.get("type", "string")),
                    nullable=col.get("nullable", True),
                    description=col.get("description"),
                ))

            return TableDetail(
                id=data.get("id", ""),
                name=data.get("name", table_name),
                schema_name=data.get("schemaName", "dbo"),
                catalog_name=lakehouse_id,
                full_name=data.get("name", table_name),
                columns=columns,
                row_count=data.get("rowCount"),
                size_bytes=data.get("size"),
                created_at=data.get("created"),
                last_modified=data.get("lastModified"),
            )

    async def preview_table(
        self,
        workspace_id: str,
        lakehouse_id: str,
        table_name: str,
        limit: int = 100,
    ) -> TablePreview | None:
        """Preview table data (first N rows)."""
        import httpx

        headers = await self._get_headers()
        url = f"{self.FABRIC_API_BASE}/workspaces/{workspace_id}/lakehouses/{lakehouse_id}/tables/{table_name}/preview"

        params = {"top": limit}

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(url, headers=headers, params=params)

            if response.status_code != 200:
                logger.warning("fabric.preview_table_failed", status=response.status_code)
                return None

            data = response.json()

            columns = data.get("columns", [])
            rows = data.get("rows", [])

            return TablePreview(
                columns=columns,
                rows=rows,
                row_count=len(rows),
                truncated=len(rows) >= limit,
            )

    # ── File Operations ───────────────────────────────────────────────────

    async def list_files(
        self,
        workspace_id: str,
        lakehouse_id: str,
        path: str = "/",
    ) -> list[FileSummary]:
        """List files and folders in a lakehouse path."""
        import httpx

        headers = await self._get_headers()
        url = f"{self.FABRIC_API_BASE}/workspaces/{workspace_id}/lakehouses/{lakehouse_id}/files"

        params = {}
        if path and path != "/":
            params["path"] = path

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers, params=params)

            if response.status_code != 200:
                logger.warning("fabric.list_files_failed", status=response.status_code)
                return []

            data = response.json()
            files = []

            for item in data.get("value", []):
                files.append(FileSummary(
                    name=item.get("name", ""),
                    path=item.get("path", ""),
                    type="folder" if item.get("isFolder") else "file",
                    size=item.get("size"),
                    last_modified=item.get("lastModified"),
                ))

            logger.info("fabric.list_files", path=path, count=len(files))
            return files

    # ── Notebook Operations ───────────────────────────────────────────────

    async def list_notebooks(self, workspace_id: str) -> list[NotebookSummary]:
        """List all notebooks in a workspace."""
        import httpx

        headers = await self._get_headers()
        url = f"{self.FABRIC_API_BASE}/workspaces/{workspace_id}/notebooks"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)

            if response.status_code != 200:
                logger.warning("fabric.list_notebooks_failed", status=response.status_code)
                return []

            data = response.json()
            notebooks = []

            for item in data.get("value", []):
                notebooks.append(NotebookSummary(
                    id=item.get("id", ""),
                    name=item.get("displayName", item.get("id", "")),
                    created_at=item.get("createdDateTime"),
                    last_modified=item.get("lastModifiedDateTime"),
                ))

            logger.info("fabric.list_notebooks", workspace_id=workspace_id, count=len(notebooks))
            return notebooks

    # ── Pipeline Operations ───────────────────────────────────────────────

    async def list_pipelines(self, workspace_id: str) -> list[PipelineSummary]:
        """List all data pipelines in a workspace."""
        import httpx

        headers = await self._get_headers()
        url = f"{self.FABRIC_API_BASE}/workspaces/{workspace_id}/dataPipelines"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)

            if response.status_code != 200:
                logger.warning("fabric.list_pipelines_failed", status=response.status_code)
                return []

            data = response.json()
            pipelines = []

            for item in data.get("value", []):
                pipelines.append(PipelineSummary(
                    id=item.get("id", ""),
                    name=item.get("displayName", item.get("id", "")),
                    type="pipeline",
                    created_at=item.get("createdDateTime"),
                    last_modified=item.get("lastModifiedDateTime"),
                ))

            logger.info("fabric.list_pipelines", workspace_id=workspace_id, count=len(pipelines))
            return pipelines

    # ── Shortcut Operations ───────────────────────────────────────────────

    async def list_shortcuts(
        self,
        workspace_id: str,
        lakehouse_id: str,
    ) -> list[dict[str, Any]]:
        """List all shortcuts in a lakehouse."""
        import httpx

        headers = await self._get_headers()
        url = f"{self.FABRIC_API_BASE}/workspaces/{workspace_id}/lakehouses/{lakehouse_id}/shortcuts"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)

            if response.status_code != 200:
                logger.warning("fabric.list_shortcuts_failed", status=response.status_code)
                return []

            data = response.json()
            shortcuts = []

            for item in data.get("value", []):
                shortcuts.append({
                    "id": item.get("id", ""),
                    "name": item.get("name", ""),
                    "path": item.get("path", ""),
                    "target": item.get("target", {}),
                    "created_at": item.get("createdDateTime"),
                })

            logger.info("fabric.list_shortcuts", workspace_id=workspace_id, lakehouse_id=lakehouse_id, count=len(shortcuts))
            return shortcuts
