from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage

from packages.agent.llm import LLMMessage, LLMToolSpec
from packages.agent.runtime import AgentRuntime


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


class _FakeToolRegistry:
    def __init__(self) -> None:
        pass

    def list_for_role(self, role: str) -> list[Any]:
        return []

    def filter_for_user_role(self, user_role: str, tools: list[Any]) -> list[Any]:
        return tools

    def get(self, name: str) -> Any | None:
        return None


def _make_runtime() -> AgentRuntime:
    return AgentRuntime(
        name="test",
        role="control",
        llm_client=MagicMock(),
        tool_registry=_FakeToolRegistry(),
    )


def _make_agent_state(
    response: Any = None,
    tool_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "messages": [LLMMessage(role="user", content="q")],
        "response": response,
        "iteration": 0,
        "status": "running",
        "tool_results": tool_results or [],
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
        "error": None,
        "pending_hitl_approval_id": None,
        "pending_hitl_job_id": None,
        "compressed_messages": None,
    }


# ---------------------------------------------------------------------------
# T-372 test cases
# ---------------------------------------------------------------------------


async def test_call_model_node_uses_bind_tools_when_lc_model_set() -> None:
    """_call_model_node calls _lc_model.bind_tools when llm_tools are provided."""
    runtime = _make_runtime()

    bound_model = MagicMock()
    bound_model.ainvoke = AsyncMock(
        return_value=AIMessage(content="hello", tool_calls=[])
    )

    lc_model = MagicMock()
    lc_model.bind_tools.return_value = bound_model
    # model attribute needed for response.model
    lc_model.model = "langchain-test"
    runtime._lc_model = lc_model

    tool_spec = LLMToolSpec(
        name="my_tool",
        description="A test tool",
        input_schema={"type": "object", "properties": {}},
    )
    state = _make_agent_state()
    config: dict[str, Any] = {
        "configurable": {
            "task": MagicMock(task_id=uuid4()),
            "llm_tools": [tool_spec],
        }
    }

    result = await runtime._call_model_node(state, config)  # type: ignore[arg-type]

    lc_model.bind_tools.assert_called_once()
    bound_model.ainvoke.assert_called_once()
    # No tool calls returned — finish_reason should be "stop"
    assert result["response"].finish_reason == "stop"


async def test_call_model_node_maps_tool_calls_args_to_input() -> None:
    """AIMessage.tool_calls[*].args are remapped to .input in the response."""
    runtime = _make_runtime()

    ai_msg = AIMessage(
        content="",
        tool_calls=[{"name": "my_tool", "args": {"param": "val"}, "id": "tc-1"}],
    )

    bound_model = MagicMock()
    bound_model.ainvoke = AsyncMock(return_value=ai_msg)

    lc_model = MagicMock()
    lc_model.bind_tools.return_value = bound_model
    lc_model.model = "langchain-test"
    runtime._lc_model = lc_model

    tool_spec = LLMToolSpec(
        name="my_tool",
        description="A test tool",
        input_schema={"type": "object", "properties": {}},
    )
    state = _make_agent_state()
    config: dict[str, Any] = {
        "configurable": {
            "task": MagicMock(task_id=uuid4()),
            "llm_tools": [tool_spec],
        }
    }

    result = await runtime._call_model_node(state, config)  # type: ignore[arg-type]

    response = result["response"]
    assert len(response.tool_calls) == 1
    tc = response.tool_calls[0]
    assert tc["name"] == "my_tool"
    assert tc["input"] == {"param": "val"}
    assert tc["id"] == "tc-1"


async def test_verify_findings_is_rule_based() -> None:
    """_verify_findings_node uses rule-based logic — no LLM call."""
    runtime = _make_runtime()

    lc_model = MagicMock()
    lc_model.ainvoke = AsyncMock(return_value=AIMessage(content="pass — grounded"))
    runtime._lc_model = lc_model

    mock_response = MagicMock()
    mock_response.text = "The stockout risk analysis is complete. Three SKUs are at risk."

    state = _make_agent_state(response=mock_response)
    ctx_mock = MagicMock()
    ctx_mock.agent_step_id = None
    config: dict[str, Any] = {
        "configurable": {
            "ctx": ctx_mock,
        }
    }

    result = await runtime._verify_findings_node(state, config)  # type: ignore[arg-type]

    lc_model.ainvoke.assert_not_called()
    assert result["status"] == "completed"


async def test_call_model_node_raises_runtime_error_when_no_lc_model() -> None:
    """_call_model_node raises RuntimeError when _lc_model is None (legacy fallback removed)."""
    import pytest

    from langgraph.errors import GraphInterrupt

    runtime = _make_runtime()
    runtime._lc_model = None

    state = _make_agent_state()
    config: dict[str, Any] = {
        "configurable": {
            "task": MagicMock(task_id=uuid4()),
            "llm_tools": [],
        }
    }

    with pytest.raises(RuntimeError, match="AgentRuntime requires model_registry"):
        await runtime._call_model_node(state, config)  # type: ignore[arg-type]
