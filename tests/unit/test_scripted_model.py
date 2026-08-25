"""Unit tests for the D-026 deterministic e2e seam.

Covers ScriptedDriverModel behaviour (structured output, job_dispatch
sequence, determinism) and its LLM_DRIVER=scripted wiring in
create_model_registry.

Zero-network rule: constructing ChatOllama/ScriptedDriverModel makes no HTTP
calls; all invocations are local computation only.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from packages.agent.llm import LLMMessage, LLMToolSpec
from packages.agent.model_registry import ModelRegistry, create_model_registry
from packages.agent.orchestrator.models import (
    AskUserDecision,
    GoalEvaluation,
    GoalSpec,
    SessionIntent,
)
from packages.agent.runtime import GroundednessVerdict
from packages.agent.scripted_model import (
    ScriptedDriverModel,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_JOB_DISPATCH_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "job_type": {
            "type": "string",
            "enum": [
                "simulate", "inventory_simulation", "optimize", "forecast",
                "train_forecast",
            ],
        },
        "params": {"type": "object"},
        "description": {"type": "string"},
    },
    "required": ["job_type", "params", "description"],
}

_CONTROL_TOOL_SPECS = [
    LLMToolSpec(
        name="list_stockout_risk",
        description="List SKUs at stockout risk",
        input_schema={"type": "object", "properties": {}},
    ),
    LLMToolSpec(
        name="job_dispatch",
        description="Dispatch a background job pending approval",
        input_schema=_JOB_DISPATCH_INPUT_SCHEMA,
    ),
]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _control_tools_dicts() -> list[dict[str, Any]]:
    """OpenAI-format tool dicts exactly as _call_model_node builds them."""
    return [
        {
            "type": "function",
            "function": {
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.input_schema,
            },
        }
        for spec in _CONTROL_TOOL_SPECS
    ]


def _scripted_registry() -> ModelRegistry:
    model = ScriptedDriverModel()
    return ModelRegistry({"orchestrator": model, "planner": model, "control": model})


def _make_agent_runtime() -> Any:
    from packages.agent.runtime import AgentRuntime

    registry = _scripted_registry()
    return AgentRuntime(
        name="control-agent",
        role="control",
        llm_client=registry.get("control"),
        tool_registry=MagicMock(),
        model_registry=registry,
    )


# ---------------------------------------------------------------------------
# ScriptedDriverModel — control-path tool-call sequence
# ---------------------------------------------------------------------------


async def test_control_call_without_tool_result_emits_job_dispatch_tool_call(
    anyio_backend: str,
) -> None:
    model = ScriptedDriverModel().bind_tools(_control_tools_dicts())
    ai_msg = await model.ainvoke([
        SystemMessage("You are a control specialist."),
        HumanMessage("Run a demand simulation for SKU-001."),
    ])
    assert len(ai_msg.tool_calls) == 1
    call = ai_msg.tool_calls[0]
    assert call["name"] == "job_dispatch"
    assert call["id"]  # LangGraph tool-result correlation requires an id


async def test_job_dispatch_args_are_schema_conformant(anyio_backend: str) -> None:
    model = ScriptedDriverModel().bind_tools(_control_tools_dicts())
    ai_msg = await model.ainvoke([HumanMessage("Run a simulation.")])
    args = ai_msg.tool_calls[0]["args"]
    # Conforms to JobDispatchTool.input_schema (required keys + enum value).
    assert set(args) >= {"job_type", "params", "description"}
    assert args["job_type"] in _JOB_DISPATCH_INPUT_SCHEMA["properties"]["job_type"]["enum"]
    assert isinstance(args["params"], dict)
    assert isinstance(args["description"], str) and args["description"]


async def test_control_call_after_tool_result_emits_final_text(anyio_backend: str) -> None:
    """Post-approval resume: ToolMessage present → final prose, zero tool calls."""
    bound = ScriptedDriverModel().bind_tools(_control_tools_dicts())
    first = await bound.ainvoke([HumanMessage("Run a simulation.")])
    tool_call = first.tool_calls[0]
    resumed = await bound.ainvoke([
        HumanMessage("Run a simulation."),
        first,  # assistant turn carrying the tool call
        ToolMessage(content='{"job_id": "j-1", "status": "queued"}', tool_call_id=tool_call["id"]),
    ])
    assert resumed.tool_calls == []
    assert isinstance(resumed.content, str)
    assert len(resumed.content.strip()) > 0


async def test_bare_invoke_without_bound_tools_returns_text(anyio_backend: str) -> None:
    model = ScriptedDriverModel()
    ai_msg = await model.ainvoke([SystemMessage("summarize"), HumanMessage("data")])
    assert ai_msg.tool_calls == []
    assert isinstance(ai_msg.content, str) and ai_msg.content.strip()


# ---------------------------------------------------------------------------
# ScriptedDriverModel — structured-output bindings
# ---------------------------------------------------------------------------


async def test_structured_output_session_intent_is_valid_instance(
    anyio_backend: str,
) -> None:
    result = await ScriptedDriverModel().with_structured_output(SessionIntent).ainvoke(
        [SystemMessage("intent"), HumanMessage("Run a simulation.")]
    )
    assert isinstance(result, SessionIntent)
    assert result.category == "supply_chain"  # routes single_agent → control agent
    assert result.confidence == pytest.approx(1.0)


async def test_structured_output_goal_spec_derives_goal_text_from_query(
    anyio_backend: str,
) -> None:
    query = "Run an inventory optimization simulation for SKU-A42."
    result = await ScriptedDriverModel().with_structured_output(GoalSpec).ainvoke(
        [SystemMessage("goal"), HumanMessage(query)]
    )
    assert isinstance(result, GoalSpec)
    assert result.goal_text == query
    assert result.success_criteria == []


async def test_structured_output_ask_user_decision_needs_no_input(
    anyio_backend: str,
) -> None:
    result = await (
        ScriptedDriverModel().with_structured_output(AskUserDecision).ainvoke(
            [SystemMessage("ask user"), HumanMessage("{}")]
        )
    )
    assert isinstance(result, AskUserDecision)
    assert result.needs_input is False


async def test_structured_output_groundedness_verdict_is_grounded(
    anyio_backend: str,
) -> None:
    result = await (
        ScriptedDriverModel().with_structured_output(GroundednessVerdict).ainvoke(
            [SystemMessage("verify"), HumanMessage("answer")]
        )
    )
    assert isinstance(result, GroundednessVerdict)
    assert result.grounded is True
    assert result.unsupported_claims == []


async def test_structured_output_goal_evaluation_is_satisfied(
    anyio_backend: str,
) -> None:
    result = await (
        ScriptedDriverModel().with_structured_output(GoalEvaluation).ainvoke(
            [SystemMessage("evaluate"), HumanMessage("{}")]
        )
    )
    assert isinstance(result, GoalEvaluation)
    assert result.satisfied is True


async def test_unknown_structured_output_schema_raises_value_error(
    anyio_backend: str,
) -> None:
    class UnrecognizedSchema:
        name = "UnrecognizedSchema"

    model = ScriptedDriverModel().bind_tools(
        [UnrecognizedSchema()], tool_choice="any"
    )
    with pytest.raises(ValueError, match="UnrecognizedSchema"):
        await model.ainvoke([HumanMessage("hello")])


# ---------------------------------------------------------------------------
# Determinism (temperature=0 invariant)
# ---------------------------------------------------------------------------


async def test_repeated_invocations_are_identical(anyio_backend: str) -> None:
    bound = ScriptedDriverModel().bind_tools(_control_tools_dicts())
    messages = [SystemMessage("s"), HumanMessage("Run a simulation.")]
    first = await bound.ainvoke(messages)
    second = await bound.ainvoke(messages)
    assert first.tool_calls == second.tool_calls
    assert first.content == second.content


# ---------------------------------------------------------------------------
# Registry wiring — LLM_DRIVER=scripted
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("role", ["orchestrator", "planner", "control"])
def test_registry_llm_driver_scripted_all_roles_scripted(
    monkeypatch: pytest.MonkeyPatch, role: str
) -> None:
    monkeypatch.setenv("LLM_DRIVER", "scripted")
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    registry = create_model_registry()
    assert isinstance(registry.get(role), ScriptedDriverModel)


def test_registry_llm_driver_scripted_overrides_llm_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_DRIVER", "scripted")
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
    registry = create_model_registry()
    assert isinstance(registry.get("control"), ScriptedDriverModel)


def test_registry_unknown_llm_driver_raises_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_DRIVER", "fancy_driver")
    with pytest.raises(RuntimeError, match="Unsupported LLM_DRIVER"):
        create_model_registry()


def test_registry_default_unaffected_when_driver_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from langchain_ollama import ChatOllama

    monkeypatch.delenv("LLM_DRIVER", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "gemma4:12b")
    registry = create_model_registry()
    assert isinstance(registry.get("control"), ChatOllama)


# ---------------------------------------------------------------------------
# Seam through AgentRuntime._call_model_node (the e2e execution path)
# ---------------------------------------------------------------------------


async def test_agent_runtime_call_model_node_dispatches_job_dispatch(
    anyio_backend: str,
) -> None:
    runtime = _make_agent_runtime()
    state: dict[str, Any] = {
        "messages": [LLMMessage(role="user", content="Run a simulation for SKU-001.")],
        "iteration": 0,
        "input_tokens": 0,
        "peak_input_tokens": 0,
    }
    config = {"configurable": {"llm_tools": _CONTROL_TOOL_SPECS}}
    result = await runtime._call_model_node(state, config)
    response = result["response"]
    assert response.finish_reason == "tool_use"
    assert [tc["name"] for tc in response.tool_calls] == ["job_dispatch"]


async def test_agent_runtime_call_model_node_finalizes_after_tool_result(
    anyio_backend: str,
) -> None:
    runtime = _make_agent_runtime()
    config = {"configurable": {"llm_tools": _CONTROL_TOOL_SPECS}}
    first = await runtime._call_model_node(
        {
            "messages": [LLMMessage(role="user", content="Run a simulation.")],
            "iteration": 0,
            "input_tokens": 0,
            "peak_input_tokens": 0,
        },
        config,
    )
    tool_call = first["response"].tool_calls[0]
    final = await runtime._call_model_node(
        {
            "messages": [
                LLMMessage(role="user", content="Run a simulation."),
                LLMMessage(
                    role="assistant",
                    content="",
                    content_blocks=[{
                        "type": "tool_use",
                        "id": tool_call["id"],
                        "name": tool_call["name"],
                        "input": tool_call["input"],
                    }],
                ),
                LLMMessage(
                    role="tool",
                    content='{"job_id": "j-1", "status": "queued"}',
                    tool_call_id=tool_call["id"],
                ),
            ],
            "iteration": 1,
            "input_tokens": 0,
            "peak_input_tokens": 0,
        },
        config,
    )
    response = final["response"]
    assert response.tool_calls == []
    assert response.finish_reason == "stop"
    assert response.text.strip()
