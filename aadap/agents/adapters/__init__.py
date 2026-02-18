"""AADAP platform adapters."""

from aadap.agents.adapters.base import (
    PlatformAdapter,
    PlatformAdapterError,
    PlatformCapabilityError,
    PlatformExecutionError,
)
from aadap.agents.adapters.databricks_adapter import DatabricksAdapter
from aadap.agents.adapters.fabric_adapter import FabricAdapter

__all__ = [
    "DatabricksAdapter",
    "FabricAdapter",
    "PlatformAdapter",
    "PlatformAdapterError",
    "PlatformCapabilityError",
    "PlatformExecutionError",
]
