from __future__ import annotations

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


def _make_task(intent_category: str, instruction: str = "Analyze supply chain") -> SpecialistTask:
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
        output={},
        tool_calls_made=[],
        status="completed",
    )


# ---------------------------------------------------------------------------
# T-288 — ControlAgent context builder unit tests
# ---------------------------------------------------------------------------


async def test_control_agent_run_injects_skill_block_when_skills_exist() -> None:
    """Skills returned by SkillLoader are prepended to task.instruction."""
    task = _make_task("supply_chain", instruction="Analyze supply chain")
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

    with (
        patch(
            "packages.knowledge.skill_loader.SkillLoader.load",
            return_value=["SKILL_CONTENT"],
        ),
        patch.object(AgentBasedSpecialist, "run", _fake_parent_run),
    ):
        agent = ControlAgent(llm_client=MagicMock(), tool_registry=MagicMock())
        await agent.run(task, ctx)

    assert len(captured_tasks) == 1
    mutated = captured_tasks[0]
    assert "## Analysis Procedures" in mutated.instruction
    assert "SKILL_CONTENT" in mutated.instruction


async def test_control_agent_run_no_skill_injection_when_empty() -> None:
    """When SkillLoader returns an empty list, instruction must be unchanged."""
    original_instruction = "Analyze supply chain"
    task = _make_task("supply_chain", instruction=original_instruction)
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

    with (
        patch(
            "packages.knowledge.skill_loader.SkillLoader.load",
            return_value=[],
        ),
        patch.object(AgentBasedSpecialist, "run", _fake_parent_run),
    ):
        agent = ControlAgent(llm_client=MagicMock(), tool_registry=MagicMock())
        await agent.run(task, ctx)

    assert len(captured_tasks) == 1
    assert captured_tasks[0].instruction == original_instruction


async def test_control_agent_run_no_skill_injection_for_chat_intent() -> None:
    """Chat intent maps to zero skills; instruction must pass through unchanged."""
    original_instruction = "Just say hello"
    task = _make_task("chat", instruction=original_instruction)
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

    with patch.object(AgentBasedSpecialist, "run", _fake_parent_run):
        agent = ControlAgent(llm_client=MagicMock(), tool_registry=MagicMock())
        await agent.run(task, ctx)

    assert len(captured_tasks) == 1
    assert captured_tasks[0].instruction == original_instruction
