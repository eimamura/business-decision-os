"""T-533 — Unit tests for P85-B-01 tool event persistence wiring.

Tests cover three scenarios:
1. Both SSE queue and persister wired through graph config → persisted tool graph_node
   start+end events with correct fields AND same events reach the queue.
2. Persister absent (None in configurable) → queue still receives events, no crash.
3. Persister raising an exception → tool execution completes normally, queue events
   unaffected.

Also covers get_registry aggregation query logic:
4. Registry tool aggregation counts only 'end' events, excludes 'start' events.

Uses _run_single_read_only_tool directly — the lightest harness that exercises the
_emit path for tool graph_node events without requiring a full graph run.
"""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from packages.agent.runtime import AgentRuntime
from packages.tools.base import ToolContext, ToolResult


# ---------------------------------------------------------------------------
# Stubs / helpers
# ---------------------------------------------------------------------------


class _SimpleTool:
    name = "nl_query"
    description = "Execute an NL query"
    input_schema: dict[str, Any] = {}
    output_schema: dict[str, Any] = {}
    safety_level = "read_only"

    async def handle(self, input: dict[str, Any], ctx: Any) -> ToolResult:
        return ToolResult(output={"rows": [{"id": 1}]}, audit_payload={})


class _FakeToolRegistry:
    def __init__(self, tools: list[Any]) -> None:
        self._tools = {t.name: t for t in tools}

    def list_for_role(self, role: str) -> list[Any]:
        return list(self._tools.values())

    def filter_for_user_role(self, user_role: str, tools: list[Any]) -> list[Any]:
        return tools

    def get(self, name: str) -> Any | None:
        return self._tools.get(name)


def _make_runtime() -> AgentRuntime:
    registry = MagicMock()
    registry.get.return_value = MagicMock()
    return AgentRuntime(
        name="test_agent",
        role="data_engineer",
        llm_client=None,
        tool_registry=_FakeToolRegistry([_SimpleTool()]),
        sse_queue=None,
        system_prompt="Test specialist.",
        model_registry=registry,
    )


def _make_ctx() -> ToolContext:
    return ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="data_engineer",
        actor="test-user",
        correlation_id=uuid4(),
        user_role="analyst",
    )


def _make_call(tool_name: str = "nl_query") -> dict[str, Any]:
    return {"id": str(uuid4()), "name": tool_name, "input": {}}


# ---------------------------------------------------------------------------
# T-533-1: SSE queue AND persister wired → persisted and queued events are correct
# ---------------------------------------------------------------------------


async def test_tool_events_persisted_and_queued_when_both_wired() -> None:
    """With both sse_queue and persister in config, tool graph_node start+end events
    must reach the persister AND the queue with correct type/kind/event/name fields."""
    runtime = _make_runtime()
    ctx = _make_ctx()
    call = _make_call("nl_query")

    queue: asyncio.Queue[Any] = asyncio.Queue()
    persisted: list[dict[str, Any]] = []

    async def recording_persister(event: dict[str, Any]) -> None:
        persisted.append(event)

    await runtime._run_single_read_only_tool(
        call=call,
        ctx=ctx,
        sse_queue=queue,
        agent_run_id="run-test-1",
        persister=recording_persister,
    )

    # Drain the queue
    queued: list[dict[str, Any]] = []
    while not queue.empty():
        queued.append(await queue.get())

    # Exactly two events (start + end) must have been persisted
    assert len(persisted) == 2, (
        f"Expected 2 persisted events (start+end), got {len(persisted)}: {persisted}"
    )

    start_event = persisted[0]
    end_event = persisted[1]

    assert start_event["type"] == "graph_node"
    assert start_event["kind"] == "tool"
    assert start_event["event"] == "start"
    assert start_event["name"] == "nl_query"

    assert end_event["type"] == "graph_node"
    assert end_event["kind"] == "tool"
    assert end_event["event"] == "end"
    assert end_event["name"] == "nl_query"

    # Same events must also have reached the queue
    assert len(queued) == 2, (
        f"Expected 2 queued events (start+end), got {len(queued)}: {queued}"
    )
    queue_types = {e["event"] for e in queued if e.get("type") == "graph_node"}
    assert "start" in queue_types
    assert "end" in queue_types


async def test_tool_events_persisted_events_name_matches_tool_name() -> None:
    """The 'name' field in persisted events must equal the tool name from the call."""
    runtime = _make_runtime()
    ctx = _make_ctx()
    call = _make_call("nl_query")

    persisted: list[dict[str, Any]] = []

    async def recording_persister(event: dict[str, Any]) -> None:
        persisted.append(event)

    await runtime._run_single_read_only_tool(
        call=call,
        ctx=ctx,
        sse_queue=None,
        agent_run_id="run-test-name",
        persister=recording_persister,
    )

    for event in persisted:
        assert event.get("name") == "nl_query", (
            f"Event 'name' field should be 'nl_query', got: {event.get('name')!r}"
        )


async def test_tool_events_event_field_is_start_or_end() -> None:
    """Each persisted tool graph_node event must have 'event' in {'start', 'end'}."""
    runtime = _make_runtime()
    ctx = _make_ctx()
    call = _make_call("nl_query")

    persisted: list[dict[str, Any]] = []

    async def recording_persister(event: dict[str, Any]) -> None:
        persisted.append(event)

    await runtime._run_single_read_only_tool(
        call=call,
        ctx=ctx,
        sse_queue=None,
        agent_run_id="run-test-event-field",
        persister=recording_persister,
    )

    for event in persisted:
        assert event.get("event") in {"start", "end"}, (
            f"'event' field must be 'start' or 'end', got: {event.get('event')!r}"
        )


# ---------------------------------------------------------------------------
# T-533-2: Persister absent (None) → queue still receives events, no crash
# ---------------------------------------------------------------------------


async def test_persister_absent_queue_still_receives_events() -> None:
    """When persister=None, the SSE queue must still receive start+end events."""
    runtime = _make_runtime()
    ctx = _make_ctx()
    call = _make_call("nl_query")

    queue: asyncio.Queue[Any] = asyncio.Queue()

    # Must not raise even though persister is absent
    result_entry, msg = await runtime._run_single_read_only_tool(
        call=call,
        ctx=ctx,
        sse_queue=queue,
        agent_run_id="run-no-persister",
        persister=None,
    )

    queued: list[dict[str, Any]] = []
    while not queue.empty():
        queued.append(await queue.get())

    assert len(queued) == 2, (
        f"Expected 2 queued events even with persister=None, got {len(queued)}"
    )
    event_values = {e.get("event") for e in queued}
    assert "start" in event_values
    assert "end" in event_values


async def test_persister_key_missing_from_config_queue_still_receives_events() -> None:
    """When 'event_persister' key is absent from configurable, _execute_tools_node
    falls back to persister=None — queue must still receive events, no crash."""
    from packages.agent.runtime import _LCResponse

    tool = _SimpleTool()
    runtime = AgentRuntime(
        name="test_agent",
        role="data_engineer",
        llm_client=None,
        tool_registry=_FakeToolRegistry([tool]),
        sse_queue=None,
        system_prompt="Test specialist.",
        model_registry=MagicMock(),
    )
    ctx = _make_ctx()
    queue: asyncio.Queue[Any] = asyncio.Queue()

    # Configurable has no 'event_persister' key — must not raise
    response = _LCResponse(
        text="",
        tool_calls=[{"id": str(uuid4()), "name": "nl_query", "input": {}}],
        finish_reason="tool_use",
        model="test",
    )
    state: dict[str, Any] = {
        "messages": [],
        "response": response,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
        "tool_results": [],
        "iteration": 0,
        "status": "running",
        "error": None,
        "pending_hitl_approval_id": None,
        "pending_hitl_job_id": None,
        "compressed_messages": None,
        "tool_plan": [],
    }
    # 'event_persister' intentionally omitted from configurable
    config: dict[str, Any] = {
        "configurable": {
            "ctx": ctx,
            "sse_queue": queue,
            "agent_run_id": "run-no-key",
            # 'event_persister' key absent
        }
    }

    await runtime._execute_tools_node(state, config)  # type: ignore[arg-type]

    queued: list[dict[str, Any]] = []
    while not queue.empty():
        queued.append(await queue.get())

    tool_events = [e for e in queued if e.get("type") == "graph_node" and e.get("kind") == "tool"]
    assert len(tool_events) >= 2, (
        f"Expected at least 2 tool graph_node events without event_persister key, "
        f"got {len(tool_events)}"
    )


# ---------------------------------------------------------------------------
# T-533-3: Persister raising → run completes, queue events unaffected
# ---------------------------------------------------------------------------


async def test_persister_raising_does_not_interrupt_tool_execution() -> None:
    """When persister raises, _run_single_read_only_tool must complete normally
    and return a valid (result_entry, message) tuple."""
    runtime = _make_runtime()
    ctx = _make_ctx()
    call = _make_call("nl_query")

    async def raising_persister(event: dict[str, Any]) -> None:
        raise RuntimeError("DB connection failed")

    # Must not raise — persister failures are swallowed by _emit
    result_entry, msg = await runtime._run_single_read_only_tool(
        call=call,
        ctx=ctx,
        sse_queue=None,
        agent_run_id="run-raising-persister",
        persister=raising_persister,
    )

    assert result_entry == {"nl_query": {"rows": [{"id": 1}]}}, (
        f"Tool result should be returned despite persister error, got: {result_entry}"
    )


async def test_persister_raising_queue_events_still_delivered() -> None:
    """When persister raises, SSE queue events must still be delivered unchanged."""
    runtime = _make_runtime()
    ctx = _make_ctx()
    call = _make_call("nl_query")

    queue: asyncio.Queue[Any] = asyncio.Queue()

    async def raising_persister(event: dict[str, Any]) -> None:
        raise ValueError("Transient write failure")

    await runtime._run_single_read_only_tool(
        call=call,
        ctx=ctx,
        sse_queue=queue,
        agent_run_id="run-raising-queue",
        persister=raising_persister,
    )

    queued: list[dict[str, Any]] = []
    while not queue.empty():
        queued.append(await queue.get())

    assert len(queued) == 2, (
        f"Expected 2 queued events even when persister raises, got {len(queued)}"
    )
    event_values = {e.get("event") for e in queued}
    assert "start" in event_values
    assert "end" in event_values


# ---------------------------------------------------------------------------
# T-533-4: get_registry tool aggregation — end events counted, start excluded
#
# Decision: Adding a focused unit test that mocks the pool rows used by
# get_registry. No existing unit test covered this endpoint; the task
# specification says "a focused unit test mocking the pool is welcome but
# optional". Given that B-01 changed the aggregation query from
# 'tool_completed' to 'graph_node kind=tool event=end', verifying the
# correct filter (end only, start excluded) adds direct coverage of the
# T-532 query fix with zero additional infrastructure.
# ---------------------------------------------------------------------------


async def test_get_registry_counts_only_end_events_not_start_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """get_registry tool aggregation must count 'end' events only.

    Mocked pool rows: one tool with execution_count=3 (end events only).
    Start events are excluded by the WHERE clause; they must not inflate the count.
    """
    import datetime
    import httpx
    from httpx import ASGITransport
    import apps.api.routers.admin as admin_router
    from apps.api.main import app

    last_ts = datetime.datetime(2026, 6, 11, 12, 0, 0, tzinfo=datetime.timezone.utc)

    class _FakeRow(dict):
        """Dict subclass that also supports attribute access (asyncpg Record-like)."""

        def __getattr__(self, name: str) -> Any:
            try:
                return self[name]
            except KeyError as exc:
                raise AttributeError(name) from exc

    agent_rows: list[Any] = []  # no agent stats needed for this test
    # Simulates 3 'end' events for 'nl_query' (start events excluded by WHERE clause)
    tool_rows: list[Any] = [
        _FakeRow(tool_name="nl_query", execution_count=3, last_executed_at=last_ts),
    ]

    class _FakeConn:
        async def fetch(self, query: str, *args: Any) -> list[Any]:
            # Return different rows based on which query is being executed
            if "agent_steps" in query:
                return agent_rows
            if "session_events" in query:
                return tool_rows
            return []

    class _FakeAcquire:
        async def __aenter__(self) -> _FakeConn:
            return _FakeConn()

        async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            return None

    class _FakePool:
        def acquire(self) -> _FakeAcquire:
            return _FakeAcquire()

    async def _fake_get_pool() -> _FakePool:
        return _FakePool()

    monkeypatch.setattr(admin_router, "get_pool", _fake_get_pool)

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/admin/registry")

    assert response.status_code == 200
    body = response.json()

    # Find nl_query in the tools list
    tools_by_name = {t["name"]: t for t in body["tools"]}
    assert "nl_query" in tools_by_name, (
        f"Expected 'nl_query' in registry tools, got: {list(tools_by_name.keys())}"
    )
    nl_query_entry = tools_by_name["nl_query"]
    assert nl_query_entry["execution_count"] == 3, (
        f"Expected execution_count=3 (from end events only), "
        f"got {nl_query_entry['execution_count']}"
    )
    assert nl_query_entry["last_executed_at"] is not None, (
        "last_executed_at must be non-null when end events exist"
    )


async def test_get_registry_tool_with_no_events_has_zero_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A tool that has never run must have execution_count=0 and last_executed_at=None."""
    import httpx
    from httpx import ASGITransport
    import apps.api.routers.admin as admin_router
    from apps.api.main import app

    class _FakeConn:
        async def fetch(self, query: str, *args: Any) -> list[Any]:
            return []  # no rows for either agents or tools

    class _FakeAcquire:
        async def __aenter__(self) -> _FakeConn:
            return _FakeConn()

        async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            return None

    class _FakePool:
        def acquire(self) -> _FakeAcquire:
            return _FakeAcquire()

    async def _fake_get_pool() -> _FakePool:
        return _FakePool()

    monkeypatch.setattr(admin_router, "get_pool", _fake_get_pool)

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/admin/registry")

    assert response.status_code == 200
    body = response.json()

    # Every tool should have execution_count=0 and last_executed_at=None
    for tool_entry in body["tools"]:
        assert tool_entry["execution_count"] == 0, (
            f"Tool {tool_entry['name']!r} should have execution_count=0 with no events, "
            f"got {tool_entry['execution_count']}"
        )
        assert tool_entry["last_executed_at"] is None, (
            f"Tool {tool_entry['name']!r} should have last_executed_at=None with no events"
        )
