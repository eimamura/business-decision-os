from __future__ import annotations

from uuid import uuid4

from packages.tools.base import ToolContext, ToolRegistry, ToolResult


class _FakeTool:
    name = "fake_tool"
    description = "A fake tool for testing"
    input_schema: dict = {}
    output_schema: dict = {}
    requires_approval = False

    async def handle(self, input: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(output={}, audit_payload={})


def test_register_and_get():
    registry = ToolRegistry()
    tool = _FakeTool()
    registry.register(tool)
    assert registry.get("fake_tool") is tool


def test_get_missing_returns_none():
    registry = ToolRegistry()
    assert registry.get("nonexistent") is None


def test_list_for_role_orchestrator_returns_empty():
    registry = ToolRegistry()
    tool = _FakeTool()
    registry.register(tool)
    tools = registry.list_for_role("orchestrator")
    assert tools == []


def test_list_for_role_data_engineer_filters_to_allowlist():
    registry = ToolRegistry()
    registry.register(_FakeTool())
    tools = registry.list_for_role("data_engineer")
    names = {t.name for t in tools}
    assert "fake_tool" not in names


def test_tool_context_schema():
    ctx = ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="evaluator",
        actor="test-actor",
        correlation_id=uuid4(),
    )
    assert ctx.specialist_role == "evaluator"
