"""
AADAP — Tool Registry & Permission Tests
============================================
Validates:
- Tool registration and retrieval
- ToolNotFoundError for unknown tools
- ToolPermissionDeniedError for forbidden tools
- Permission check passes for allowed tools
- execute_tool calls handler only when permitted
"""

from __future__ import annotations

import pytest

from aadap.agents.tools.registry import (
    ToolDefinition,
    ToolNotFoundError,
    ToolPermissionDeniedError,
    ToolRegistry,
)


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def registry() -> ToolRegistry:
    return ToolRegistry()


@pytest.fixture
def read_tool() -> ToolDefinition:
    return ToolDefinition(
        name="read_file",
        description="Read a file from the filesystem",
        handler=lambda path="": f"content of {path}",
    )


@pytest.fixture
def write_tool() -> ToolDefinition:
    return ToolDefinition(
        name="write_file",
        description="Write to a file",
        handler=lambda path="", content="": f"wrote {len(content)} chars to {path}",
        requires_approval=False,
    )


@pytest.fixture
def delete_tool() -> ToolDefinition:
    return ToolDefinition(
        name="delete_file",
        description="Delete a file",
        handler=lambda path="": f"deleted {path}",
        requires_approval=True,
        is_destructive=True,
    )


# ── Tests ────────────────────────────────────────────────────────────────


class TestToolRegistration:
    """Register, retrieve, unregister tools."""

    def test_register_and_get(
        self, registry: ToolRegistry, read_tool: ToolDefinition
    ):
        registry.register(read_tool)
        retrieved = registry.get("read_file")
        assert retrieved.name == "read_file"
        assert retrieved.description == read_tool.description

    def test_register_duplicate_raises(
        self, registry: ToolRegistry, read_tool: ToolDefinition
    ):
        registry.register(read_tool)
        with pytest.raises(ValueError, match="already registered"):
            registry.register(read_tool)

    def test_unregister(
        self, registry: ToolRegistry, read_tool: ToolDefinition
    ):
        registry.register(read_tool)
        registry.unregister("read_file")
        with pytest.raises(ToolNotFoundError):
            registry.get("read_file")

    def test_unregister_unknown_raises(self, registry: ToolRegistry):
        with pytest.raises(ToolNotFoundError):
            registry.unregister("nonexistent")

    def test_get_unknown_raises(self, registry: ToolRegistry):
        with pytest.raises(ToolNotFoundError, match="not registered"):
            registry.get("nonexistent")

    def test_list_tools(
        self,
        registry: ToolRegistry,
        read_tool: ToolDefinition,
        write_tool: ToolDefinition,
    ):
        registry.register(read_tool)
        registry.register(write_tool)
        tools = registry.list_tools()
        assert len(tools) == 2
        names = {t.name for t in tools}
        assert names == {"read_file", "write_file"}


class TestPermissionEnforcement:
    """Tool permission checks."""

    def test_permission_granted(self, registry: ToolRegistry):
        allowed = {"read_file", "write_file"}
        assert registry.check_permission(allowed, "read_file") is True

    def test_permission_denied(self, registry: ToolRegistry):
        allowed = {"read_file"}
        with pytest.raises(ToolPermissionDeniedError, match="delete_file"):
            registry.check_permission(allowed, "delete_file")

    def test_permission_denied_with_agent_id(self, registry: ToolRegistry):
        allowed = {"read_file"}
        with pytest.raises(ToolPermissionDeniedError, match="agent 'dev-1'"):
            registry.check_permission(allowed, "delete_file", agent_id="dev-1")

    def test_empty_allowed_set_denies_all(self, registry: ToolRegistry):
        with pytest.raises(ToolPermissionDeniedError):
            registry.check_permission(set(), "read_file")


class TestToolExecution:
    """execute_tool checks permission then calls handler."""

    def test_execute_allowed_tool(
        self, registry: ToolRegistry, read_tool: ToolDefinition
    ):
        registry.register(read_tool)
        result = registry.execute_tool(
            allowed_tools={"read_file"},
            tool_name="read_file",
            path="/test.txt",
        )
        assert result == "content of /test.txt"

    def test_execute_forbidden_tool_raises(
        self, registry: ToolRegistry, read_tool: ToolDefinition
    ):
        registry.register(read_tool)
        with pytest.raises(ToolPermissionDeniedError):
            registry.execute_tool(
                allowed_tools={"write_file"},
                tool_name="read_file",
            )

    def test_execute_unregistered_tool_raises(
        self, registry: ToolRegistry
    ):
        with pytest.raises(ToolPermissionDeniedError):
            registry.execute_tool(
                allowed_tools=set(),
                tool_name="nonexistent",
            )

    def test_destructive_tool_metadata(
        self, registry: ToolRegistry, delete_tool: ToolDefinition
    ):
        registry.register(delete_tool)
        tool = registry.get("delete_file")
        assert tool.is_destructive is True
        assert tool.requires_approval is True
