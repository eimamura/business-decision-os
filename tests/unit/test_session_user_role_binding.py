"""D-026 fix: session-driven control turns must bind hitl-safety tools.

Before the fix, ``packages/agent/orchestrator/runtime._run_agent`` built
``ToolContext`` without ``user_role``, silently defaulting to "analyst"
(packages/tools/base.py). ``ToolRegistry.filter_for_user_role("analyst", …)``
strips every ``safety_level="hitl"`` tool, so ``job_dispatch`` was never bound
on interactive session control turns — live-model runs hallucinated unbound
calls (flaky e2e) and ScriptedDriverModel raises on dispatch-less control
bindings.

Proven here:
1. The session path (_run_agent) now builds a manager-equivalent context.
2. With that role, the real registry + control allowlist binds job_dispatch
   (and request_approval) exactly as AgentRuntime.run computes bindings
   (packages/agent/runtime.py: list_for_role ∩ filter_for_user_role ∩ allowed_tools).
3. Analyst contexts still exclude all hitl tools from binding.
4. Manager does not over-grant: write-safety tools stay excluded.

Zero-network, zero-DB unit tier.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from packages.tools import create_tool_registry
from packages.tools.base import ToolContext


# ---------------------------------------------------------------------------
# Helpers — follow test_graph_node_model_name.py's _run_agent stubbing pattern
# ---------------------------------------------------------------------------

_captured_ctxs: list[Any] = []


class _CapturingAgent:
    """Fake specialist that records the ToolContext it was handed."""

    role = "control"

    async def run(self, task: Any, ctx: Any, agent_run_id: str = "") -> Any:
        from packages.agent.orchestrator.models import SpecialistResult

        _captured_ctxs.append(ctx)
        return SpecialistResult(
            task_id=task.task_id,
            agent_role=self.role,
            status="completed",
            output={"text": "done"},
            tool_calls_made=[],
            usage={"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
            error=None,
        )


async def _run_session_agent_and_capture_ctx() -> Any:
    """Invoke runtime._run_agent (the session-path executor) and return its ctx."""
    from packages.agent.orchestrator.runtime import _run_agent

    _captured_ctxs.clear()
    collected: list[dict[str, Any]] = []

    class _FakeOrchestrator:
        _llm_client = MagicMock(_model="stub-model")
        _tool_registry = MagicMock()
        _sse_queue = None

        async def _push(self, event: dict[str, Any], sse_queue: Any = None) -> None:
            collected.append(event)

    with (
        patch(
            "packages.agent.orchestrator.runtime._make_agent",
            return_value=_CapturingAgent(),
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
            orchestrator=_FakeOrchestrator(),
            session_id=uuid4(),
            agent_role="control",
            instruction="train the forecast model as a background job",
            context_payload={},
            allowed_tools=[],
        )

    assert _captured_ctxs, "fake agent must have been invoked with a ToolContext"
    return _captured_ctxs[0]


def _bound_tool_names(user_role: str) -> set[str]:
    """Recompute AgentRuntime.run's binding math with the real registry.

    Mirrors packages/agent/runtime.py:
        agent_role_tools   = registry.list_for_role(agent_role)
        user_filtered      = registry.filter_for_user_role(ctx.user_role, agent_role_tools)
        tool_objects       = [t for t in user_filtered if t.name in allowed_tools]
    """
    from packages.agent.orchestrator.runtime import _default_tools

    registry = create_tool_registry()
    allowed_tools = set(_default_tools("control"))
    user_filtered = registry.filter_for_user_role(
        user_role, registry.list_for_role("control")
    )
    return {t.name for t in user_filtered if t.name in allowed_tools}


# ---------------------------------------------------------------------------
# 1. Session path carries an explicit manager-equivalent user_role
# ---------------------------------------------------------------------------


async def test_session_path_builds_manager_user_role_context() -> None:
    """_run_agent must pass SESSION_USER_ROLE ("manager") into ToolContext."""
    from packages.agent.orchestrator.runtime import SESSION_USER_ROLE

    ctx = await _run_session_agent_and_capture_ctx()
    assert ctx.user_role == "manager"
    assert ctx.user_role == SESSION_USER_ROLE


async def test_session_user_role_constant_is_manager() -> None:
    """The constant itself pins 'manager' — the read_only+hitl tier."""
    from packages.agent.orchestrator.runtime import SESSION_USER_ROLE

    assert SESSION_USER_ROLE == "manager"


# ---------------------------------------------------------------------------
# 2. With the session role, job_dispatch is bound on control turns
# ---------------------------------------------------------------------------


def test_manager_context_binds_job_dispatch_on_control_turns() -> None:
    """job_dispatch must survive Layer 1 + allowlist + intent-subset filtering."""
    bound = _bound_tool_names("manager")
    assert "job_dispatch" in bound, (
        f"job_dispatch must be bound for session control turns; bound={sorted(bound)}"
    )


def test_manager_context_binds_request_approval_too() -> None:
    """request_approval is the other registered hitl tool and must bind as well."""
    from packages.tools.base import ToolRegistry

    registry = create_tool_registry()
    assert registry._tools["request_approval"].safety_level == "hitl"
    bound = _bound_tool_names("manager")
    assert "request_approval" in bound


# ---------------------------------------------------------------------------
# 3. Analyst semantics unchanged — hitl tools still excluded
# ---------------------------------------------------------------------------


def test_analyst_context_excludes_all_hitl_tools_from_binding() -> None:
    """filter_for_user_role('analyst') must strip every hitl-safety tool."""
    registry = create_tool_registry()
    hitl_names = {
        t.name
        for t in registry.list_for_role("control")
        if t.safety_level == "hitl"
    }
    assert hitl_names, "registry must contain at least one hitl tool for this proof"
    bound = _bound_tool_names("analyst")
    assert bound.isdisjoint(hitl_names), (
        f"analyst contexts must not bind hitl tools; leaked={sorted(bound & hitl_names)}"
    )
    assert "job_dispatch" not in bound
    assert "request_approval" not in bound


def test_default_toolcontext_user_role_remains_analyst() -> None:
    """The ToolContext default stays 'analyst' — only the session path changed."""
    ctx = ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="control",
        actor="test",
        correlation_id=uuid4(),
    )
    assert ctx.user_role == "analyst"


# ---------------------------------------------------------------------------
# 4. Manager does not over-grant write tools (no blanket admin)
# ---------------------------------------------------------------------------


def test_manager_context_excludes_write_safety_tools() -> None:
    """Choosing manager (not admin) keeps write-level tools out of chat bindings."""
    registry = create_tool_registry()
    write_names = {
        t.name
        for t in registry.list_for_role("control")
        if t.safety_level == "write"
    }
    assert write_names, "registry must contain at least one write tool for this proof"
    bound = _bound_tool_names("manager")
    assert bound.isdisjoint(write_names), (
        f"manager sessions must not inline-bind write tools; leaked={sorted(bound & write_names)}"
    )
