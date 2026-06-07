from __future__ import annotations

"""Unit tests for T-167 and T-168: model_name emitted in graph_node meta.

T-167 — session_orchestrator._get_orchestrator_model_name helper and
        its use in _astream_run on_chain_start / on_chain_end branches.

T-168 — runtime._run_agent() includes model_name in meta for both
        graph_node start and end events.
"""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from packages.agent.orchestrator.session_orchestrator import (
    _get_orchestrator_model_name,
)


# ---------------------------------------------------------------------------
# T-167 helper: _get_orchestrator_model_name
# ---------------------------------------------------------------------------


def test_get_orchestrator_model_name_returns_orchestrator_model_first() -> None:
    """_orchestrator_model takes precedence over _model."""

    class _Client:
        _orchestrator_model = "claude-opus-4"
        _model = "claude-haiku-4"

    result = _get_orchestrator_model_name(_Client())
    assert result == "claude-opus-4"


def test_get_orchestrator_model_name_falls_back_to_model() -> None:
    """When _orchestrator_model is absent, falls back to _model."""

    class _Client:
        _model = "claude-haiku-4"

    result = _get_orchestrator_model_name(_Client())
    assert result == "claude-haiku-4"


def test_get_orchestrator_model_name_returns_none_for_stub() -> None:
    """When neither attribute exists, returns None (stub clients)."""

    class _StubClient:
        pass

    result = _get_orchestrator_model_name(_StubClient())
    assert result is None


def test_get_orchestrator_model_name_treats_empty_orchestrator_model_as_falsy() -> None:
    """Empty string _orchestrator_model falls back to _model."""

    class _Client:
        _orchestrator_model = ""
        _model = "claude-sonnet-4-6"

    result = _get_orchestrator_model_name(_Client())
    assert result == "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# T-167 integration: graph_node events include model_name in meta
# ---------------------------------------------------------------------------


class _DirectChatLLMClient:
    """Minimal stub that routes through direct_chat and exposes model attributes."""

    def __init__(self, model: str = "stub-model", orchestrator_model: str | None = None) -> None:
        self._model = model
        if orchestrator_model is not None:
            self._orchestrator_model = orchestrator_model

    async def complete(
        self,
        messages: Any,
        tools: Any = None,
        temperature: float = 0.0,
        max_tokens: int = 512,
        prompt_cache: bool = False,
        agent_step_id: Any = None,
        specialist_role: Any = None,
    ) -> Any:
        from decimal import Decimal

        from packages.agent.llm import LLMResponse, LLMUsage

        system = messages[0].content if messages else ""
        if "intent classifier" in system:
            text = (
                '{"category":"direct_chat","confidence":0.95,'
                '"rationale":"Greeting","goal_text":"hello"}'
            )
        elif "router inside SessionOrchestrator" in system:
            text = (
                '{"mode":"direct_chat","agents":[],'
                '"requires_planning":false,"requires_dag":false,"rationale":"chat"}'
            )
        else:
            text = "Hi there!"
        return LLMResponse(
            text=text,
            tool_calls=[],
            finish_reason="stop",
            usage=LLMUsage(input_tokens=0, output_tokens=0, total_cost_usd=Decimal("0")),
            model=self._model,
            request_id=str(uuid4()),
            latency_ms=0,
        )

    async def stream(self, messages: Any, tools: Any = None, **kwargs: Any) -> Any:
        from packages.agent.llm import LLMStreamEvent

        resp = await self.complete(messages, tools=tools, **kwargs)

        async def _gen() -> Any:
            yield LLMStreamEvent(event="text_delta", data=resp.text)

        return _gen()


async def _run_orchestrator_collect_events(
    llm_client: Any,
) -> list[dict[str, Any]]:
    """Run the orchestrator for a simple direct_chat query, collect SSE events.

    Follows the same pattern as test_tool_layer_integration.py — no explicit
    patching needed because make_step and DecisionSessionRepository both swallow
    exceptions gracefully when the DB is absent.
    """
    import asyncio

    from packages.agent.orchestrator import SessionOrchestrator, SessionUserQuery
    from packages.agent.orchestrator.models import AgentRoute, SessionIntent
    from packages.memory import StubMemoryStore
    from packages.tools import create_tool_registry
    from tests.unit.helpers import MultiRoleModelRegistry, StructuredOutputFakeModel

    # chat intent skips AskUserDecision — routes direct_chat immediately
    orch_model = StructuredOutputFakeModel([
        SessionIntent(
            category="chat", confidence=0.95,
            rationale="Greeting", goal_text="hello",
        ),
        AgentRoute(
            mode="direct_chat", agents=[],
            requires_planning=False, requires_dag=False, rationale="chat",
        ),
    ])
    registry = MultiRoleModelRegistry({"orchestrator": orch_model})

    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    orch = SessionOrchestrator(
        llm_client=llm_client,
        tool_registry=create_tool_registry(llm_client),
        memory_store=StubMemoryStore(),
        sse_queue=queue,
        model_registry=registry,
    )

    session_id = uuid4()
    query = SessionUserQuery(text="Hello!")

    await orch.run(session_id, query)

    events: list[dict[str, Any]] = []
    while not queue.empty():
        events.append(await queue.get())
    return events


async def test_t167_orchestrator_graph_node_start_has_model_name() -> None:
    """graph_node start events (kind=orchestrator) must include model_name in meta."""
    llm = _DirectChatLLMClient(model="test-model-start")
    events = await _run_orchestrator_collect_events(llm)

    orch_starts = [
        e for e in events
        if e.get("type") == "graph_node"
        and e.get("event") == "start"
        and e.get("kind") == "orchestrator"
    ]
    assert orch_starts, "Expected at least one orchestrator graph_node start event"

    for ev in orch_starts:
        meta = ev.get("meta", {})
        assert "model_name" in meta, (
            f"graph_node start meta missing model_name: {ev}"
        )
        assert meta["model_name"] == "test-model-start", (
            f"Unexpected model_name in start meta: {meta['model_name']!r}"
        )


async def test_t167_orchestrator_graph_node_end_has_model_name() -> None:
    """graph_node end events (kind=orchestrator) must include model_name in meta."""
    llm = _DirectChatLLMClient(model="test-model-end")
    events = await _run_orchestrator_collect_events(llm)

    orch_ends = [
        e for e in events
        if e.get("type") == "graph_node"
        and e.get("event") == "end"
        and e.get("kind") == "orchestrator"
    ]
    assert orch_ends, "Expected at least one orchestrator graph_node end event"

    for ev in orch_ends:
        meta = ev.get("meta", {})
        assert "model_name" in meta, (
            f"graph_node end meta missing model_name: {ev}"
        )
        assert meta["model_name"] == "test-model-end", (
            f"Unexpected model_name in end meta: {meta['model_name']!r}"
        )


async def test_t167_orchestrator_model_attribute_preferred_over_model() -> None:
    """When _orchestrator_model is set, it is used in meta rather than _model."""
    llm = _DirectChatLLMClient(
        model="haiku-model", orchestrator_model="sonnet-model"
    )
    events = await _run_orchestrator_collect_events(llm)

    orch_starts = [
        e for e in events
        if e.get("type") == "graph_node"
        and e.get("event") == "start"
        and e.get("kind") == "orchestrator"
    ]
    assert orch_starts, "Expected at least one orchestrator graph_node start event"

    for ev in orch_starts:
        meta = ev.get("meta", {})
        assert meta.get("model_name") == "sonnet-model", (
            f"Expected orchestrator model 'sonnet-model', got: {meta.get('model_name')!r}"
        )


# ---------------------------------------------------------------------------
# T-168: _run_agent includes model_name in agent graph_node meta
# ---------------------------------------------------------------------------


async def test_t168_run_agent_start_meta_includes_model_name() -> None:
    """_run_agent() graph_node start event must include model_name in meta."""
    from packages.agent.orchestrator.runtime import _run_agent

    collected: list[dict[str, Any]] = []

    class _FakeOrchestrator:
        _llm_client = MagicMock(_model="agent-model-123")
        _tool_registry = MagicMock()
        _sse_queue = None

        async def _push(self, event: dict[str, Any], sse_queue: Any = None) -> None:
            collected.append(event)

    orch = _FakeOrchestrator()

    # Fake agent that returns a SpecialistResult immediately
    class _FakeAgent:
        role = "data_engineer"

        async def run(self, task: Any, ctx: Any, agent_run_id: str = "") -> Any:
            from decimal import Decimal

            from packages.agent.orchestrator.models import SpecialistResult

            return SpecialistResult(
                task_id=task.task_id,
                agent_role="data_engineer",
                status="completed",
                output={"text": "done"},
                tool_calls_made=[],
                usage={"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
                error=None,
            )

    with (
        patch(
            "packages.agent.orchestrator.runtime._make_agent",
            return_value=_FakeAgent(),
        ),
        patch(
            "packages.persistence.agent_steps_repo.AgentStepsRepository"
        ) as mock_repo_cls,
        patch("packages.agent.orchestrator.runtime.asyncio.create_task"),
    ):
        mock_repo = MagicMock()
        mock_repo.create = AsyncMock()
        mock_repo.update_ended = AsyncMock()
        mock_repo_cls.return_value = mock_repo

        await _run_agent(
            orchestrator=orch,
            session_id=uuid4(),
            agent_role="data_engineer",
            instruction="analyze data",
            context_payload={},
            allowed_tools=[],
        )

    start_events = [
        e for e in collected
        if e.get("type") == "graph_node" and e.get("event") == "start" and e.get("kind") == "agent"
    ]
    assert start_events, "Expected at least one agent graph_node start event"

    start_meta = start_events[0].get("meta", {})
    assert "model_name" in start_meta, (
        f"agent graph_node start meta missing model_name: {start_meta}"
    )
    assert start_meta["model_name"] == "agent-model-123", (
        f"Unexpected model_name in start meta: {start_meta['model_name']!r}"
    )


async def test_t168_run_agent_end_meta_includes_model_name() -> None:
    """_run_agent() graph_node end event must include model_name in meta."""
    from packages.agent.orchestrator.runtime import _run_agent

    collected: list[dict[str, Any]] = []

    class _FakeOrchestrator:
        _llm_client = MagicMock(_model="agent-model-456")
        _tool_registry = MagicMock()
        _sse_queue = None

        async def _push(self, event: dict[str, Any], sse_queue: Any = None) -> None:
            collected.append(event)

    orch = _FakeOrchestrator()

    class _FakeAgent:
        role = "data_engineer"

        async def run(self, task: Any, ctx: Any, agent_run_id: str = "") -> Any:
            from packages.agent.orchestrator.models import SpecialistResult

            return SpecialistResult(
                task_id=task.task_id,
                agent_role="data_engineer",
                status="completed",
                output={"text": "done"},
                tool_calls_made=[],
                usage={"input_tokens": 5, "output_tokens": 3, "cost_usd": 0.001},
                error=None,
            )

    with (
        patch(
            "packages.agent.orchestrator.runtime._make_agent",
            return_value=_FakeAgent(),
        ),
        patch(
            "packages.persistence.agent_steps_repo.AgentStepsRepository"
        ) as mock_repo_cls,
        patch("packages.agent.orchestrator.runtime.asyncio.create_task"),
    ):
        mock_repo = MagicMock()
        mock_repo.create = AsyncMock()
        mock_repo.update_ended = AsyncMock()
        mock_repo_cls.return_value = mock_repo

        await _run_agent(
            orchestrator=orch,
            session_id=uuid4(),
            agent_role="data_engineer",
            instruction="analyze data",
            context_payload={},
            allowed_tools=[],
        )

    end_events = [
        e for e in collected
        if e.get("type") == "graph_node" and e.get("event") == "end" and e.get("kind") == "agent"
    ]
    assert end_events, "Expected at least one agent graph_node end event"

    end_meta = end_events[0].get("meta", {})
    assert "model_name" in end_meta, (
        f"agent graph_node end meta missing model_name: {end_meta}"
    )
    assert end_meta["model_name"] == "agent-model-456", (
        f"Unexpected model_name in end meta: {end_meta['model_name']!r}"
    )


async def test_t168_run_agent_model_name_none_when_llm_client_lacks_model() -> None:
    """When llm_client has no _model attribute, model_name is None (not an error)."""
    from packages.agent.orchestrator.runtime import _run_agent

    collected: list[dict[str, Any]] = []

    class _FakeOrchestrator:
        _llm_client = MagicMock(spec=[])  # no _model attribute
        _tool_registry = MagicMock()
        _sse_queue = None

        async def _push(self, event: dict[str, Any], sse_queue: Any = None) -> None:
            collected.append(event)

    orch = _FakeOrchestrator()

    class _FakeAgent:
        role = "data_engineer"

        async def run(self, task: Any, ctx: Any, agent_run_id: str = "") -> Any:
            from packages.agent.orchestrator.models import SpecialistResult

            return SpecialistResult(
                task_id=task.task_id,
                agent_role="data_engineer",
                status="completed",
                output={"text": "done"},
                tool_calls_made=[],
                usage={"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
                error=None,
            )

    with (
        patch(
            "packages.agent.orchestrator.runtime._make_agent",
            return_value=_FakeAgent(),
        ),
        patch(
            "packages.persistence.agent_steps_repo.AgentStepsRepository"
        ) as mock_repo_cls,
        patch("packages.agent.orchestrator.runtime.asyncio.create_task"),
    ):
        mock_repo = MagicMock()
        mock_repo.create = AsyncMock()
        mock_repo.update_ended = AsyncMock()
        mock_repo_cls.return_value = mock_repo

        await _run_agent(
            orchestrator=orch,
            session_id=uuid4(),
            agent_role="data_engineer",
            instruction="analyze data",
            context_payload={},
            allowed_tools=[],
        )

    start_events = [
        e for e in collected
        if e.get("type") == "graph_node" and e.get("event") == "start" and e.get("kind") == "agent"
    ]
    assert start_events, "Expected at least one agent graph_node start event"
    start_meta = start_events[0].get("meta", {})
    assert "model_name" in start_meta, "meta must contain model_name key even when None"
    assert start_meta["model_name"] is None, (
        f"Expected None for model_name, got: {start_meta['model_name']!r}"
    )
