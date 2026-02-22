"""
AADAP — Centralized Exception Taxonomy
=======================================
Hybrid exception hierarchy with category-based classes and severity property.

Design decisions:
- Category-based exceptions (OrchestratorError, AgentLifecycleError, etc.)
- Severity property on each exception for error classification
- Technical details only: error code, context, identifiers for tracing
- Follows existing exception patterns from approval_engine.py, agents/base.py

Usage:
    from aadap.core.exceptions import AADAPError, OrchestratorError, ErrorSeverity

    raise OrchestratorError(
        "Graph execution failed",
        task_id="abc-123",
        correlation_id="req-456"
    )
"""

from __future__ import annotations

from enum import StrEnum


class ErrorSeverity(StrEnum):
    """
    Error severity levels for exception classification.

    Matches RiskLevel pattern from aadap.safety.static_analysis:
    LOW < MEDIUM < HIGH < CRITICAL
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AADAPError(Exception):
    """
    Base exception for all AADAP-specific errors.

    All AADAP exceptions inherit from this base class, providing:
    - severity: Classification for error handling/routing
    - error_code: Unique identifier for programmatic handling
    - Tracing identifiers: task_id, agent_id, correlation_id

    Technical details only — no user-facing messages.
    """

    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    error_code: str = "AADAP_ERROR"

    def __init__(
        self,
        message: str,
        *,
        task_id: str | None = None,
        agent_id: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        self.task_id = task_id
        self.agent_id = agent_id
        self.correlation_id = correlation_id
        super().__init__(message)

    def __repr__(self) -> str:
        parts = [
            f"{self.__class__.__name__}(",
            f"error_code={self.error_code!r}, ",
            f"severity={self.severity.value!r}",
        ]
        if self.task_id:
            parts.append(f", task_id={self.task_id!r}")
        if self.agent_id:
            parts.append(f", agent_id={self.agent_id!r}")
        if self.correlation_id:
            parts.append(f", correlation_id={self.correlation_id!r}")
        parts.append(")")
        return "".join(parts)


# ── Orchestrator Exceptions ───────────────────────────────────────────────


class OrchestratorError(AADAPError):
    """Errors in the orchestration layer (graph execution, state management)."""

    error_code = "ORCHESTRATOR_ERROR"


class GraphExecutionError(OrchestratorError):
    """Raised when graph execution fails during task processing."""

    severity = ErrorSeverity.HIGH
    error_code = "GRAPH_EXECUTION_ERROR"


class RoutingError(OrchestratorError):
    """Raised when task routing to agents fails."""

    severity = ErrorSeverity.MEDIUM
    error_code = "ROUTING_ERROR"


# ── Agent Lifecycle Exceptions ────────────────────────────────────────────


class AgentLifecycleError(AADAPError):
    """Errors in agent lifecycle management (initialization, execution, cleanup)."""

    error_code = "AGENT_LIFECYCLE_ERROR"


class AgentInitializationError(AgentLifecycleError):
    """Raised when agent initialization fails."""

    severity = ErrorSeverity.HIGH
    error_code = "AGENT_INITIALIZATION_ERROR"


class AgentExecutionError(AgentLifecycleError):
    """Raised when agent execution fails during task processing."""

    severity = ErrorSeverity.HIGH
    error_code = "AGENT_EXECUTION_ERROR"


# ── Integration Exceptions ────────────────────────────────────────────────


class IntegrationError(AADAPError):
    """Errors in external system integrations (Databricks, Fabric, LLMs)."""

    error_code = "INTEGRATION_ERROR"


class PlatformConnectionError(IntegrationError):
    """Raised when connection to external platform fails."""

    severity = ErrorSeverity.HIGH
    error_code = "PLATFORM_CONNECTION_ERROR"


class LLMError(IntegrationError):
    """Raised when LLM API call fails."""

    severity = ErrorSeverity.MEDIUM
    error_code = "LLM_ERROR"


# ── Execution Exceptions ──────────────────────────────────────────────────


class ExecutionError(AADAPError):
    """Errors during code execution (validation, deployment, runtime)."""

    error_code = "EXECUTION_ERROR"


class ValidationFailedError(ExecutionError):
    """Raised when code validation fails."""

    severity = ErrorSeverity.MEDIUM
    error_code = "VALIDATION_FAILED_ERROR"


class DeploymentError(ExecutionError):
    """Raised when deployment to environment fails."""

    severity = ErrorSeverity.HIGH
    error_code = "DEPLOYMENT_ERROR"


# ── Configuration Exceptions ──────────────────────────────────────────────


class ConfigurationError(AADAPError):
    """Errors in configuration (missing settings, invalid values)."""

    severity = ErrorSeverity.HIGH
    error_code = "CONFIGURATION_ERROR"


class MissingConfigurationError(ConfigurationError):
    """Raised when required configuration is missing."""

    error_code = "MISSING_CONFIGURATION_ERROR"


class InvalidConfigurationError(ConfigurationError):
    """Raised when configuration value is invalid."""

    error_code = "INVALID_CONFIGURATION_ERROR"
