from __future__ import annotations

"""P43-B-01 pipeline tests — T-305, T-306, T-307, T-305b.

These tests validate the ControlAgent context-building pipeline for supply_chain
intent without making real LLM calls.  They use the pattern established in
test_control_agent_skill_injection.py: patch AgentBasedSpecialist.run to capture
the SpecialistTask that ControlAgent forwards to the base runtime, then assert
that the correct Skill content has been injected into the instruction.

No @pytest.mark.asyncio — asyncio_mode = "auto" is set globally in conftest.
"""

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from packages.agent.base import AgentBasedSpecialist
from packages.agent.control.control_agent import ControlAgent
from packages.agent.orchestrator import SpecialistResult, SpecialistTask
from packages.tools.base import ToolContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_supply_chain_task(
    instruction: str = "What are today's supply chain exceptions?",
) -> SpecialistTask:
    return SpecialistTask(
        task_id=uuid.uuid4(),
        instruction=instruction,
        context_payload={
            "intent": {"category": "supply_chain"},
            "session_id": str(uuid.uuid4()),
        },
        allowed_tools=[],
    )


def _make_ctx() -> ToolContext:
    return ToolContext(
        session_id=uuid.uuid4(),
        agent_step_id=uuid.uuid4(),
        specialist_role="control",
        actor="test",
        correlation_id=uuid.uuid4(),
    )


def _stub_result(task: SpecialistTask) -> SpecialistResult:
    return SpecialistResult(
        task_id=task.task_id,
        output={"text": "stub recommendation"},
        tool_calls_made=[uuid.uuid4()],
        status="completed",
    )


# ---------------------------------------------------------------------------
# Shared patch helper — intercept AgentBasedSpecialist.run and capture the task
# ---------------------------------------------------------------------------


def _make_fake_parent_run(captured: list[SpecialistTask]) -> Any:
    """Return an unbound async method compatible with patch.object on AgentBasedSpecialist."""

    async def _fake_parent_run(
        self_inner: Any,
        t: SpecialistTask,
        c: ToolContext,
        agent_run_id: str = "",
    ) -> SpecialistResult:
        captured.append(t)
        return _stub_result(t)

    return _fake_parent_run


# ---------------------------------------------------------------------------
# T-305 — exception_detection Skill injected for supply_chain intent
# ---------------------------------------------------------------------------


async def test_control_agent_injects_exception_detection_skill_for_supply_chain_intent() -> None:
    """ControlAgent must inject exception_detection skill content for supply_chain intent.

    SkillLoader loads the real skill files from disk (no mock), so the assertion
    verifies that the actual file content reaches the instruction forwarded to
    super().run().
    """
    task = _make_supply_chain_task("What are today's exceptions?")
    ctx = _make_ctx()

    captured: list[SpecialistTask] = []
    mock_search = AsyncMock(return_value=[])
    mock_write = AsyncMock()

    with (
        patch(
            "packages.agent.control.control_agent.DecisionMemoryStore",
        ) as MockStore,
        patch.object(AgentBasedSpecialist, "run", _make_fake_parent_run(captured)),
    ):
        instance = MockStore.return_value
        instance.search = mock_search
        instance.write = mock_write

        agent = ControlAgent(llm_client=MagicMock(), tool_registry=MagicMock())
        await agent.run(task, ctx)

    assert len(captured) == 1
    injected_instruction = captured[0].instruction
    assert "## Analysis Procedures" in injected_instruction
    assert "exception_detection" in injected_instruction


# ---------------------------------------------------------------------------
# T-306 — stockout_risk_analysis Skill injected for supply_chain intent
# ---------------------------------------------------------------------------


async def test_control_agent_injects_stockout_skill_for_supply_chain_intent() -> None:
    """ControlAgent must inject stockout_risk_analysis skill content for supply_chain intent."""
    task = _make_supply_chain_task("Which products are at stockout risk this week?")
    ctx = _make_ctx()

    captured: list[SpecialistTask] = []
    mock_search = AsyncMock(return_value=[])
    mock_write = AsyncMock()

    with (
        patch(
            "packages.agent.control.control_agent.DecisionMemoryStore",
        ) as MockStore,
        patch.object(AgentBasedSpecialist, "run", _make_fake_parent_run(captured)),
    ):
        instance = MockStore.return_value
        instance.search = mock_search
        instance.write = mock_write

        agent = ControlAgent(llm_client=MagicMock(), tool_registry=MagicMock())
        await agent.run(task, ctx)

    assert len(captured) == 1
    injected_instruction = captured[0].instruction
    assert "## Analysis Procedures" in injected_instruction
    assert "stockout_risk_analysis" in injected_instruction


# ---------------------------------------------------------------------------
# T-307 — shipment_delay_root_cause Skill injected for supply_chain intent
# ---------------------------------------------------------------------------


async def test_control_agent_injects_shipment_delay_skill_for_supply_chain_intent() -> None:
    """ControlAgent must inject shipment_delay_root_cause skill content for supply_chain intent."""
    task = _make_supply_chain_task("Why is order #X delayed?")
    ctx = _make_ctx()

    captured: list[SpecialistTask] = []
    mock_search = AsyncMock(return_value=[])
    mock_write = AsyncMock()

    with (
        patch(
            "packages.agent.control.control_agent.DecisionMemoryStore",
        ) as MockStore,
        patch.object(AgentBasedSpecialist, "run", _make_fake_parent_run(captured)),
    ):
        instance = MockStore.return_value
        instance.search = mock_search
        instance.write = mock_write

        agent = ControlAgent(llm_client=MagicMock(), tool_registry=MagicMock())
        await agent.run(task, ctx)

    assert len(captured) == 1
    injected_instruction = captured[0].instruction
    assert "## Analysis Procedures" in injected_instruction
    assert "shipment_delay_root_cause" in injected_instruction


# ---------------------------------------------------------------------------
# T-305b — DecisionMemory write called with record_type="decision" after run
# ---------------------------------------------------------------------------


async def test_control_agent_writes_decision_record_after_supply_chain_run() -> None:
    """After a successful run for supply_chain intent, write() must be called
    with record_type="decision"."""
    task = _make_supply_chain_task()
    ctx = _make_ctx()

    mock_search = AsyncMock(return_value=[])
    mock_write = AsyncMock()

    async def _fake_parent_run(
        self_inner: Any,
        t: SpecialistTask,
        c: ToolContext,
        agent_run_id: str = "",
    ) -> SpecialistResult:
        return _stub_result(t)

    with (
        patch(
            "packages.agent.control.control_agent.DecisionMemoryStore",
        ) as MockStore,
        patch.object(AgentBasedSpecialist, "run", _fake_parent_run),
    ):
        instance = MockStore.return_value
        instance.search = mock_search
        instance.write = mock_write

        agent = ControlAgent(llm_client=MagicMock(), tool_registry=MagicMock())
        await agent.run(task, ctx)

    mock_write.assert_called_once()
    write_payload: dict[str, Any] = mock_write.call_args[0][0]
    assert write_payload["record_type"] == "decision"


# ---------------------------------------------------------------------------
# Additional coverage — pipeline does not error for supply_chain intent
# ---------------------------------------------------------------------------


async def test_control_agent_pipeline_does_not_raise_for_supply_chain_intent() -> None:
    """The full pipeline must complete without exception for supply_chain intent."""
    task = _make_supply_chain_task()
    ctx = _make_ctx()

    mock_search = AsyncMock(return_value=[])
    mock_write = AsyncMock()

    async def _fake_parent_run(
        self_inner: Any,
        t: SpecialistTask,
        c: ToolContext,
        agent_run_id: str = "",
    ) -> SpecialistResult:
        return _stub_result(t)

    with (
        patch(
            "packages.agent.control.control_agent.DecisionMemoryStore",
        ) as MockStore,
        patch.object(AgentBasedSpecialist, "run", _fake_parent_run),
    ):
        instance = MockStore.return_value
        instance.search = mock_search
        instance.write = mock_write

        agent = ControlAgent(llm_client=MagicMock(), tool_registry=MagicMock())
        result = await agent.run(task, ctx)  # must not raise

    assert result.status == "completed"


# ---------------------------------------------------------------------------
# All three MVP questions inject all three skills (comprehensive check)
# ---------------------------------------------------------------------------


async def test_control_agent_all_three_skills_injected_for_supply_chain() -> None:
    """For supply_chain intent with GENERIC ContextPack (no skill_keys override),
    the intent-level fallback must inject all three MVP skills:
    stockout_risk_analysis, exception_detection, and shipment_delay_root_cause.

    The instruction must NOT match any Q1–Q10 keyword so that ContextBuilder returns
    GENERIC_PACK (skill_keys=[]), causing _inject_skills() to fall back to the
    intent-level SkillLoader.load("supply_chain") path.
    """
    # "Provide a supply chain overview" matches no Q1–Q10 keywords → GENERIC_PACK.
    task = _make_supply_chain_task("Provide a supply chain overview and analysis.")
    ctx = _make_ctx()

    captured: list[SpecialistTask] = []
    mock_search = AsyncMock(return_value=[])
    mock_write = AsyncMock()

    with (
        patch(
            "packages.agent.control.control_agent.DecisionMemoryStore",
        ) as MockStore,
        patch.object(AgentBasedSpecialist, "run", _make_fake_parent_run(captured)),
    ):
        instance = MockStore.return_value
        instance.search = mock_search
        instance.write = mock_write

        agent = ControlAgent(llm_client=MagicMock(), tool_registry=MagicMock())
        await agent.run(task, ctx)

    assert len(captured) == 1
    injected_instruction = captured[0].instruction
    assert "stockout_risk_analysis" in injected_instruction
    assert "exception_detection" in injected_instruction
    assert "shipment_delay_root_cause" in injected_instruction


# ---------------------------------------------------------------------------
# P116 B-01 — _narrow_tools() unit tests
# ---------------------------------------------------------------------------


def test_narrow_tools_non_empty_list_sets_allowed_tools() -> None:
    """P116 B-01: _narrow_tools with a non-empty list must set task.allowed_tools
    to exactly that list.

    ControlAgent._narrow_tools() accepts a pre-filtered list (allowed_tools) and
    calls model_copy to update the task.  This replaces the previous behaviour that
    re-read _INTENT_TOOL_SUBSET internally.
    """
    task = _make_supply_chain_task()
    agent = ControlAgent(llm_client=MagicMock(), tool_registry=MagicMock())
    narrowed = ["list_stockout_risk", "nl_query"]
    result = agent._narrow_tools(task, narrowed)
    assert result.allowed_tools == narrowed


def test_narrow_tools_empty_list_leaves_allowed_tools_unchanged() -> None:
    """P116 B-01: _narrow_tools with an empty list must return the task unchanged.

    When allowed_tools is [] (e.g. unknown intent or no prohibition narrowing),
    _narrow_tools must fall back to the task's original allowed_tools without
    modification, preserving the full unrestricted tool set.
    """
    original_tools = ["nl_query", "list_today_exceptions"]
    task = SpecialistTask(
        task_id=uuid.uuid4(),
        instruction="What are today's supply chain exceptions?",
        context_payload={"intent": {"category": "supply_chain"}, "session_id": str(uuid.uuid4())},
        allowed_tools=original_tools,
    )
    agent = ControlAgent(llm_client=MagicMock(), tool_registry=MagicMock())
    result = agent._narrow_tools(task, [])
    assert result.allowed_tools == original_tools


# ---------------------------------------------------------------------------
# P117 B-02 — _inject_schema_context() unit tests (T-677)
# ---------------------------------------------------------------------------


def test_inject_schema_context_appends_to_instruction() -> None:
    """P117 B-02: when get_schema_context() returns a non-empty schema string,
    _inject_schema_context() must append the rendered schema block to task.instruction.

    render_schema_context() wraps _make_schema_example() which builds a correlated-subquery
    SQL example from the schema string.  We patch get_schema_context() to return a minimal
    but structurally valid schema that satisfies the four required tables so that
    _make_schema_example() produces a non-empty example string.
    """
    minimal_schema = (
        "sku_master(sku_id TEXT, sku_name TEXT)\n"
        "demand_history(sku_id TEXT, quantity NUMERIC)\n"
        "inventory_snapshot(sku_id TEXT, on_hand NUMERIC)\n"
        "supply_orders(sku_id TEXT, quantity NUMERIC, status TEXT, expected_arrival DATE)"
    )

    task = _make_supply_chain_task("Which products face supply shortages?")
    agent = ControlAgent(llm_client=MagicMock(), tool_registry=MagicMock())

    with patch(
        "packages.agent.control.control_agent.get_schema_context",
        return_value=minimal_schema,
    ):
        result = agent._inject_schema_context(task)

    assert task.instruction in result.instruction
    assert len(result.instruction) > len(task.instruction)
    # The schema example embeds "sku_master" from the schema string.
    assert "sku_master" in result.instruction


def test_inject_schema_context_empty_schema_noop() -> None:
    """P117 B-02: when get_schema_context() returns an empty string,
    _inject_schema_context() must return the task unchanged (fail-open).
    """
    task = _make_supply_chain_task("Which products face supply shortages?")
    agent = ControlAgent(llm_client=MagicMock(), tool_registry=MagicMock())

    with patch(
        "packages.agent.control.control_agent.get_schema_context",
        return_value="",
    ):
        result = agent._inject_schema_context(task)

    assert result.instruction == task.instruction
