from __future__ import annotations

from typing import Any

from packages.tools.base import ToolContext, ToolRegistry, ToolResult


# ---------------------------------------------------------------------------
# Minimal fake tools
# ---------------------------------------------------------------------------

class _ReadOnlyTool:
    name = "ro_tool"
    description = "read-only"
    input_schema: dict[str, Any] = {}
    output_schema: dict[str, Any] = {}
    requires_approval = False
    safety_level = "read_only"

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        return ToolResult(output={}, audit_payload={})


class _WriteTool:
    name = "write_tool"
    description = "write"
    input_schema: dict[str, Any] = {}
    output_schema: dict[str, Any] = {}
    requires_approval = False
    safety_level = "write"

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        return ToolResult(output={}, audit_payload={})


class _HitlTool:
    name = "hitl_tool"
    description = "hitl"
    input_schema: dict[str, Any] = {}
    output_schema: dict[str, Any] = {}
    requires_approval = True
    safety_level = "hitl"

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        return ToolResult(output={}, audit_payload={})


def _make_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(_ReadOnlyTool())
    registry.register(_WriteTool())
    registry.register(_HitlTool())
    return registry


def _all_tools(registry: ToolRegistry) -> list[Any]:
    return list(registry._tools.values())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_analyst_gets_only_read_only_tools() -> None:
    registry = _make_registry()
    result = registry.filter_for_user_role("analyst", _all_tools(registry))
    names = {t.name for t in result}
    assert names == {"ro_tool"}


def test_manager_gets_read_only_and_hitl_tools() -> None:
    registry = _make_registry()
    result = registry.filter_for_user_role("manager", _all_tools(registry))
    names = {t.name for t in result}
    assert names == {"ro_tool", "hitl_tool"}


def test_admin_gets_all_tools() -> None:
    registry = _make_registry()
    result = registry.filter_for_user_role("admin", _all_tools(registry))
    names = {t.name for t in result}
    assert names == {"ro_tool", "write_tool", "hitl_tool"}


def test_unknown_role_falls_back_to_analyst() -> None:
    registry = _make_registry()
    result = registry.filter_for_user_role("superuser", _all_tools(registry))
    names = {t.name for t in result}
    assert names == {"ro_tool"}
