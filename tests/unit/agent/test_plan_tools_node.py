"""T-419: Unit tests for AgentRuntime._plan_tools_node (Gap 1 — P64 B-05).

Verifies:
- tool_plan is populated for domain_analysis, cross_domain_analysis, and decision_support intents
- plan_tools node is skipped (returns {}) for supply_chain and lookup intents
- plan_tools node is skipped when tool_plan is already populated
"""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from langchain_core.messages import AIMessage

from packages.agent.orchestrator.models import SpecialistTask
from packages.agent.runtime import AgentRuntime, ToolPlan


def _make_lc_model_returning_plan(tool_plan_json: str) -> Any:
    """Create a fake LC model that returns a JSON plan string."""
    lc_model = MagicMock()
    ai_msg = AIMessage(content=tool_plan_json)
    lc_model.ainvoke = AsyncMock(return_value=ai_msg)
    return lc_model


def _make_runtime(lc_model: Any) -> AgentRuntime:
    registry = MagicMock()
    registry.get.return_value = lc_model
    tool_reg = MagicMock()
    tool_reg.list_for_role.return_value = []
    tool_reg.filter_for_user_role.return_value = []
    return AgentRuntime(
        name="test_agent",
        role="control",
        llm_client=None,
        tool_registry=tool_reg,
        sse_queue=None,
        system_prompt="Test.",
        model_registry=registry,
    )


def _make_state(tool_plan: list[ToolPlan] | None = None) -> dict[str, Any]:
    from packages.agent.llm import LLMMessage
    return {
        "messages": [LLMMessage(role="user", content="analyze demand")],
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
        "compressed_messages": None,
        "tool_plan": tool_plan or [],
    }


def _make_task_with_intent(intent_category: str) -> SpecialistTask:
    return SpecialistTask(
        task_id=uuid4(),
        instruction="Analyze demand vs supply gap and recommend actions.",
        context_payload={"intent": {"category": intent_category}},
        allowed_tools=[],
    )


def _make_config(task: SpecialistTask, llm_tools: list[Any] | None = None) -> dict[str, Any]:
    return {
        "configurable": {
            "task": task,
            "llm_tools": llm_tools or [],
            "agent_run_id": "run-test",
        }
    }


_SAMPLE_PLAN_JSON = json.dumps([
    {"tool": "nl_query", "purpose": "Get demand data", "depends_on": []},
    {"tool": "list_stockout_risk", "purpose": "Identify at-risk SKUs", "depends_on": ["nl_query"]},
])


@pytest.mark.parametrize("intent", [
    "domain_analysis",
    "cross_domain_analysis",
    "decision_support",
])
async def test_plan_tools_node_populates_tool_plan_for_complex_intents(intent: str) -> None:
    """plan_tools node must populate state['tool_plan'] for complex intents."""
    lc_model = _make_lc_model_returning_plan(_SAMPLE_PLAN_JSON)
    runtime = _make_runtime(lc_model)
    state = _make_state()
    task = _make_task_with_intent(intent)
    config = _make_config(task)

    result = await runtime._plan_tools_node(state, config)  # type: ignore[arg-type]

    assert "tool_plan" in result, f"Expected tool_plan in result for intent '{intent}'"
    plan = result["tool_plan"]
    assert isinstance(plan, list), "tool_plan must be a list"
    assert len(plan) == 2, f"Expected 2 plan steps, got {len(plan)}"
    assert plan[0]["tool"] == "nl_query"
    assert plan[1]["tool"] == "list_stockout_risk"
    assert plan[1]["depends_on"] == ["nl_query"]


@pytest.mark.parametrize("intent", [
    "supply_chain",
    "lookup",
    "reporting",
    "",
])
async def test_plan_tools_node_skipped_for_simple_intents(intent: str) -> None:
    """plan_tools node must return {} (skip) for non-complex intents."""
    lc_model = _make_lc_model_returning_plan(_SAMPLE_PLAN_JSON)
    runtime = _make_runtime(lc_model)
    state = _make_state()
    task = _make_task_with_intent(intent)
    config = _make_config(task)

    result = await runtime._plan_tools_node(state, config)  # type: ignore[arg-type]

    assert result == {}, (
        f"plan_tools node should return {{}} for intent '{intent}', got: {result}"
    )
    # LLM must NOT be called for non-complex intents
    lc_model.ainvoke.assert_not_called()


async def test_plan_tools_node_skipped_when_already_populated() -> None:
    """plan_tools node must return {} when state['tool_plan'] is already populated."""
    existing_plan = [
        ToolPlan(tool="nl_query", purpose="already planned", depends_on=[])
    ]
    lc_model = _make_lc_model_returning_plan(_SAMPLE_PLAN_JSON)
    runtime = _make_runtime(lc_model)
    state = _make_state(tool_plan=existing_plan)
    task = _make_task_with_intent("domain_analysis")
    config = _make_config(task)

    result = await runtime._plan_tools_node(state, config)  # type: ignore[arg-type]

    assert result == {}, (
        "plan_tools node must skip when tool_plan is already populated"
    )
    lc_model.ainvoke.assert_not_called()
