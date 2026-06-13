"""T-074: Unit test — HITL interrupt/resume via LangGraph.

Full HITL cycle using MemorySaver (no real DB required).  Verifies:
1. Graph suspends at wait_for_approval with __interrupt__ in the state.
2. ApprovalsRepository.create is called exactly once (not twice).
3. After resume via astream(None, ...), execute_job() is called.
4. The final SessionResponse is returned by resume().
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from packages.agent.llm import LLMMessage, LLMResponse, LLMToolSpec
from packages.agent.orchestrator.models import SpecialistTask
from packages.agent.runtime import AgentRuntime, AgentState
from tests.unit.helpers import (
    FakeLCModel,
    make_llm_usage,
    make_model_registry,
    make_stop_response,
)


# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------


def _tool_use_response(tool_name: str, tool_input: dict[str, Any]) -> LLMResponse:
    call_id = str(uuid4())
    return LLMResponse(
        text="",
        tool_calls=[{"id": call_id, "name": tool_name, "input": tool_input}],
        finish_reason="tool_use",
        usage=make_llm_usage(),
        model="claude-sonnet-4-6-test",
        request_id=str(uuid4()),
        latency_ms=1,
    )


class _SequenceLLMClient:
    """Returns a fixed sequence of LLMResponse objects, then falls back to stop."""

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self._model = "sequence-stub"
        self.call_count = 0

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: Any = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        prompt_cache: bool = True,
        agent_step_id: Any = None,
        specialist_role: Any = None,
    ) -> LLMResponse:
        self.call_count += 1
        if self._responses:
            return self._responses.pop(0)
        return make_stop_response("fallback")


class _FakeHITLTool:
    """Tool with safety_level == 'hitl'."""

    name = "request_approval"
    description = "Requests human approval"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {"action_summary": {"type": "string"}},
        "required": ["action_summary"],
    }
    output_schema: dict[str, Any] = {}
    safety_level = "hitl"

    async def handle(self, input: dict[str, Any], ctx: Any) -> Any:
        raise AssertionError("handle() must not be called for a HITL tool")


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


def _make_task(allowed_tools: list[str] | None = None) -> SpecialistTask:
    return SpecialistTask(
        task_id=uuid4(),
        instruction="Approve action X",
        context_payload={},
        allowed_tools=allowed_tools or ["request_approval"],
    )


def _build_initial_state(
    initial_messages: list[LLMMessage],
) -> AgentState:
    return AgentState(
        messages=initial_messages,
        response=None,
        input_tokens=0,
        output_tokens=0,
        cost_usd=0.0,
        tool_results=[],
        iteration=0,
        status="running",
        error=None,
        pending_hitl_approval_id=None,
        pending_hitl_job_id=None,
        compressed_messages=None,
    )


def _build_system_messages() -> list[LLMMessage]:
    ephemeral: dict[str, Any] = {"type": "ephemeral"}
    role_text = (
        "Role: data_engineer\nAvailable tools: 1\n"
        "Always respond in the same language the user writes in."
    )
    return [
        LLMMessage(
            role="system",
            content="",
            content_blocks=[
                {"type": "text", "text": "You are a test specialist.", "cache_control": ephemeral},
                {"type": "text", "text": "", "cache_control": ephemeral},
                {"type": "text", "text": role_text},
            ],
        ),
        LLMMessage(role="user", content="Approve action X"),
    ]


# ---------------------------------------------------------------------------
# T-074 tests
# ---------------------------------------------------------------------------


async def test_hitl_graph_suspends_at_wait_for_approval() -> None:
    """After the LLM requests a HITL tool, the graph must suspend with __interrupt__."""
    from unittest.mock import MagicMock

    tool_input = {"action_summary": "Reorder 500 units of SKU-A"}
    lc_model = FakeLCModel([_tool_use_response("request_approval", tool_input)])
    registry = _FakeToolRegistry([_FakeHITLTool()])
    runtime = AgentRuntime(
        name="test_agent",
        role="data_engineer",
        llm_client=MagicMock(),
        tool_registry=registry,
        sse_queue=None,
        system_prompt="You are a test specialist.",
        model_registry=make_model_registry(lc_model),
    )
    task = _make_task()
    ctx = _FakeToolContext()

    from langgraph.checkpoint.memory import MemorySaver

    checkpointer = MemorySaver()
    graph = runtime._build_graph(checkpointer)
    thread_id = str(uuid4())
    run_config: dict[str, Any] = {
        "configurable": {
            "thread_id": thread_id,
            "task": task,
            "ctx": ctx,
            "llm_tools": [
                LLMToolSpec(
                    name=_FakeHITLTool.name,
                    description=_FakeHITLTool.description,
                    input_schema=_FakeHITLTool.input_schema,
                )
            ],
            "sse_queue": None,
        }
    }

    initial_state = _build_initial_state(_build_system_messages())

    mock_repo = MagicMock()
    expected_approval_id = str(uuid4())
    mock_repo.create = AsyncMock(return_value={"id": expected_approval_id})

    with patch(
        "packages.persistence.approvals_repo.ApprovalsRepository",
        return_value=mock_repo,
    ):
        result = await graph.ainvoke(initial_state, config=run_config)

    # Confirm graph is paused at wait_for_approval checkpoint
    assert "__interrupt__" in result, (
        "Graph must suspend with __interrupt__ when HITL tool is encountered"
    )
    interrupt_values = result["__interrupt__"]
    assert len(interrupt_values) >= 1
    assert interrupt_values[0].value.get("tool_name") == "request_approval"
    assert interrupt_values[0].value.get("approval_id") == expected_approval_id


async def test_hitl_approvals_create_called_exactly_once() -> None:
    """ApprovalsRepository.create must be called exactly once — not twice — during HITL."""
    from unittest.mock import MagicMock

    tool_input = {"action_summary": "Critical shipment release"}
    lc_model = FakeLCModel([_tool_use_response("request_approval", tool_input)])
    registry = _FakeToolRegistry([_FakeHITLTool()])
    runtime = AgentRuntime(
        name="test_agent",
        role="data_engineer",
        llm_client=MagicMock(),
        tool_registry=registry,
        sse_queue=None,
        system_prompt="You are a test specialist.",
        model_registry=make_model_registry(lc_model),
    )
    task = _make_task()
    ctx = _FakeToolContext()

    from langgraph.checkpoint.memory import MemorySaver

    checkpointer = MemorySaver()
    graph = runtime._build_graph(checkpointer)
    run_config: dict[str, Any] = {
        "configurable": {
            "thread_id": str(uuid4()),
            "task": task,
            "ctx": ctx,
            "llm_tools": [
                LLMToolSpec(
                    name=_FakeHITLTool.name,
                    description=_FakeHITLTool.description,
                    input_schema=_FakeHITLTool.input_schema,
                )
            ],
            "sse_queue": None,
        }
    }

    initial_state = _build_initial_state(_build_system_messages())

    mock_repo = MagicMock()
    mock_repo.create = AsyncMock(return_value={"id": str(uuid4())})

    with patch(
        "packages.persistence.approvals_repo.ApprovalsRepository",
        return_value=mock_repo,
    ):
        await graph.ainvoke(initial_state, config=run_config)

    # Must be called exactly once — not twice
    assert mock_repo.create.call_count == 1, (
        f"ApprovalsRepository.create must be called exactly once, "
        f"got {mock_repo.create.call_count} calls"
    )


async def test_hitl_resume_calls_execute_job() -> None:
    """After interrupt/resume cycle with job_dispatch tool, execute_job must be called.

    Uses job_dispatch (not request_approval) because only job_dispatch causes
    prepare_hitl to create a JobsRepository row and set pending_hitl_job_id.
    The execute_tools node calls execute_job (not tool.handle) when pending_hitl_job_id
    is set.
    """
    import uuid

    job_id = str(uuid.uuid4())
    approval_id = str(uuid.uuid4())

    # job_dispatch tool input — matches the HITL path in prepare_hitl
    tool_input = {
        "job_type": "simulation",
        "description": "Run demand simulation",
        "params": {"sku": "A", "horizon": 30},
    }

    class _FakeJobDispatchTool:
        name = "job_dispatch"
        description = "Dispatches a job requiring approval"
        input_schema: dict[str, Any] = {
            "type": "object",
            "properties": {
                "job_type": {"type": "string"},
                "description": {"type": "string"},
                "params": {"type": "object"},
            },
        }
        output_schema: dict[str, Any] = {}
        safety_level = "hitl"

        async def handle(self, input: dict[str, Any], ctx: Any) -> Any:
            raise AssertionError("handle() must not be called for a HITL tool")

    from unittest.mock import MagicMock

    lc_model = FakeLCModel([
        _tool_use_response("job_dispatch", tool_input),
        make_stop_response("Simulation job dispatched successfully."),
        make_stop_response("pass"),
    ])
    registry = _FakeToolRegistry([_FakeJobDispatchTool()])
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
        task_id=uuid.uuid4(),
        instruction="Dispatch simulation job",
        context_payload={},
        allowed_tools=["job_dispatch"],
    )
    ctx = _FakeToolContext()

    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.types import Command

    checkpointer = MemorySaver()
    graph = runtime._build_graph(checkpointer)
    thread_id = str(uuid.uuid4())
    run_config: dict[str, Any] = {
        "configurable": {
            "thread_id": thread_id,
            "task": task,
            "ctx": ctx,
            "llm_tools": [
                LLMToolSpec(
                    name="job_dispatch",
                    description="Dispatches a job requiring approval",
                    input_schema=_FakeJobDispatchTool.input_schema,
                )
            ],
            "sse_queue": None,
        }
    }

    initial_state = _build_initial_state(_build_system_messages())

    mock_approvals_repo = MagicMock()
    mock_approvals_repo.create = AsyncMock(return_value={"id": approval_id})

    mock_jobs_repo = MagicMock()
    mock_jobs_repo.create = AsyncMock(return_value={"id": job_id})

    execute_job_calls: list[Any] = []

    async def _fake_execute_job(job_id_arg: Any, sse_queue: Any = None) -> dict[str, Any]:
        execute_job_calls.append(str(job_id_arg))
        return {"result_json": {"status": "completed", "output": "simulation done"}}

    with (
        patch(
            "packages.persistence.approvals_repo.ApprovalsRepository",
            return_value=mock_approvals_repo,
        ),
        patch(
            "packages.persistence.jobs_repo.JobsRepository",
            return_value=mock_jobs_repo,
        ),
        patch(
            "packages.agent.job_executor.execute_job",
            side_effect=_fake_execute_job,
        ),
    ):
        # Phase 1: initial invocation — graph must suspend at wait_for_approval
        result = await graph.ainvoke(initial_state, config=run_config)

    assert "__interrupt__" in result, "Graph must suspend with __interrupt__ before resume"

    # pending_hitl_job_id must be set (only when tool is job_dispatch)
    pending_job_id = result.get("pending_hitl_job_id")
    assert pending_job_id is not None, (
        "pending_hitl_job_id must be set after prepare_hitl for job_dispatch tool"
    )

    with (
        patch(
            "packages.persistence.approvals_repo.ApprovalsRepository",
            return_value=mock_approvals_repo,
        ),
        patch(
            "packages.persistence.jobs_repo.JobsRepository",
            return_value=mock_jobs_repo,
        ),
        patch(
            "packages.agent.job_executor.execute_job",
            side_effect=_fake_execute_job,
        ),
    ):
        # Phase 2: resume via Command(resume='approved') — correct LangGraph 1.x pattern
        resume_result = await graph.ainvoke(
            Command(resume="approved"),
            config=run_config,
        )
        # Yield to the event loop so the background execute_job task gets a chance to run
        # (T-601: execute_job is now dispatched via asyncio.create_task, not awaited directly).
        await asyncio.sleep(0)

    # execute_job must have been scheduled and run (not tool.handle)
    assert len(execute_job_calls) >= 1, (
        "execute_job must be called when resuming after HITL job_dispatch approval"
    )
    # The job_id passed to execute_job must match what prepare_hitl stored
    assert execute_job_calls[0] == pending_job_id, (
        f"execute_job called with wrong job_id: got {execute_job_calls[0]!r}, "
        f"expected {pending_job_id!r}"
    )
    # Graph must have completed
    assert resume_result.get("status") == "completed", (
        f"Expected status='completed' after resume, got: {resume_result.get('status')}"
    )


async def test_hitl_handle_never_called_on_resume() -> None:
    """tool.handle() must never be invoked for HITL tools — even after Command(resume=...)."""
    import uuid

    handle_calls: list[Any] = []
    job_id = str(uuid.uuid4())
    approval_id = str(uuid.uuid4())

    tool_input = {
        "job_type": "simulation",
        "description": "Dangerous action",
        "params": {},
    }

    class _SentinelJobDispatchTool:
        name = "job_dispatch"
        description = "Dispatches a job requiring approval"
        input_schema: dict[str, Any] = {
            "type": "object",
            "properties": {
                "job_type": {"type": "string"},
                "description": {"type": "string"},
                "params": {"type": "object"},
            },
        }
        output_schema: dict[str, Any] = {}
        safety_level = "hitl"

        async def handle(self, input: dict[str, Any], ctx: Any) -> Any:
            handle_calls.append(True)
            raise AssertionError("handle() must not be called for a HITL tool")

    from unittest.mock import MagicMock

    lc_model = FakeLCModel([
        _tool_use_response("job_dispatch", tool_input),
        make_stop_response("Action completed."),
        make_stop_response("pass"),
    ])
    registry = _FakeToolRegistry([_SentinelJobDispatchTool()])
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
        task_id=uuid.uuid4(),
        instruction="Execute dangerous action",
        context_payload={},
        allowed_tools=["job_dispatch"],
    )
    ctx = _FakeToolContext()

    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.types import Command

    checkpointer = MemorySaver()
    graph = runtime._build_graph(checkpointer)
    thread_id = str(uuid.uuid4())
    run_config: dict[str, Any] = {
        "configurable": {
            "thread_id": thread_id,
            "task": task,
            "ctx": ctx,
            "llm_tools": [
                LLMToolSpec(
                    name="job_dispatch",
                    description="Dispatches a job requiring approval",
                    input_schema={"type": "object"},
                )
            ],
            "sse_queue": None,
        }
    }

    initial_state = _build_initial_state(_build_system_messages())

    mock_approvals_repo = MagicMock()
    mock_approvals_repo.create = AsyncMock(return_value={"id": approval_id})
    mock_jobs_repo = MagicMock()
    mock_jobs_repo.create = AsyncMock(return_value={"id": job_id})

    async def _fake_execute_job(job_id_arg: Any, sse_queue: Any = None) -> dict[str, Any]:
        return {"result_json": {"status": "done"}}

    _approvals_path = "packages.persistence.approvals_repo.ApprovalsRepository"
    _jobs_path = "packages.persistence.jobs_repo.JobsRepository"
    _execute_path = "packages.agent.job_executor.execute_job"

    with (
        patch(_approvals_path, return_value=mock_approvals_repo),
        patch(_jobs_path, return_value=mock_jobs_repo),
        patch(_execute_path, side_effect=_fake_execute_job),
    ):
        # Phase 1: invoke — suspends at wait_for_approval
        await graph.ainvoke(initial_state, config=run_config)

    with (
        patch(_approvals_path, return_value=mock_approvals_repo),
        patch(_jobs_path, return_value=mock_jobs_repo),
        patch(_execute_path, side_effect=_fake_execute_job),
    ):
        # Phase 2: resume via Command(resume='approved')
        await graph.ainvoke(Command(resume="approved"), config=run_config)
        # Yield to the event loop so the background execute_job task gets a chance to run
        # (T-601: execute_job is now dispatched via asyncio.create_task, not awaited directly).
        await asyncio.sleep(0)

    # tool.handle() must never have been called — execute_job is used instead
    assert handle_calls == [], "tool.handle() must never be called for a HITL tool"
