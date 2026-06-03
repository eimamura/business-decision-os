from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from packages.tools.base import ToolContext, ToolRegistry, ToolResult


# ---------------------------------------------------------------------------
# Minimal fake tools covering all three safety levels
# ---------------------------------------------------------------------------

class _ReadOnlyTool:
    name = "fake_read_only"
    description = "Fake read-only tool"
    input_schema: dict[str, Any] = {}
    output_schema: dict[str, Any] = {}
    safety_level = "read_only"

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        return ToolResult(output={}, audit_payload={})


class _WriteTool:
    name = "fake_write"
    description = "Fake write tool"
    input_schema: dict[str, Any] = {}
    output_schema: dict[str, Any] = {}
    safety_level = "write"

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        return ToolResult(output={}, audit_payload={})


class _HitlTool:
    name = "fake_hitl"
    description = "Fake HITL tool"
    input_schema: dict[str, Any] = {}
    output_schema: dict[str, Any] = {}
    safety_level = "hitl"

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        return ToolResult(output={}, audit_payload={})


def _make_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(_ReadOnlyTool())
    registry.register(_WriteTool())
    registry.register(_HitlTool())
    return registry


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

VALID_SAFETY_LEVELS = {"read_only", "write", "hitl"}


def test_all_registered_tools_have_safety_level() -> None:
    """Every tool in the default registry must declare a valid safety_level."""
    from packages.tools import create_tool_registry

    registry = create_tool_registry()
    # Bypass the role allowlist by inspecting internal dict directly
    tools = list(registry._tools.values())
    assert tools, "Registry must contain at least one tool"
    for tool in tools:
        assert hasattr(tool, "safety_level"), (
            f"{tool.name!r} is missing safety_level"
        )
        assert tool.safety_level in VALID_SAFETY_LEVELS, (
            f"{tool.name!r} has invalid safety_level {tool.safety_level!r}"
        )


def test_list_read_only_returns_only_read_only_tools() -> None:
    registry = _make_registry()
    read_only = registry.list_read_only()
    assert all(t.safety_level == "read_only" for t in read_only)
    names = {t.name for t in read_only}
    assert "fake_read_only" in names
    assert "fake_write" not in names
    assert "fake_hitl" not in names


def test_list_hitl_tools_returns_only_hitl_tools() -> None:
    registry = _make_registry()
    hitl = registry.list_hitl_tools()
    assert all(t.safety_level == "hitl" for t in hitl)
    names = {t.name for t in hitl}
    assert "fake_hitl" in names
    assert "fake_read_only" not in names
    assert "fake_write" not in names


def test_tool_context_defaults_user_role_to_analyst() -> None:
    ctx = ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="data_engineer",
        actor="test",
        correlation_id=uuid4(),
    )
    assert ctx.user_role == "analyst"


def test_tool_context_accepts_custom_user_role() -> None:
    ctx = ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="data_engineer",
        actor="test",
        correlation_id=uuid4(),
        user_role="manager",
    )
    assert ctx.user_role == "manager"


@pytest.mark.parametrize("tool_name,expected_level", [
    ("sql_query", "read_only"),
    ("nl_query", "read_only"),
    ("data_catalog_search", "read_only"),
    ("table_schema_reader", "read_only"),
    ("data_quality_checker", "read_only"),
    ("evaluate_candidates", "read_only"),
    ("forecast", "write"),
    ("train_forecast", "write"),
    ("simulate_inventory", "write"),
    ("optimize_replenishment", "write"),
    ("write_audit_log", "write"),
    ("request_approval", "hitl"),
])
def test_concrete_tool_safety_levels(tool_name: str, expected_level: str) -> None:
    """Each concrete tool must have the expected safety_level classification."""
    from packages.tools import create_tool_registry

    registry = create_tool_registry()
    tool = registry.get(tool_name)
    assert tool is not None, f"Tool {tool_name!r} not found in registry"
    assert tool.safety_level == expected_level, (
        f"{tool_name!r} safety_level is {tool.safety_level!r}, expected {expected_level!r}"
    )
