from __future__ import annotations

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
# T-338 — LongTermMemoryStore integration in ControlAgent
# ---------------------------------------------------------------------------


async def test_domain_knowledge_injected_when_records_returned() -> None:
    """When LongTermMemoryStore.search returns records, the instruction forwarded
    to super().run() must contain '## Domain Knowledge'."""
    task = _make_task(intent_category="supply_chain")
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

    mock_ltm_search = AsyncMock(
        return_value=[{"content": "KPI threshold: DOS < 7 is critical"}]
    )

    mock_decision_search = AsyncMock(return_value=[])
    mock_decision_write = AsyncMock()

    with (
        patch(
            "packages.agent.control.control_agent.LongTermMemoryStore",
        ) as MockLTMStore,
        patch(
            "packages.agent.control.control_agent.DecisionMemoryStore",
        ) as MockDecisionStore,
        patch(
            "packages.knowledge.skill_loader.SkillLoader.load",
            return_value=[],
        ),
        patch.object(AgentBasedSpecialist, "run", _fake_parent_run),
    ):
        ltm_instance = MockLTMStore.return_value
        ltm_instance.search = mock_ltm_search

        decision_instance = MockDecisionStore.return_value
        decision_instance.search = mock_decision_search
        decision_instance.write = mock_decision_write

        agent = ControlAgent(llm_client=MagicMock(), tool_registry=MagicMock())
        await agent.run(task, ctx)

    assert len(captured_tasks) == 1
    assert "Domain Knowledge" in captured_tasks[0].instruction
    assert "KPI threshold: DOS < 7 is critical" in captured_tasks[0].instruction


async def test_domain_knowledge_search_failure_does_not_abort() -> None:
    """When LongTermMemoryStore.search raises RuntimeError, ControlAgent must not
    raise and must still call super().run()."""
    task = _make_task(intent_category="supply_chain")
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

    mock_ltm_search = AsyncMock(side_effect=RuntimeError("db error"))

    mock_decision_search = AsyncMock(return_value=[])
    mock_decision_write = AsyncMock()

    with (
        patch(
            "packages.agent.control.control_agent.LongTermMemoryStore",
        ) as MockLTMStore,
        patch(
            "packages.agent.control.control_agent.DecisionMemoryStore",
        ) as MockDecisionStore,
        patch(
            "packages.knowledge.skill_loader.SkillLoader.load",
            return_value=[],
        ),
        patch.object(AgentBasedSpecialist, "run", _fake_parent_run),
    ):
        ltm_instance = MockLTMStore.return_value
        ltm_instance.search = mock_ltm_search

        decision_instance = MockDecisionStore.return_value
        decision_instance.search = mock_decision_search
        decision_instance.write = mock_decision_write

        agent = ControlAgent(llm_client=MagicMock(), tool_registry=MagicMock())
        await agent.run(task, ctx)  # must not raise

    assert parent_run_called
