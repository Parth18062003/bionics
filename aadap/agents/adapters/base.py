"""
AADAP — Platform Adapter Abstractions
======================================
Unified adapter interface for platform-specific orchestration operations.

Architecture layer: L4 (Agent Layer).
Adapters provide a stable capability surface for agents while delegating
all platform-specific operations to integration clients.
"""

from __future__ import annotations

import abc
from typing import Any


class PlatformAdapterError(Exception):
    """Base exception for all platform adapter failures."""


class PlatformCapabilityError(PlatformAdapterError):
    """Raised when an adapter operation is not supported by the backing client."""


class PlatformExecutionError(PlatformAdapterError):
    """Raised when an adapter operation fails during execution."""


class PlatformAdapter(abc.ABC):
    """
    Abstract platform adapter contract for capability-specific agents.

    Implementations must wrap existing integration clients and avoid direct
    REST access outside the client layer.
    """

    def __init__(self, platform_name: str) -> None:
        self._platform_name = platform_name

    @property
    def platform_name(self) -> str:
        """Return the adapter platform name."""
        return self._platform_name

    @abc.abstractmethod
    async def create_pipeline(self, definition: dict[str, Any]) -> str:
        """Create a pipeline resource and return its identifier."""
        ...

    @abc.abstractmethod
    async def execute_pipeline(self, pipeline_id: str) -> dict[str, Any]:
        """Execute a pipeline resource and return execution metadata."""
        ...

    @abc.abstractmethod
    async def create_job(self, definition: dict[str, Any]) -> str:
        """Create a job definition and return its identifier."""
        ...

    @abc.abstractmethod
    async def execute_job(
        self,
        job_id: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a job and return submission metadata."""
        ...

    @abc.abstractmethod
    async def get_job_status(self, job_id: str) -> dict[str, Any]:
        """Return canonical job status details for a submitted job."""
        ...

    @abc.abstractmethod
    async def create_table(self, schema: dict[str, Any]) -> str:
        """Create table metadata and return table identifier."""
        ...

    @abc.abstractmethod
    async def list_tables(self) -> list[dict[str, Any]]:
        """List available table metadata objects."""
        ...

    @abc.abstractmethod
    async def create_shortcut(self, config: dict[str, Any]) -> str:
        """Create a shortcut/link resource and return its identifier."""
        ...

    @abc.abstractmethod
    async def execute_sql(self, sql: str) -> dict[str, Any]:
        """Execute SQL text and return execution output."""
        ...
