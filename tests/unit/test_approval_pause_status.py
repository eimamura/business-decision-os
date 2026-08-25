"""D-026: approval-pause persists decision_sessions.status='awaiting_input'.

Lifecycle under test:
  1. Control run hits a HITL tool call (job_dispatch / request_approval)
     -> _prepare_hitl_node persists status='awaiting_input' using the same
        mechanism as the ask_user pause path (DECISIONS.md 2026-08-24).
  2. Resume-on-approve: linked job executes -> session reaches the
        contract-correct terminal state ('completed' / 'failed').
  3. Reject / decision-time transitions stay per contract.
"""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

from packages.agent.llm import LLMMessage, LLMResponse
from packages.agent.orchestrator.models import SpecialistTask
from packages.agent.runtime import AgentRuntime
from packages.tools.base import ToolResult
from tests.unit.helpers import (
    FakeLCModel,
    make_llm_usage,
    make_model_registry,
)

_AWAITING_INPUT = "awaiting_input"


# ---------------------------------------------------------------------------
# Harness (mirrors tests/unit/test_hitl_flow.py)
# ---------------------------------------------------------------------------


def _tool_use_response(tool_name: str, tool_input: dict[str, Any]) -> LLMResponse:
    return LLMResponse(
        text="",
        tool_calls=[{"id": str(uuid4()), "name": tool_name, "input": tool_input}],
        finish_reason="tool_use",
        usage=make_llm_usage(),
        model="claude-sonnet-4-6-test",
        request_id=str(uuid4()),
        latency_ms=1,
    )


class _FakeHITLTool:
    def __init__(self, name: str = "request_approval") -> None:
        self.name = name

    description = "Requests human approval"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {"action_summary": {"type": "string"}},
        "required": ["action_summary"],
    }
    output_schema: dict[str, Any] = {}
    safety_level = "hitl"

    async def handle(self, input: dict[str, Any], ctx: Any) -> Any:
        raise AssertionError("handle() must not be called for a hitl tool")


class _FakeToolRegistry:
    def __init__(self, tools: list[Any]) -> None:
        self._tools = tools

    def list_for_role(self, role: str) -> list[Any]:
        return self._tools

    def filter_for_user_role(self, user_role: str, tools: list[Any]) -> list[Any]:
        return tools

    def get(self, name: str) -> Any | None:
        for t in self._tools:
            if t.name == name:
                return t
        return None


class _FakeToolContext:
    def __init__(self) -> None:
        self.agent_step_id = uuid4()
        self.session_id = uuid4()
        self.user_id = "test-user"
        self.user_role = "manager"
        self.actor = "test-user"


async def _run_hitl_graph_to_interrupt(
    tool: Any,
    tool_name: str,
    tool_input: dict[str, Any],
    approvals_repo: Any,
) -> UUID:
    """Drive an AgentRuntime graph into the approval interrupt; return ctx.session_id."""
    lc_model = FakeLCModel([_tool_use_response(tool_name, tool_input)])
    registry = _FakeToolRegistry([tool])
    runtime = AgentRuntime(
        name="test_agent",
        role="data_engineer",
        llm_client=MagicMock(),
        tool_registry=registry,
        sse_queue=None,
        system_prompt="You are a test specialist.",
        model_registry=make_model_registry(lc_model),
    )
    task = SpecialistTask(
        task_id=uuid4(),
        instruction="Dispatch the job",
        context_payload={},
        allowed_tools=[tool_name],
    )
    ctx = _FakeToolContext()

    from langgraph.checkpoint.memory import MemorySaver
    from packages.agent.llm import LLMToolSpec

    llm_tools = [
        LLMToolSpec(name=t.name, description=t.description, input_schema=t.input_schema)
        for t in registry.list_for_role("data_engineer")
    ]
    system_blocks = [
        {"type": "text", "text": "You are a test specialist.", "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": "", "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": "Role: data_engineer\nAvailable tools: 1"},
    ]
    checkpointer = MemorySaver()
    graph = runtime._build_graph(checkpointer)
    run_config: dict[str, Any] = {
        "configurable": {
            "thread_id": str(uuid4()),
            "task": task,
            "ctx": ctx,
            "llm_tools": llm_tools,
            "sse_queue": None,
        }
    }
    from packages.agent.runtime import AgentState

    initial_state: AgentState = {
        "messages": [
            LLMMessage(role="system", content="", content_blocks=system_blocks),
            LLMMessage(role="user", content="Dispatch the job"),
        ],
        "response": None,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
        "tool_results": [],
        "iteration": 0,
        "status": "running",
        "error": None,
        "pending_hitl_approval_id": None,
        "pending_hitl_job_id": None,
    }

    with patch(
        "packages.persistence.approvals_repo.ApprovalsRepository",
        return_value=approvals_repo,
    ):
        result = await graph.ainvoke(initial_state, config=run_config)

    assert "__interrupt__" in result, (
        "graph must suspend at wait_for_approval for this test to exercise the pause path"
    )
    await _drain_pending_tasks()
    return ctx.session_id


async def _drain_pending_tasks() -> None:
    """Flush fire-and-forget asyncio tasks (_schedule_session_status_update)."""
    for _ in range(10):
        pending = [
            t for t in asyncio.all_tasks() if t is not asyncio.current_task()
        ]
        if not pending:
            return
        await asyncio.gather(*pending, return_exceptions=True)


def _mock_approvals_repo(approval_id: str | None = None) -> MagicMock:
    repo = MagicMock()
    repo.create = AsyncMock(return_value={"id": approval_id or str(uuid4())})
    return repo


# ---------------------------------------------------------------------------
# 1. Approval-pause persists awaiting_input
# ---------------------------------------------------------------------------


async def test_approval_pause_persists_awaiting_input_on_job_dispatch() -> None:
    """The production pause path (job_dispatch HITL) must persist awaiting_input."""
    session_status_calls: list[tuple[str, str]] = []

    async def _fake_session_update(sid: str, status: str) -> None:
        session_status_calls.append((sid, status))

    mock_jobs_repo = MagicMock()
    mock_jobs_repo.create = AsyncMock(return_value={"id": str(uuid4())})

    with (
        patch(
            "packages.persistence.sessions_repo.DecisionSessionRepository.update_status",
            side_effect=_fake_session_update,
        ),
        patch(
            "packages.persistence.jobs_repo.JobsRepository.create",
            mock_jobs_repo.create,
        ),
    ):
        session_id = await _run_hitl_graph_to_interrupt(
            _FakeHITLTool(name="job_dispatch"),
            "job_dispatch",
            {
                "job_type": "simulate",
                "params": {},
                "description": "Run simulation",
            },
            _mock_approvals_repo(),
        )

    assert (str(session_id), _AWAITING_INPUT) in session_status_calls, (
        f"approval-pause must persist status='awaiting_input' for session "
        f"{session_id}; got {session_status_calls}"
    )


async def test_approval_pause_persists_awaiting_input_on_generic_hitl_tool() -> None:
    """Non-job HITL tools pause through the same node and must behave identically."""
    session_status_calls: list[tuple[str, str]] = []

    async def _fake_session_update(sid: str, status: str) -> None:
        session_status_calls.append((sid, status))

    with patch(
        "packages.persistence.sessions_repo.DecisionSessionRepository.update_status",
        side_effect=_fake_session_update,
    ):
        session_id = await _run_hitl_graph_to_interrupt(
            _FakeHITLTool(),
            "request_approval",
            {"action_summary": "Reorder 1000 units of SKU-A"},
            _mock_approvals_repo(),
        )

    assert (str(session_id), _AWAITING_INPUT) in session_status_calls, (
        f"generic HITL pause must persist awaiting_input; got {session_status_calls}"
    )


async def test_approval_pause_persists_awaiting_input_when_repo_create_fails() -> None:
    """The status write must survive an ApprovalsRepository outage (fallback UUID path)."""
    session_status_calls: list[tuple[str, str]] = []

    async def _fake_session_update(sid: str, status: str) -> None:
        session_status_calls.append((sid, status))

    failing_repo = MagicMock()
    failing_repo.create = AsyncMock(side_effect=RuntimeError("DB unavailable"))

    mock_jobs_repo = MagicMock()
    mock_jobs_repo.create = AsyncMock(return_value={"id": str(uuid4())})

    with (
        patch(
            "packages.persistence.sessions_repo.DecisionSessionRepository.update_status",
            side_effect=_fake_session_update,
        ),
        patch(
            "packages.persistence.jobs_repo.JobsRepository.create",
            mock_jobs_repo.create,
        ),
    ):
        session_id = await _run_hitl_graph_to_interrupt(
            _FakeHITLTool(name="job_dispatch"),
            "job_dispatch",
            {"job_type": "simulate", "params": {}, "description": "x"},
            failing_repo,
        )

    assert (str(session_id), _AWAITING_INPUT) in session_status_calls, (
        f"pause status write must not depend on approvals-repo health; got {session_status_calls}"
    )


async def test_approval_pause_does_not_write_other_statuses() -> None:
    """Only 'awaiting_input' may be written by the pause path (vocabulary contract)."""
    session_status_calls: list[tuple[str, str]] = []

    async def _fake_session_update(sid: str, status: str) -> None:
        session_status_calls.append((sid, status))

    with patch(
        "packages.persistence.sessions_repo.DecisionSessionRepository.update_status",
        side_effect=_fake_session_update,
    ):
        await _run_hitl_graph_to_interrupt(
            _FakeHITLTool(),
            "request_approval",
            {"action_summary": "x"},
            _mock_approvals_repo(),
        )

    assert set(status for _, status in session_status_calls) == {_AWAITING_INPUT}, (
        f"pause path must write only awaiting_input; got {session_status_calls}"
    )


# ---------------------------------------------------------------------------
# 2. Resume-on-approve reaches the contract-correct terminal state
# ---------------------------------------------------------------------------


def _fake_job_row(job_id: UUID, session_id: UUID | None) -> dict[str, Any]:
    return {
        "id": job_id,
        "job_type": "simulate",
        "params_json": {},
        "session_id": session_id,
        "status": "pending_approval",
    }


async def test_execute_job_syncs_session_completed_after_job_execution() -> None:
    """After a linked job completes, the session must transition to 'completed'."""
    from packages.agent.job_executor import execute_job

    job_id = uuid4()
    session_id = uuid4()
    fake_job = _fake_job_row(job_id, session_id)
    mock_handle = AsyncMock(return_value=ToolResult(output={"result": "ok"}, audit_payload={}))

    session_update = AsyncMock()

    with (
        patch("packages.persistence.jobs_repo.JobsRepository.get_job", AsyncMock(return_value=fake_job)),
        patch(
            "packages.persistence.jobs_repo.JobsRepository.update_status",
            AsyncMock(return_value={**fake_job, "status": "completed"}),
        ),
        patch("packages.tools.simulation_tool.SimulationTool.handle", mock_handle),
        patch(
            "packages.persistence.sessions_repo.DecisionSessionRepository.update_status",
            session_update,
        ),
        patch(
            "packages.persistence.sessions_repo.DecisionSessionRepository.add_message",
            AsyncMock(),
        ),
    ):
        await execute_job(job_id)

    assert (str(session_id), "completed") in [
        (c.args[0], c.args[1]) for c in session_update.await_args_list
    ], (
        f"session must reach 'completed' after successful job execution; "
        f"got {[c.args for c in session_update.await_args_list]}"
    )


async def test_execute_job_syncs_session_failed_when_job_fails() -> None:
    """A failed linked job must drive the session to the 'failed' terminal state."""
    from packages.agent.job_executor import execute_job

    job_id = uuid4()
    session_id = uuid4()
    fake_job = _fake_job_row(job_id, session_id)

    session_update = AsyncMock()

    with (
        patch("packages.persistence.jobs_repo.JobsRepository.get_job", AsyncMock(return_value=fake_job)),
        patch(
            "packages.persistence.jobs_repo.JobsRepository.update_status",
            AsyncMock(return_value={**fake_job, "status": "failed"}),
        ),
        patch(
            "packages.tools.simulation_tool.SimulationTool.handle",
            AsyncMock(side_effect=RuntimeError("boom")),
        ),
        patch(
            "packages.persistence.sessions_repo.DecisionSessionRepository.update_status",
            session_update,
        ),
        patch(
            "packages.persistence.sessions_repo.DecisionSessionRepository.add_message",
            AsyncMock(),
        ),
    ):
        await execute_job(job_id)

    statuses = [c.args[1] for c in session_update.await_args_list]
    assert statuses[-1] == "failed", (
        f"session terminal status after failed job must be 'failed'; got {statuses}"
    )


async def test_execute_job_skips_session_sync_without_session_id() -> None:
    """Jobs without a session_id must not attempt a status sync."""
    from packages.agent.job_executor import execute_job

    job_id = uuid4()
    fake_job = _fake_job_row(job_id, None)
    session_update = AsyncMock()

    with (
        patch("packages.persistence.jobs_repo.JobsRepository.get_job", AsyncMock(return_value=fake_job)),
        patch(
            "packages.persistence.jobs_repo.JobsRepository.update_status",
            AsyncMock(return_value={**fake_job, "status": "completed"}),
        ),
        patch(
            "packages.tools.simulation_tool.SimulationTool.handle",
            AsyncMock(return_value=ToolResult(output={}, audit_payload={})),
        ),
        patch(
            "packages.persistence.sessions_repo.DecisionSessionRepository.update_status",
            session_update,
        ),
        patch(
            "packages.persistence.sessions_repo.DecisionSessionRepository.add_message",
            AsyncMock(),
        ),
    ):
        await execute_job(job_id)

    assert session_update.await_count == 0, (
        "no session status sync may occur when the job has no session_id"
    )


async def test_full_lifecycle_pause_then_approve_reaches_terminal() -> None:
    """End-to-end unit lifecycle: pause writes awaiting_input, approve+job completes it.

    Phase 1: HITL pause -> awaiting_input.
    Phase 2: POST /approvals/{id}/decision approved with linked job ->
             decision-time 'completed' write + execute_job dispatched.
    """
    from httpx import ASGITransport, AsyncClient

    # --- Phase 1: pause ---
    phase1_calls: list[tuple[str, str]] = []

    async def _fake_session_update_phase1(sid: str, status: str) -> None:
        phase1_calls.append((sid, status))

    paused_session_id: UUID | None = None
    mock_jobs_repo_pause = MagicMock()
    mock_jobs_repo_pause.create = AsyncMock(return_value={"id": str(uuid4())})

    with (
        patch(
            "packages.persistence.sessions_repo.DecisionSessionRepository.update_status",
            side_effect=_fake_session_update_phase1,
        ),
        patch(
            "packages.persistence.jobs_repo.JobsRepository.create",
            mock_jobs_repo_pause.create,
        ),
    ):
        paused_session_id = await _run_hitl_graph_to_interrupt(
            _FakeHITLTool(name="job_dispatch"),
            "job_dispatch",
            {"job_type": "simulate", "params": {}, "description": "x"},
            _mock_approvals_repo(),
        )

    assert (str(paused_session_id), _AWAITING_INPUT) in phase1_calls

    # --- Phase 2: approve ---
    session_id_str = str(paused_session_id)
    approval_id = uuid4()
    job_id = uuid4()

    record = {
        "id": str(approval_id),
        "status": "pending",
        "session_id": session_id_str,
        "recommendation_id": None,
        "reason": None,
        "actor": None,
    }
    updated = {**record, "status": "approved", "actor": "test-user"}

    mock_approvals_repo = MagicMock()
    mock_approvals_repo.get = AsyncMock(return_value=record)
    mock_approvals_repo.update = AsyncMock(return_value=updated)

    mock_jobs_repo = MagicMock()
    mock_jobs_repo.get_by_approval_id = AsyncMock(return_value={"id": str(job_id)})
    mock_jobs_repo.update_status = AsyncMock()

    phase2_calls: list[tuple[str, str]] = []
    execute_job_calls: list[UUID] = []

    async def _fake_session_update_phase2(sid: str, status: str) -> None:
        phase2_calls.append((sid, status))

    async def _fake_execute_job(jid: UUID, sse_queue: Any = None) -> dict[str, Any]:
        execute_job_calls.append(jid)
        return {}

    mock_orchestrator = MagicMock()
    mock_orchestrator.resume = AsyncMock()

    from apps.api.main import app
    import apps.api.routers.approvals as approvals_module

    app.dependency_overrides[approvals_module.get_orchestrator_dep] = (
        lambda: mock_orchestrator
    )
    try:
        with (
            patch.object(approvals_module, "_approvals_repo", mock_approvals_repo),
            patch(
                "packages.persistence.sessions_repo.DecisionSessionRepository.update_status",
                side_effect=_fake_session_update_phase2,
            ),
            patch(
                "packages.persistence.jobs_repo.JobsRepository",
                return_value=mock_jobs_repo,
            ),
            patch(
                "packages.agent.job_executor.execute_job",
                side_effect=_fake_execute_job,
            ),
            patch("apps.api.state.broadcasters", {}),
        ):
            transport = ASGITransport(app=app)  # type: ignore[arg-type]
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    f"/api/v1/approvals/{approval_id}/decision",
                    json={"decision": "approved"},
                    headers={"x-dev-user": "test-user"},
                )
    finally:
        app.dependency_overrides.pop(approvals_module.get_orchestrator_dep, None)

    assert resp.status_code == 200
    await _drain_pending_tasks()

    assert len(execute_job_calls) == 1 and execute_job_calls[0] == job_id
    assert (session_id_str, "completed") in phase2_calls, (
        f"approve must transition the session toward its completed terminal state; "
        f"got {phase2_calls}"
    )
    # The linked-job path dispatches execute_job directly — no LangGraph resume.
    assert mock_orchestrator.resume.call_count == 0


# ---------------------------------------------------------------------------
# 3. Reject path stays per contract
# ---------------------------------------------------------------------------


async def test_rejected_decision_marks_session_failed_per_contract() -> None:
    """POST decision='rejected' must mark the session 'failed' (migration-0014 vocabulary)."""
    from httpx import ASGITransport, AsyncClient

    session_id = str(uuid4())
    approval_id = uuid4()
    record = {
        "id": str(approval_id),
        "status": "pending",
        "session_id": session_id,
        "recommendation_id": None,
        "reason": None,
        "actor": None,
    }
    updated = {**record, "status": "rejected"}

    mock_approvals_repo = MagicMock()
    mock_approvals_repo.get = AsyncMock(return_value=record)
    mock_approvals_repo.update = AsyncMock(return_value=updated)

    mock_jobs_repo = MagicMock()
    mock_jobs_repo.get_by_approval_id = AsyncMock(return_value=None)

    session_status_calls: list[tuple[str, str]] = []

    async def _fake_session_update(sid: str, status: str) -> None:
        session_status_calls.append((sid, status))

    mock_orchestrator = MagicMock()
    mock_orchestrator.resume = AsyncMock()

    from apps.api.main import app
    import apps.api.routers.approvals as approvals_module

    app.dependency_overrides[approvals_module.get_orchestrator_dep] = (
        lambda: mock_orchestrator
    )
    try:
        with (
            patch.object(approvals_module, "_approvals_repo", mock_approvals_repo),
            patch(
                "packages.persistence.sessions_repo.DecisionSessionRepository.update_status",
                side_effect=_fake_session_update,
            ),
            patch(
                "packages.persistence.jobs_repo.JobsRepository",
                return_value=mock_jobs_repo,
            ),
        ):
            transport = ASGITransport(app=app)  # type: ignore[arg-type]
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    f"/api/v1/approvals/{approval_id}/decision",
                    json={"decision": "rejected", "reason": "not acceptable"},
                    headers={"x-dev-user": "test-user"},
                )
    finally:
        app.dependency_overrides.pop(approvals_module.get_orchestrator_dep, None)

    assert resp.status_code == 200
    assert (session_id, "failed") in session_status_calls, (
        f"reject must transition the session to 'failed'; got {session_status_calls}"
    )
    assert mock_orchestrator.resume.call_count == 0
