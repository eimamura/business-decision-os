from __future__ import annotations

import json
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.agent.base import AgentBasedSpecialist
from packages.agent.control.control_agent import ControlAgent
from packages.agent.orchestrator import SpecialistResult, SpecialistTask
from packages.tools.base import ToolContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_task(
    intent_category: str = "supply_chain",
    instruction: str = "Analyze supply chain",
) -> SpecialistTask:
    return SpecialistTask(
        task_id=uuid.uuid4(),
        instruction=instruction,
        context_payload={"intent": {"category": intent_category}},
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
        output={"text": "recommendation text"},
        tool_calls_made=[uuid.uuid4()],
        status="completed",
    )


# ---------------------------------------------------------------------------
# T-302 — Pre-call search and context injection
# ---------------------------------------------------------------------------


async def test_control_agent_run_queries_decision_memory_before_llm_call() -> None:
    """search() is called with the task instruction as the semantic query (T-673), and when
    results are returned, the instruction passed to super().run() includes
    '## Past Decisions'."""
    task = _make_task()
    ctx = _make_ctx()

    captured_tasks: list[SpecialistTask] = []

    async def _fake_parent_run(
        self_inner: Any,
        t: SpecialistTask,
        c: ToolContext,
        agent_run_id: str = "",
    ) -> SpecialistResult:
        captured_tasks.append(t)
        return _stub_result(t)

    mock_search = AsyncMock(
        return_value=[{"content_json": '{"decision": "past_decision"}', "record_type": "decision"}]
    )
    mock_write = AsyncMock()

    with (
        patch(
            "packages.agent.control.control_agent.DecisionMemoryStore",
        ) as MockStore,
        patch(
            "packages.knowledge.skill_loader.SkillLoader.load",
            return_value=[],
        ),
        patch.object(AgentBasedSpecialist, "run", _fake_parent_run),
    ):
        instance = MockStore.return_value
        instance.search = mock_search
        instance.write = mock_write

        agent = ControlAgent(llm_client=MagicMock(), tool_registry=MagicMock())
        await agent.run(task, ctx)

    # search must have been called with the task instruction as the semantic query (T-673)
    mock_search.assert_called_once()
    call_args = mock_search.call_args
    query_arg: str = call_args[0][0]
    assert query_arg == task.instruction

    # instruction forwarded to super().run() must contain the Past Decisions block
    assert len(captured_tasks) == 1
    assert "## Past Decisions" in captured_tasks[0].instruction


async def test_control_agent_run_no_past_decisions_when_search_returns_empty() -> None:
    """When search returns [], the instruction must NOT contain '## Past Decisions'."""
    task = _make_task(instruction="Analyze supply chain")
    ctx = _make_ctx()

    captured_tasks: list[SpecialistTask] = []

    async def _fake_parent_run(
        self_inner: Any,
        t: SpecialistTask,
        c: ToolContext,
        agent_run_id: str = "",
    ) -> SpecialistResult:
        captured_tasks.append(t)
        return _stub_result(t)

    mock_search = AsyncMock(return_value=[])
    mock_write = AsyncMock()

    with (
        patch(
            "packages.agent.control.control_agent.DecisionMemoryStore",
        ) as MockStore,
        patch(
            "packages.knowledge.skill_loader.SkillLoader.load",
            return_value=[],
        ),
        patch.object(AgentBasedSpecialist, "run", _fake_parent_run),
    ):
        instance = MockStore.return_value
        instance.search = mock_search
        instance.write = mock_write

        agent = ControlAgent(llm_client=MagicMock(), tool_registry=MagicMock())
        await agent.run(task, ctx)

    assert len(captured_tasks) == 1
    assert "## Past Decisions" not in captured_tasks[0].instruction


async def test_control_agent_run_continues_when_memory_search_fails() -> None:
    """A RuntimeError from search must not propagate; super().run() must still be called."""
    task = _make_task()
    ctx = _make_ctx()

    parent_run_called = False

    async def _fake_parent_run(
        self_inner: Any,
        t: SpecialistTask,
        c: ToolContext,
        agent_run_id: str = "",
    ) -> SpecialistResult:
        nonlocal parent_run_called
        parent_run_called = True
        return _stub_result(t)

    mock_search = AsyncMock(side_effect=RuntimeError("DB error"))
    mock_write = AsyncMock()

    with (
        patch(
            "packages.agent.control.control_agent.DecisionMemoryStore",
        ) as MockStore,
        patch(
            "packages.knowledge.skill_loader.SkillLoader.load",
            return_value=[],
        ),
        patch.object(AgentBasedSpecialist, "run", _fake_parent_run),
    ):
        instance = MockStore.return_value
        instance.search = mock_search
        instance.write = mock_write

        agent = ControlAgent(llm_client=MagicMock(), tool_registry=MagicMock())
        await agent.run(task, ctx)  # must not raise

    assert parent_run_called


# ---------------------------------------------------------------------------
# T-303 — Post-call write and failure write
# ---------------------------------------------------------------------------


async def test_control_agent_run_writes_decision_record_on_success() -> None:
    """After a successful super().run(), write() must be called with record_type='decision'."""
    task = _make_task()
    ctx = _make_ctx()

    async def _fake_parent_run(
        self_inner: Any,
        t: SpecialistTask,
        c: ToolContext,
        agent_run_id: str = "",
    ) -> SpecialistResult:
        return _stub_result(t)

    mock_search = AsyncMock(return_value=[])
    mock_write = AsyncMock()

    with (
        patch(
            "packages.agent.control.control_agent.DecisionMemoryStore",
        ) as MockStore,
        patch(
            "packages.knowledge.skill_loader.SkillLoader.load",
            return_value=[],
        ),
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


async def test_control_agent_run_writes_failure_record_on_exception() -> None:
    """When super().run() raises, write() must be called with record_type='failure'
    and error_type set to the exception class name."""
    task = _make_task()
    ctx = _make_ctx()

    async def _fake_parent_run(
        self_inner: Any,
        t: SpecialistTask,
        c: ToolContext,
        agent_run_id: str = "",
    ) -> SpecialistResult:
        raise RuntimeError("agent error")

    mock_search = AsyncMock(return_value=[])
    mock_write = AsyncMock()

    with (
        patch(
            "packages.agent.control.control_agent.DecisionMemoryStore",
        ) as MockStore,
        patch(
            "packages.knowledge.skill_loader.SkillLoader.load",
            return_value=[],
        ),
        patch.object(AgentBasedSpecialist, "run", _fake_parent_run),
    ):
        instance = MockStore.return_value
        instance.search = mock_search
        instance.write = mock_write

        agent = ControlAgent(llm_client=MagicMock(), tool_registry=MagicMock())
        with pytest.raises(RuntimeError):
            await agent.run(task, ctx)

    mock_write.assert_called_once()
    write_payload: dict[str, Any] = mock_write.call_args[0][0]
    assert write_payload["record_type"] == "failure"
    content = write_payload["content_json"]
    assert content["error_type"] == "RuntimeError"


async def test_control_agent_run_reraises_original_exception_even_if_memory_write_fails() -> None:
    """If super().run() raises ValueError and write() also raises RuntimeError,
    the original ValueError must be re-raised (not the memory write exception)."""
    task = _make_task()
    ctx = _make_ctx()

    async def _fake_parent_run(
        self_inner: Any,
        t: SpecialistTask,
        c: ToolContext,
        agent_run_id: str = "",
    ) -> SpecialistResult:
        raise ValueError("agent error")

    mock_search = AsyncMock(return_value=[])
    mock_write = AsyncMock(side_effect=RuntimeError("memory write failed"))

    with (
        patch(
            "packages.agent.control.control_agent.DecisionMemoryStore",
        ) as MockStore,
        patch(
            "packages.knowledge.skill_loader.SkillLoader.load",
            return_value=[],
        ),
        patch.object(AgentBasedSpecialist, "run", _fake_parent_run),
    ):
        instance = MockStore.return_value
        instance.search = mock_search
        instance.write = mock_write

        agent = ControlAgent(llm_client=MagicMock(), tool_registry=MagicMock())
        with pytest.raises(ValueError, match="agent error"):
            await agent.run(task, ctx)
