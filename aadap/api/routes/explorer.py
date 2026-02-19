"""
AADAP — Explorer API Routes
==============================
REST endpoints for exploring Fabric and Databricks resources.

These operations bypass code generation and directly query platform APIs
for read-only operations like listing tables, previewing data, etc.

Endpoints:
    GET /api/v1/explorer/{platform}/catalogs
    GET /api/v1/explorer/{platform}/schemas?catalog=
    GET /api/v1/explorer/{platform}/tables?catalog=&schema=
    GET /api/v1/explorer/{platform}/tables/{fqn}
    GET /api/v1/explorer/{platform}/tables/{fqn}/preview
    GET /api/v1/explorer/{platform}/files?path=
    GET /api/v1/explorer/{platform}/notebooks
    GET /api/v1/explorer/{platform}/jobs
    GET /api/v1/explorer/{platform}/pipelines
    GET /api/v1/explorer/{platform}/lakehouses (Fabric only)
    GET /api/v1/explorer/{platform}/shortcuts (Fabric only)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Any

from aadap.core.logging import get_logger
from aadap.integrations.databricks_client import DatabricksClient
from aadap.integrations.fabric_client import FabricClient
from aadap.services.databricks_explorer import DatabricksExplorerService
from aadap.services.fabric_explorer import FabricExplorerService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/explorer", tags=["explorer"])


# ── Response Models ────────────────────────────────────────────────────────


class CatalogResponse(BaseModel):
    id: str
    name: str
    type: str
    description: str | None = None


class SchemaResponse(BaseModel):
    id: str
    name: str
    catalog_id: str
    type: str
    description: str | None = None


class TableResponse(BaseModel):
    id: str
    name: str
    schema_name: str
    catalog_name: str
    full_name: str
    type: str
    row_count: int | None = None


class ColumnResponse(BaseModel):
    name: str
    data_type: str
    nullable: bool = True
    comment: str | None = None


class TableDetailResponse(BaseModel):
    id: str
    name: str
    schema_name: str
    catalog_name: str
    full_name: str
    columns: list[ColumnResponse]
    table_type: str | None = None
    row_count: int | None = None
    comment: str | None = None


class TablePreviewResponse(BaseModel):
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool = False


class FileResponse(BaseModel):
    name: str
    path: str
    type: str
    size: int | None = None


class NotebookResponse(BaseModel):
    id: str
    name: str
    path: str | None = None


class JobResponse(BaseModel):
    id: str
    name: str
    status: str | None = None


class PipelineResponse(BaseModel):
    id: str
    name: str
    status: str | None = None


# ── Service Helpers ────────────────────────────────────────────────────────


def get_databricks_explorer() -> DatabricksExplorerService:
    """Get Databricks explorer service."""
    try:
        client = DatabricksClient.from_settings()
        return DatabricksExplorerService(client)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Databricks not configured: {e}")


def get_fabric_explorer() -> FabricExplorerService:
    """Get Fabric explorer service."""
    try:
        client = FabricClient.from_settings()
        return FabricExplorerService(client)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Fabric not configured: {e}")


# ── Catalog Endpoints ──────────────────────────────────────────────────────


@router.get(
    "/{platform}/catalogs",
    response_model=list[CatalogResponse],
    summary="List catalogs",
)
async def list_catalogs(platform: str):
    """List all catalogs/workspaces."""
    platform = platform.lower()

    if platform == "databricks":
        explorer = get_databricks_explorer()
        catalogs = await explorer.list_catalogs()
    elif platform == "fabric":
        explorer = get_fabric_explorer()
        catalogs = await explorer.list_workspaces()
    else:
        raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}")

    return [
        CatalogResponse(
            id=c.id,
            name=c.name,
            type=c.type,
            description=c.description,
        )
        for c in catalogs
    ]


@router.get(
    "/{platform}/schemas",
    response_model=list[SchemaResponse],
    summary="List schemas",
)
async def list_schemas(
    platform: str,
    catalog: str = Query(..., description="Catalog name"),
):
    """List all schemas/lakehouses in a catalog."""
    platform = platform.lower()

    if platform == "databricks":
        explorer = get_databricks_explorer()
        schemas = await explorer.list_schemas(catalog)
    elif platform == "fabric":
        explorer = get_fabric_explorer()
        schemas = await explorer.list_lakehouses(catalog)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}")

    return [
        SchemaResponse(
            id=s.id,
            name=s.name,
            catalog_id=s.catalog_id,
            type=s.type,
            description=s.description,
        )
        for s in schemas
    ]


# ── Table Endpoints ────────────────────────────────────────────────────────


@router.get(
    "/{platform}/tables",
    response_model=list[TableResponse],
    summary="List tables",
)
async def list_tables(
    platform: str,
    catalog: str = Query(..., description="Catalog name"),
    schema: str = Query(..., description="Schema name"),
):
    """List all tables in a schema."""
    platform = platform.lower()

    if platform == "databricks":
        explorer = get_databricks_explorer()
        tables = await explorer.list_tables(catalog, schema)
    elif platform == "fabric":
        explorer = get_fabric_explorer()
        tables = await explorer.list_tables(catalog, schema)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}")

    return [
        TableResponse(
            id=t.id,
            name=t.name,
            schema_name=t.schema_name,
            catalog_name=t.catalog_name,
            full_name=t.full_name,
            type=t.type,
            row_count=t.row_count,
        )
        for t in tables
    ]


@router.get(
    "/{platform}/tables/{full_name:path}",
    response_model=TableDetailResponse,
    summary="Get table details",
)
async def get_table_detail(platform: str, full_name: str):
    """Get table schema and details."""
    platform = platform.lower()

    parts = full_name.split(".")
    if len(parts) != 3:
        raise HTTPException(status_code=400, detail="Table name must be catalog.schema.table")

    catalog, schema, table = parts

    if platform == "databricks":
        explorer = get_databricks_explorer()
        detail = await explorer.get_table_schema(catalog, schema, table)
    elif platform == "fabric":
        explorer = get_fabric_explorer()
        detail = await explorer.get_table_schema(catalog, schema, table)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}")

    if detail is None:
        raise HTTPException(status_code=404, detail="Table not found")

    return TableDetailResponse(
        id=detail.id,
        name=detail.name,
        schema_name=detail.schema_name,
        catalog_name=detail.catalog_name,
        full_name=detail.full_name,
        columns=[
            ColumnResponse(name=c.name, data_type=c.data_type, nullable=c.nullable, comment=c.comment)
            for c in detail.columns
        ],
        table_type=detail.table_type,
        row_count=detail.row_count,
        comment=detail.comment,
    )


@router.get(
    "/{platform}/tables/{full_name:path}/preview",
    response_model=TablePreviewResponse,
    summary="Preview table data",
)
async def preview_table(
    platform: str,
    full_name: str,
    limit: int = Query(default=100, ge=1, le=1000),
):
    """Preview table data (first N rows)."""
    platform = platform.lower()

    parts = full_name.split(".")
    if len(parts) != 3:
        raise HTTPException(status_code=400, detail="Table name must be catalog.schema.table")

    catalog, schema, table = parts

    if platform == "databricks":
        explorer = get_databricks_explorer()
        preview = await explorer.preview_table(catalog, schema, table, limit)
    elif platform == "fabric":
        explorer = get_fabric_explorer()
        preview = await explorer.preview_table(catalog, schema, table, limit)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}")

    if preview is None:
        raise HTTPException(status_code=404, detail="Could not preview table")

    return TablePreviewResponse(
        columns=preview.columns,
        rows=preview.rows,
        row_count=preview.row_count,
        truncated=preview.truncated,
    )


# ── File Endpoints ────────────────────────────────────────────────────────


@router.get(
    "/{platform}/files",
    response_model=list[FileResponse],
    summary="List files",
)
async def list_files(
    platform: str,
    path: str = Query(default="/", description="Path to list"),
    workspace_id: str | None = Query(default=None, description="Workspace ID (Fabric)"),
    lakehouse_id: str | None = Query(default=None, description="Lakehouse ID (Fabric)"),
):
    """List files and directories."""
    platform = platform.lower()

    if platform == "databricks":
        explorer = get_databricks_explorer()
        files = await explorer.list_files(path)
    elif platform == "fabric":
        if not workspace_id or not lakehouse_id:
            raise HTTPException(status_code=400, detail="workspace_id and lakehouse_id required for Fabric")
        explorer = get_fabric_explorer()
        files = await explorer.list_files(workspace_id, lakehouse_id, path)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}")

    return [
        FileResponse(name=f.name, path=f.path, type=f.type, size=f.size)
        for f in files
    ]


# ── Notebook Endpoints ─────────────────────────────────────────────────────


@router.get(
    "/{platform}/notebooks",
    response_model=list[NotebookResponse],
    summary="List notebooks",
)
async def list_notebooks(
    platform: str,
    path: str = Query(default="/", description="Path to search (Databricks)"),
    workspace_id: str | None = Query(default=None, description="Workspace ID (Fabric)"),
):
    """List all notebooks."""
    platform = platform.lower()

    if platform == "databricks":
        explorer = get_databricks_explorer()
        notebooks = await explorer.list_notebooks(path)
    elif platform == "fabric":
        if not workspace_id:
            raise HTTPException(status_code=400, detail="workspace_id required for Fabric")
        explorer = get_fabric_explorer()
        notebooks = await explorer.list_notebooks(workspace_id)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}")

    return [
        NotebookResponse(id=n.id, name=n.name, path=n.path)
        for n in notebooks
    ]


# ── Job Endpoints ──────────────────────────────────────────────────────────


@router.get(
    "/{platform}/jobs",
    response_model=list[JobResponse],
    summary="List jobs",
)
async def list_jobs(platform: str):
    """List all jobs."""
    platform = platform.lower()

    if platform == "databricks":
        explorer = get_databricks_explorer()
        jobs = await explorer.list_jobs()
    else:
        raise HTTPException(status_code=400, detail=f"Jobs not supported on {platform}")

    return [
        JobResponse(id=j.id, name=j.name, status=j.status)
        for j in jobs
    ]


# ── Pipeline Endpoints ─────────────────────────────────────────────────────


@router.get(
    "/{platform}/pipelines",
    response_model=list[PipelineResponse],
    summary="List pipelines",
)
async def list_pipelines(
    platform: str,
    workspace_id: str | None = Query(default=None, description="Workspace ID (Fabric)"),
):
    """List all pipelines/DLT."""
    platform = platform.lower()

    if platform == "databricks":
        explorer = get_databricks_explorer()
        pipelines = await explorer.list_pipelines()
    elif platform == "fabric":
        if not workspace_id:
            raise HTTPException(status_code=400, detail="workspace_id required for Fabric")
        explorer = get_fabric_explorer()
        pipelines = await explorer.list_pipelines(workspace_id)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}")

    return [
        PipelineResponse(id=p.id, name=p.name, status=p.status)
        for p in pipelines
    ]


# ── Fabric-specific Endpoints ──────────────────────────────────────────────


@router.get(
    "/fabric/lakehouses",
    response_model=list[SchemaResponse],
    summary="List lakehouses (Fabric only)",
)
async def list_lakehouses(
    workspace_id: str = Query(..., description="Workspace ID"),
):
    """List all lakehouses in a Fabric workspace."""
    explorer = get_fabric_explorer()
    lakehouses = await explorer.list_lakehouses(workspace_id)

    return [
        SchemaResponse(
            id=l.id,
            name=l.name,
            catalog_id=l.catalog_id,
            type=l.type,
            description=l.description,
        )
        for l in lakehouses
    ]


@router.get(
    "/fabric/shortcuts",
    response_model=list[dict[str, Any]],
    summary="List shortcuts (Fabric only)",
)
async def list_shortcuts(
    workspace_id: str = Query(..., description="Workspace ID"),
    lakehouse_id: str = Query(..., description="Lakehouse ID"),
):
    """List all shortcuts in a Fabric lakehouse."""
    explorer = get_fabric_explorer()
    shortcuts = await explorer.list_shortcuts(workspace_id, lakehouse_id)
    return shortcuts
