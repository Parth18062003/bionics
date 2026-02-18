"""
AADAP — Agent Marketplace Service
=====================================
Provides a catalog of available agents with metadata for the frontend
Agent Marketplace page.

Architecture layer: L4 (Agent Layer) / L6 (Presentation support).

Each agent entry describes:
- Unique identifier and display name
- Target platform (Databricks, Fabric, etc.)
- Supported language(s)
- Description and capabilities
- Required configuration
- Availability status

Usage:
    from aadap.services.marketplace import get_agent_catalog
    agents = get_agent_catalog()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AgentCatalogEntry:
    """An agent available in the marketplace."""

    id: str
    name: str
    description: str
    platform: str
    languages: list[str]
    capabilities: list[str]
    icon: str
    status: str = "available"  # available | coming_soon | beta
    config_defaults: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "platform": self.platform,
            "languages": self.languages,
            "capabilities": self.capabilities,
            "icon": self.icon,
            "status": self.status,
            "config_defaults": self.config_defaults,
        }


# ── Agent Catalog ──────────────────────────────────────────────────────

_AGENT_CATALOG: list[AgentCatalogEntry] = [
    AgentCatalogEntry(
        id="adb-sql",
        name="ADB SQL Agent",
        description=(
            "Generates and executes SQL queries on Azure Databricks SQL Warehouse. "
            "Ideal for data exploration, ETL transformations, table creation, "
            "and analytical queries using Spark SQL syntax."
        ),
        platform="Azure Databricks",
        languages=["sql"],
        capabilities=[
            "SQL code generation via Azure AI Foundry",
            "Execution on Databricks SQL Warehouse",
            "Safety analysis (destructive op detection)",
            "Result retrieval and artifact storage",
            "Real-time status tracking",
        ],
        icon="🗄️",
        status="available",
        config_defaults={"language": "sql", "environment": "SANDBOX"},
    ),
    AgentCatalogEntry(
        id="adb-python",
        name="ADB Python Agent",
        description=(
            "Generates and executes Python/PySpark code on Azure Databricks. "
            "Suitable for complex data transformations, ML pipelines, "
            "custom UDFs, and advanced data engineering workflows."
        ),
        platform="Azure Databricks",
        languages=["python", "pyspark"],
        capabilities=[
            "Python/PySpark code generation via Azure AI Foundry",
            "Execution on Databricks Compute Cluster",
            "AST-based safety analysis",
            "Self-correction (up to 3 attempts per INV-03)",
            "PySpark optimization suggestions",
        ],
        icon="🐍",
        status="available",
        config_defaults={"language": "python", "environment": "SANDBOX"},
    ),
    AgentCatalogEntry(
        id="fabric-scala",
        name="Fabric Scala Agent",
        description=(
            "Generates Scala/Spark code for Microsoft Fabric workloads. "
            "Targets Fabric Lakehouse and Warehouse for enterprise-scale "
            "data processing and analytics."
        ),
        platform="Microsoft Fabric",
        languages=["scala"],
        capabilities=[
            "Scala/Spark code generation via Azure AI Foundry",
            "Execution on Fabric Spark notebooks",
            "Fabric Lakehouse integration",
            "Data pipeline orchestration",
            "Delta Lake operations",
            "Safety analysis (destructive op detection)",
            "SPA authentication (Service Principal)",
        ],
        icon="⚡",
        status="available",
        config_defaults={"language": "scala", "environment": "SANDBOX"},
    ),
    AgentCatalogEntry(
        id="fabric-python",
        name="Fabric Python Agent",
        description=(
            "Generates Python/PySpark code for Microsoft Fabric notebooks. "
            "Supports data exploration, transformation, and ML workflows "
            "within the Fabric ecosystem."
        ),
        platform="Microsoft Fabric",
        languages=["python"],
        capabilities=[
            "Python/PySpark code generation via Azure AI Foundry",
            "Execution on Fabric Spark notebooks",
            "Lakehouse data access via notebookutils/mssparkutils",
            "Semantic model integration",
            "Power BI dataset refresh triggers",
            "Safety analysis (AST-based)",
            "SPA authentication (Service Principal)",
        ],
        icon="🔮",
        status="available",
        config_defaults={"language": "python", "environment": "SANDBOX"},
    ),
    AgentCatalogEntry(
        id="fabric-sql",
        name="Fabric SQL Agent",
        description=(
            "Generates and executes SQL queries on Microsoft Fabric "
            "Lakehouse SQL endpoint or Warehouse. Ideal for data exploration, "
            "ETL transformations, and analytical queries using T-SQL or Spark SQL."
        ),
        platform="Microsoft Fabric",
        languages=["sql"],
        capabilities=[
            "SQL code generation via Azure AI Foundry",
            "Execution on Fabric Lakehouse SQL endpoint",
            "Delta Lake support (MERGE, TIME TRAVEL)",
            "T-SQL and Spark SQL compatibility",
            "Safety analysis (destructive op detection)",
            "SPA authentication (Service Principal)",
        ],
        icon="🏢",
        status="available",
        config_defaults={"language": "sql", "environment": "SANDBOX"},
    ),
    AgentCatalogEntry(
        id="adb-optimization",
        name="ADB Optimization Agent",
        description=(
            "Analyses existing PySpark code and applies performance optimizations. "
            "Focuses on partitioning, caching, broadcast joins, predicate pushdown, "
            "and shuffle reduction."
        ),
        platform="Azure Databricks",
        languages=["python", "pyspark"],
        capabilities=[
            "PySpark performance profiling",
            "Automatic optimization suggestions",
            "Partition strategy recommendations",
            "Cache and broadcast join optimization",
            "Shuffle reduction analysis",
        ],
        icon="🚀",
        status="beta",
        config_defaults={"language": "python", "environment": "SANDBOX"},
    ),
]


def get_agent_catalog() -> list[dict[str, Any]]:
    """Return the full agent catalog as serializable dicts."""
    return [entry.to_dict() for entry in _AGENT_CATALOG]


def get_agent_by_id(agent_id: str) -> dict[str, Any] | None:
    """Look up a single agent entry by ID."""
    for entry in _AGENT_CATALOG:
        if entry.id == agent_id:
            return entry.to_dict()
    return None
