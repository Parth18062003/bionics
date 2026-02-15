"""
AADAP — Tool Registry & Permission Enforcement
===================================================
Central registry for all tools available to agents, with explicit
permission checks before execution.

Architecture layer: L3 (Integration) / L4 (Agent Layer).
Enforces:
- Tool access must be explicitly granted (PHASE_3_CONTRACTS.md)
- Agents are untrusted workers (ARCHITECTURE.md §Trust Boundaries)

Usage:
    registry = ToolRegistry()
    registry.register(ToolDefinition(name="read_file", ...))
    registry.check_permission({"read_file"}, "read_file")  # OK
    registry.check_permission({"read_file"}, "delete_file")  # raises
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from aadap.core.logging import get_logger

logger = get_logger(__name__)


# ── Exceptions ──────────────────────────────────────────────────────────


class ToolNotFoundError(Exception):
    """Raised when a requested tool is not registered."""

    def __init__(self, tool_name: str) -> None:
        self.tool_name = tool_name
        super().__init__(f"Tool '{tool_name}' is not registered.")


class ToolPermissionDeniedError(Exception):
    """Raised when an agent attempts to use a tool it has not been granted."""

    def __init__(self, tool_name: str, agent_id: str | None = None) -> None:
        self.tool_name = tool_name
        self.agent_id = agent_id
        msg = f"Permission denied: tool '{tool_name}' is not in the agent's allowed set."
        if agent_id:
            msg = f"Permission denied: agent '{agent_id}' may not use tool '{tool_name}'."
        super().__init__(msg)


# ── Tool Definition ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class ToolDefinition:
    """
    Descriptor for a registered tool.

    Parameters
    ----------
    name
        Unique tool identifier (e.g. ``read_file``, ``execute_sql``).
    description
        Human-readable description of what the tool does.
    handler
        Callable that implements the tool's logic.
    requires_approval
        Whether using this tool requires human approval (INV-01).
    is_destructive
        Whether this tool performs destructive operations.
    """

    name: str
    description: str
    handler: Callable[..., Any]
    requires_approval: bool = False
    is_destructive: bool = False


# ── Tool Registry ───────────────────────────────────────────────────────


class ToolRegistry:
    """
    Central, authoritative tool registry.

    All tools must be registered here before agents can use them.
    Permission enforcement is mandatory — no agent may call a tool
    that is not in its explicit ``allowed_tools`` set.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        """
        Register a tool.

        Raises ``ValueError`` if a tool with the same name already exists.
        """
        if tool.name in self._tools:
            raise ValueError(
                f"Tool '{tool.name}' is already registered. "
                f"Unregister it first to replace."
            )
        self._tools[tool.name] = tool
        logger.info("tool.registered", tool_name=tool.name)

    def unregister(self, name: str) -> None:
        """
        Remove a tool from the registry.

        Raises ``ToolNotFoundError`` if the tool is not registered.
        """
        if name not in self._tools:
            raise ToolNotFoundError(name)
        del self._tools[name]
        logger.info("tool.unregistered", tool_name=name)

    def get(self, name: str) -> ToolDefinition:
        """
        Retrieve a tool definition by name.

        Raises ``ToolNotFoundError`` if not found.
        """
        tool = self._tools.get(name)
        if tool is None:
            raise ToolNotFoundError(name)
        return tool

    def list_tools(self) -> list[ToolDefinition]:
        """Return all registered tools."""
        return list(self._tools.values())

    @staticmethod
    def check_permission(
        allowed_tools: set[str],
        tool_name: str,
        agent_id: str | None = None,
    ) -> bool:
        """
        Verify an agent is permitted to use the named tool.

        Parameters
        ----------
        allowed_tools
            The set of tool names explicitly granted to the agent.
        tool_name
            The tool being requested.
        agent_id
            Optional agent identifier for error reporting.

        Returns
        -------
        bool
            ``True`` if permitted.

        Raises
        ------
        ToolPermissionDeniedError
            If the tool is not in the agent's allowed set.
        """
        if tool_name not in allowed_tools:
            logger.warning(
                "tool.permission_denied",
                tool_name=tool_name,
                agent_id=agent_id,
                allowed_tools=sorted(allowed_tools),
            )
            raise ToolPermissionDeniedError(tool_name, agent_id)
        return True

    def execute_tool(
        self,
        allowed_tools: set[str],
        tool_name: str,
        agent_id: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """
        Check permission, then execute the tool's handler.

        Parameters
        ----------
        allowed_tools
            The agent's granted tool set.
        tool_name
            Tool to execute.
        agent_id
            Optional agent identifier for logging / error messages.
        **kwargs
            Arguments forwarded to the tool handler.

        Raises
        ------
        ToolPermissionDeniedError
            If the agent may not use this tool.
        ToolNotFoundError
            If the tool is not registered.
        """
        self.check_permission(allowed_tools, tool_name, agent_id)
        tool = self.get(tool_name)

        logger.info(
            "tool.executing",
            tool_name=tool_name,
            agent_id=agent_id,
            requires_approval=tool.requires_approval,
        )
        return tool.handler(**kwargs)
