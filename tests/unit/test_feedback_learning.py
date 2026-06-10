"""Unit tests for P73 — Feedback Learning Loop (T-467).

ADR: docs/adr/2026-06-10-autonomy-loops.md §3

Scenarios covered:
  - set_latest_outcome: valid +1 outcome updates the latest decision row
    (mock asyncpg pool: SQL targets record_type='decision' with ORDER BY created_at DESC
    LIMIT 1 subquery; returns True when asyncpg result string is "UPDATE 1")
  - set_latest_outcome: returns False when asyncpg result string is "UPDATE 0"
  - set_latest_outcome: raises ValueError for outcome not in {1, -1}
  - feedback endpoint: store raising does NOT change the 204 response
  - ControlAgent Past Decisions block renders "[user feedback: positive]" when outcome=1
  - ControlAgent Past Decisions block renders "[user feedback: negative]" when outcome=-1
  - ControlAgent Past Decisions block omits annotation when outcome is NULL/None
  - _SYSTEM_PROMPT contains the negative-feedback-avoidance instruction
"""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.main import app
from packages.memory.decision import DecisionMemoryStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_pool(execute_result: str = "UPDATE 1") -> Any:
    """Return a mock asyncpg pool whose conn.execute() resolves to execute_result."""
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=execute_result)

    # asyncpg pool.acquire() is an async context manager
    mock_acquire = MagicMock()
    mock_acquire.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_acquire.__aexit__ = AsyncMock(return_value=None)

    mock_pool = MagicMock()
    mock_pool.acquire = MagicMock(return_value=mock_acquire)
    return mock_pool, mock_conn


# ---------------------------------------------------------------------------
# set_latest_outcome — SQL path
# ---------------------------------------------------------------------------


async def test_set_latest_outcome_positive_updates_row_returns_true() -> None:
    """set_latest_outcome(+1) executes an UPDATE with the correct subquery and returns
    True when asyncpg returns 'UPDATE 1'."""
    mock_pool, mock_conn = _make_mock_pool("UPDATE 1")
    store = DecisionMemoryStore(pool=mock_pool)

    session_id = str(uuid4())
    result = await store.set_latest_outcome(session_id, 1)

    assert result is True
    mock_conn.execute.assert_called_once()
    sql_call_args = mock_conn.execute.call_args
    sql = sql_call_args[0][0]

    # The UPDATE must target the latest decision row via the subquery
    assert "record_type = 'decision'" in sql, (
        "SQL must filter record_type='decision'"
    )
    assert "ORDER BY created_at DESC" in sql, (
        "SQL must order by created_at DESC to get the latest row"
    )
    assert "LIMIT 1" in sql, (
        "SQL must limit to 1 row (the latest)"
    )
    # The session_id and outcome values must be passed as parameters
    assert sql_call_args[0][1] == 1, (
        "First parameter must be outcome=1"
    )
    assert sql_call_args[0][2] == session_id, (
        "Second parameter must be the session_id"
    )


async def test_set_latest_outcome_negative_updates_row_returns_true() -> None:
    """set_latest_outcome(-1) with 'UPDATE 1' result returns True."""
    mock_pool, mock_conn = _make_mock_pool("UPDATE 1")
    store = DecisionMemoryStore(pool=mock_pool)

    result = await store.set_latest_outcome(str(uuid4()), -1)

    assert result is True
    sql_call_args = mock_conn.execute.call_args
    assert sql_call_args[0][1] == -1, "First parameter must be outcome=-1"


async def test_set_latest_outcome_no_decision_row_returns_false() -> None:
    """set_latest_outcome returns False when asyncpg returns 'UPDATE 0' (no row matched)."""
    mock_pool, _ = _make_mock_pool("UPDATE 0")
    store = DecisionMemoryStore(pool=mock_pool)

    result = await store.set_latest_outcome(str(uuid4()), 1)

    assert result is False


async def test_set_latest_outcome_invalid_outcome_raises_value_error() -> None:
    """set_latest_outcome raises ValueError for outcome values other than 1 or -1."""
    store = DecisionMemoryStore(pool=MagicMock())

    with pytest.raises(ValueError, match="outcome must be 1 or -1"):
        await store.set_latest_outcome(str(uuid4()), 0)

    with pytest.raises(ValueError, match="outcome must be 1 or -1"):
        await store.set_latest_outcome(str(uuid4()), 2)

    with pytest.raises(ValueError, match="outcome must be 1 or -1"):
        await store.set_latest_outcome(str(uuid4()), -2)


# ---------------------------------------------------------------------------
# feedback endpoint — store failure must not change 204 response
# ---------------------------------------------------------------------------


async def test_feedback_endpoint_204_when_store_raises() -> None:
    """PATCH /sessions/{id}/messages/{msg_id}/feedback must return 204 even when
    DecisionMemoryStore.set_latest_outcome raises an exception (best-effort hook)."""
    session_id = str(uuid4())
    message_id = str(uuid4())

    # Mock repo.set_message_feedback to return True (message found and updated)
    mock_repo = AsyncMock()
    mock_repo.set_message_feedback = AsyncMock(return_value=True)

    # Make DecisionMemoryStore.set_latest_outcome raise
    async def _raising_set_latest_outcome(sid: str, outcome: int) -> bool:
        raise RuntimeError("DB connection lost")

    with (
        patch(
            "apps.api.routers.sessions.DecisionSessionRepository",
            return_value=mock_repo,
        ),
        patch.object(
            DecisionMemoryStore,
            "set_latest_outcome",
            new=_raising_set_latest_outcome,
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.patch(
                f"/api/v1/sessions/{session_id}/messages/{message_id}/feedback",
                json={"feedback": 1},
            )

    assert resp.status_code == 204, (
        f"Expected 204 even when set_latest_outcome raises, got {resp.status_code}"
    )


async def test_feedback_endpoint_204_on_valid_feedback() -> None:
    """PATCH feedback endpoint returns 204 when everything succeeds."""
    session_id = str(uuid4())
    message_id = str(uuid4())

    mock_repo = AsyncMock()
    mock_repo.set_message_feedback = AsyncMock(return_value=True)

    mock_pool, _ = _make_mock_pool("UPDATE 1")
    mock_store = DecisionMemoryStore(pool=mock_pool)

    with (
        patch(
            "apps.api.routers.sessions.DecisionSessionRepository",
            return_value=mock_repo,
        ),
        patch(
            "apps.api.routers.sessions.DecisionMemoryStore",
            return_value=mock_store,
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.patch(
                f"/api/v1/sessions/{session_id}/messages/{message_id}/feedback",
                json={"feedback": -1},
            )

    assert resp.status_code == 204


# ---------------------------------------------------------------------------
# ControlAgent Past Decisions block — annotation rendering
# ---------------------------------------------------------------------------


async def test_control_agent_past_decisions_renders_positive_annotation() -> None:
    """When a past decision record has outcome=1, the context block must contain
    '[user feedback: positive]'."""
    from packages.agent.control.control_agent import ControlAgent
    from packages.agent.orchestrator.models import SpecialistTask

    session_id = str(uuid4())
    task = SpecialistTask(
        task_id=uuid4(),
        instruction="Analyze stockout risk.",
        context_payload={
            "intent": {"category": "supply_chain"},
            "session_id": session_id,
        },
        allowed_tools=[],
    )

    # Fake past decision record with outcome=1
    past_record = {
        "content_json": json.dumps({"decision": "order more SKU-001"}),
        "outcome": 1,
    }

    mock_tool_registry = MagicMock()
    mock_tool_registry.list_for_role.return_value = []
    mock_tool_registry.filter_for_user_role.return_value = []

    captured_instructions: list[str] = []

    async def _fake_super_run(
        self_inner: Any, task_inner: Any, ctx: Any, agent_run_id: str = ""
    ) -> Any:
        captured_instructions.append(task_inner.instruction)
        result = MagicMock()
        result.output = {"text": "Done."}
        result.status = "completed"
        result.usage = {}
        return result

    ctx = MagicMock()
    ctx.session_id = uuid4()

    with (
        patch(
            "packages.agent.control.control_agent.DecisionMemoryStore.search",
            new=AsyncMock(return_value=[past_record]),
        ),
        patch(
            "packages.agent.control.control_agent.LongTermMemoryStore.search",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "packages.agent.control.control_agent.SkillLoader.load",
            return_value=[],
        ),
        patch(
            "packages.agent.base.AgentBasedSpecialist.run",
            new=_fake_super_run,
        ),
    ):
        agent = ControlAgent(
            llm_client=MagicMock(_model="stub"),
            tool_registry=mock_tool_registry,
        )
        await agent.run(task, ctx)

    assert captured_instructions, "Expected at least one instruction to be captured"
    instruction = captured_instructions[0]
    assert "[user feedback: positive]" in instruction, (
        f"Expected '[user feedback: positive]' in instruction, got:\n{instruction!r}"
    )


async def test_control_agent_past_decisions_renders_negative_annotation() -> None:
    """When a past decision record has outcome=-1, the context block must contain
    '[user feedback: negative]'."""
    from packages.agent.control.control_agent import ControlAgent
    from packages.agent.orchestrator.models import SpecialistTask

    session_id = str(uuid4())
    task = SpecialistTask(
        task_id=uuid4(),
        instruction="Analyze stockout risk.",
        context_payload={
            "intent": {"category": "supply_chain"},
            "session_id": session_id,
        },
        allowed_tools=[],
    )

    past_record = {
        "content_json": json.dumps({"decision": "reduce safety stock"}),
        "outcome": -1,
    }

    mock_tool_registry = MagicMock()
    mock_tool_registry.list_for_role.return_value = []
    mock_tool_registry.filter_for_user_role.return_value = []

    captured_instructions: list[str] = []

    async def _fake_super_run(
        self_inner: Any, task_inner: Any, ctx: Any, agent_run_id: str = ""
    ) -> Any:
        captured_instructions.append(task_inner.instruction)
        result = MagicMock()
        result.output = {"text": "Done."}
        result.status = "completed"
        result.usage = {}
        return result

    ctx = MagicMock()
    ctx.session_id = uuid4()

    with (
        patch(
            "packages.agent.control.control_agent.DecisionMemoryStore.search",
            new=AsyncMock(return_value=[past_record]),
        ),
        patch(
            "packages.agent.control.control_agent.LongTermMemoryStore.search",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "packages.agent.control.control_agent.SkillLoader.load",
            return_value=[],
        ),
        patch(
            "packages.agent.base.AgentBasedSpecialist.run",
            new=_fake_super_run,
        ),
    ):
        agent = ControlAgent(
            llm_client=MagicMock(_model="stub"),
            tool_registry=mock_tool_registry,
        )
        await agent.run(task, ctx)

    assert captured_instructions
    instruction = captured_instructions[0]
    assert "[user feedback: negative]" in instruction, (
        f"Expected '[user feedback: negative]' in instruction, got:\n{instruction!r}"
    )


async def test_control_agent_past_decisions_omits_annotation_when_outcome_null() -> None:
    """When a past decision record has outcome=None (NULL), no annotation is added."""
    from packages.agent.control.control_agent import ControlAgent
    from packages.agent.orchestrator.models import SpecialistTask

    session_id = str(uuid4())
    task = SpecialistTask(
        task_id=uuid4(),
        instruction="Analyze stockout risk.",
        context_payload={
            "intent": {"category": "supply_chain"},
            "session_id": session_id,
        },
        allowed_tools=[],
    )

    past_record = {
        "content_json": json.dumps({"decision": "hold current stock"}),
        "outcome": None,
    }

    mock_tool_registry = MagicMock()
    mock_tool_registry.list_for_role.return_value = []
    mock_tool_registry.filter_for_user_role.return_value = []

    captured_instructions: list[str] = []

    async def _fake_super_run(
        self_inner: Any, task_inner: Any, ctx: Any, agent_run_id: str = ""
    ) -> Any:
        captured_instructions.append(task_inner.instruction)
        result = MagicMock()
        result.output = {"text": "Done."}
        result.status = "completed"
        result.usage = {}
        return result

    ctx = MagicMock()
    ctx.session_id = uuid4()

    with (
        patch(
            "packages.agent.control.control_agent.DecisionMemoryStore.search",
            new=AsyncMock(return_value=[past_record]),
        ),
        patch(
            "packages.agent.control.control_agent.LongTermMemoryStore.search",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "packages.agent.control.control_agent.SkillLoader.load",
            return_value=[],
        ),
        patch(
            "packages.agent.base.AgentBasedSpecialist.run",
            new=_fake_super_run,
        ),
    ):
        agent = ControlAgent(
            llm_client=MagicMock(_model="stub"),
            tool_registry=mock_tool_registry,
        )
        await agent.run(task, ctx)

    assert captured_instructions
    instruction = captured_instructions[0]
    assert "[user feedback: positive]" not in instruction, (
        "Must not add positive annotation when outcome is NULL"
    )
    assert "[user feedback: negative]" not in instruction, (
        "Must not add negative annotation when outcome is NULL"
    )
    # The decision content itself must still appear
    assert "hold current stock" in instruction, (
        "Decision content must still appear even without outcome annotation"
    )


# ---------------------------------------------------------------------------
# _SYSTEM_PROMPT contains negative-feedback-avoidance instruction
# ---------------------------------------------------------------------------


def test_system_prompt_contains_negative_feedback_avoidance_instruction() -> None:
    """_SYSTEM_PROMPT must instruct the agent to avoid approaches that previously
    received negative feedback (ADR §3)."""
    from packages.agent.control.control_agent import _SYSTEM_PROMPT

    assert "negative" in _SYSTEM_PROMPT.lower(), (
        "_SYSTEM_PROMPT must reference 'negative' feedback"
    )
    assert "avoid" in _SYSTEM_PROMPT.lower(), (
        "_SYSTEM_PROMPT must instruct the agent to 'avoid' negatively-rated approaches"
    )
    # Exact phrase from the implementation
    assert "[user feedback: negative]" in _SYSTEM_PROMPT, (
        "_SYSTEM_PROMPT must contain the literal '[user feedback: negative]' annotation "
        "so the agent recognises it in the Past Decisions block"
    )
