from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import uuid4

from packages.agent.cross_domain.data_engineer import _data_engineer_output_builder
from packages.agent.cross_domain.simulation_optimizer import (
    SimulationOptimizerAgent,
    _simulation_optimizer_output_builder,
)
from packages.agent.llm import LLMMessage, LLMResponse, LLMUsage
from packages.agent.orchestrator.models import SpecialistTask
from packages.agent.runtime import AgentRuntime, _default_output_builder

# Unit tests for T-006: output builder extraction from AgentRuntime.


# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------


def _make_usage() -> LLMUsage:
    return LLMUsage(
        input_tokens=10,
        output_tokens=5,
        total_cost_usd=Decimal("0"),
    )


def _stop_response(text: str = "done") -> LLMResponse:
    return LLMResponse(
        text=text,
        tool_calls=[],
        finish_reason="stop",
        usage=_make_usage(),
        model="claude-sonnet-4-6-test",
        request_id=str(uuid4()),
        latency_ms=1,
    )


class _RecordingLLMClient:
    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self._model = "claude-sonnet-4-6-mock"

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
        if not self._responses:
            return _stop_response("fallback")
        return self._responses.pop(0)


class _FakeToolRegistry:
    def list_for_role(self, role: str) -> list[Any]:
        return []

    def filter_for_user_role(self, user_role: str, tools: list[Any]) -> list[Any]:
        return tools

    def get(self, name: str) -> Any | None:
        return None


class _FakeToolContext:
    def __init__(self) -> None:
        self.agent_step_id = uuid4()
        self.session_id = uuid4()
        self.user_id = "test-user"
        self.user_role = "analyst"


def _make_task(instruction: str = "Analyze demand.") -> SpecialistTask:
    return SpecialistTask(
        task_id=uuid4(),
        instruction=instruction,
        context_payload={},
        allowed_tools=[],
    )


# ---------------------------------------------------------------------------
# Tests: _default_output_builder (pure function)
# ---------------------------------------------------------------------------


def test_default_output_builder_returns_text_and_specialist() -> None:
    """_default_output_builder should return {"text": ..., "specialist": name}."""
    builder = _default_output_builder("my_agent")

    class _FakeResponse:
        text = "Hello from the agent."

    result = builder({}, _FakeResponse())

    assert result["text"] == "Hello from the agent."
    assert result["specialist"] == "my_agent"


def test_default_output_builder_no_tool_results_omits_tool_results_key() -> None:
    """When tool_results is empty, the key 'tool_results' must not appear."""
    builder = _default_output_builder("my_agent")

    class _FakeResponse:
        text = "Done."

    result = builder({}, _FakeResponse())

    assert "tool_results" not in result


def test_default_output_builder_with_tool_results_includes_them() -> None:
    """When tool_results is non-empty, they must be included in the output."""
    builder = _default_output_builder("my_agent")

    class _FakeResponse:
        text = "Done."

    result = builder({"sql_query": {"rows": []}}, _FakeResponse())

    assert "tool_results" in result


def test_default_output_builder_none_response_gives_empty_text() -> None:
    """When response is None, text must be an empty string."""
    builder = _default_output_builder("my_agent")
    result = builder({}, None)

    assert result["text"] == ""


# ---------------------------------------------------------------------------
# Tests: AgentRuntime uses default builder (no role branching)
# ---------------------------------------------------------------------------


async def test_agent_runtime_default_builder_produces_text_and_specialist() -> None:
    """AgentRuntime with no custom output_builder should include 'text' and 'specialist'."""
    llm = _RecordingLLMClient([_stop_response("Analysis complete."), _stop_response("pass")])
    runtime = AgentRuntime(
        name="generic_agent",
        role="inventory",
        llm_client=llm,
        tool_registry=_FakeToolRegistry(),
    )
    task = _make_task()
    ctx = _FakeToolContext()

    result = await runtime.run(task, ctx)

    assert result.output["text"] == "Analysis complete."
    assert result.output["specialist"] == "generic_agent"


async def test_agent_runtime_default_builder_no_simulation_branching() -> None:
    """AgentRuntime with role='simulation_optimizer' but no custom output_builder
    must NOT produce {'candidates': ...} — it should use the default builder."""
    llm = _RecordingLLMClient([_stop_response("No candidates here."), _stop_response("pass")])
    runtime = AgentRuntime(
        name="sim_agent",
        role="simulation_optimizer",
        llm_client=llm,
        tool_registry=_FakeToolRegistry(),
        # No custom output_builder — intentionally omitted to confirm no branching
    )
    task = _make_task()
    ctx = _FakeToolContext()

    result = await runtime.run(task, ctx)

    # Default builder: must have 'specialist', must NOT have 'candidates'
    assert result.output["specialist"] == "sim_agent"
    assert "candidates" not in result.output


# ---------------------------------------------------------------------------
# Tests: _simulation_optimizer_output_builder (pure function)
# ---------------------------------------------------------------------------


def test_simulation_optimizer_output_builder_with_candidates() -> None:
    """When 'optimize_replenishment' key is present, return {'candidates': [...]}."""
    tool_results = {
        "optimize_replenishment": {"candidates": [{"sku": "A", "qty": 100}]}
    }

    class _FakeResponse:
        text = "Optimization complete."

    result = _simulation_optimizer_output_builder(tool_results, _FakeResponse())

    assert result == {"candidates": [{"sku": "A", "qty": 100}]}


def test_simulation_optimizer_output_builder_empty_candidates() -> None:
    """When 'optimize_replenishment' has no 'candidates' key, return {'candidates': []}."""
    tool_results = {"optimize_replenishment": {}}

    class _FakeResponse:
        text = "Optimization complete."

    result = _simulation_optimizer_output_builder(tool_results, _FakeResponse())

    assert result == {"candidates": []}


def test_simulation_optimizer_output_builder_without_optimize_tool() -> None:
    """When 'optimize_replenishment' is not in tool_results, return {'text': ...}."""
    class _FakeResponse:
        text = "No optimization run."

    result = _simulation_optimizer_output_builder({}, _FakeResponse())

    assert result == {"text": "No optimization run."}


def test_simulation_optimizer_output_builder_none_response_fallback() -> None:
    """When response is None and no optimize_replenishment key, text is empty string."""
    result = _simulation_optimizer_output_builder({}, None)

    assert result == {"text": ""}


# ---------------------------------------------------------------------------
# Tests: _data_engineer_output_builder (pure function)
# ---------------------------------------------------------------------------


def test_data_engineer_output_builder_with_sql_query() -> None:
    """When 'sql_query' key is present, return {'data_summary': ..., 'text': ...}."""
    sql_result = {"rows": [{"sku": "X", "stock": 50}]}
    tool_results = {"sql_query": sql_result}

    class _FakeResponse:
        text = "Here is the data."

    result = _data_engineer_output_builder(tool_results, _FakeResponse())

    assert result["data_summary"] == sql_result
    assert result["text"] == "Here is the data."


def test_data_engineer_output_builder_without_sql_query() -> None:
    """When 'sql_query' is not in tool_results, return {'text': ...} only."""
    class _FakeResponse:
        text = "No SQL ran."

    result = _data_engineer_output_builder({}, _FakeResponse())

    assert result == {"text": "No SQL ran."}


def test_data_engineer_output_builder_none_response_fallback() -> None:
    """When response is None and no sql_query key, text is empty string."""
    result = _data_engineer_output_builder({}, None)

    assert result == {"text": ""}


# ---------------------------------------------------------------------------
# Integration: SimulationOptimizerAgent uses the custom output_builder
# ---------------------------------------------------------------------------


async def test_simulation_optimizer_agent_returns_candidates() -> None:
    """SimulationOptimizerAgent must produce {'candidates': [...]} when
    optimize_replenishment is in tool_results."""

    class _OptimizeTool:
        name = "optimize_replenishment"
        description = "Optimize replenishment"
        input_schema: dict[str, Any] = {}

        async def handle(self, input: dict[str, Any], ctx: Any) -> Any:
            from packages.tools.base import ToolResult
            return ToolResult(
                output={"candidates": [{"sku": "B", "qty": 200}]},
                audit_payload={},
            )

    class _OptimizeToolRegistry:
        def list_for_role(self, role: str) -> list[Any]:
            return [_OptimizeTool()]

        def filter_for_user_role(self, user_role: str, tools: list[Any]) -> list[Any]:
            return tools

        def get(self, name: str) -> Any | None:
            if name == "optimize_replenishment":
                return _OptimizeTool()
            return None

    # LLM call sequence:
    # 1. Main loop -> tool call for optimize_replenishment
    # 2. After tool result -> stop response
    # 3. Verifier -> pass

    tool_call_response = LLMResponse(
        text="",
        tool_calls=[
            {
                "id": "tc_001",
                "name": "optimize_replenishment",
                "input": {"horizon_days": 30},
            }
        ],
        finish_reason="tool_use",
        usage=_make_usage(),
        model="claude-sonnet-4-6-test",
        request_id=str(uuid4()),
        latency_ms=1,
    )
    final_response = _stop_response("Optimization done.")
    verifier_response = _stop_response("pass")

    llm = _RecordingLLMClient([tool_call_response, final_response, verifier_response])

    agent = SimulationOptimizerAgent(
        llm_client=llm,
        tool_registry=_OptimizeToolRegistry(),
    )
    task = SpecialistTask(
        task_id=uuid4(),
        instruction="Optimize replenishment for SKU B.",
        context_payload={},
        allowed_tools=["optimize_replenishment"],
    )
    ctx = _FakeToolContext()

    result = await agent.run(task, ctx)

    assert "candidates" in result.output
    assert result.output["candidates"] == [{"sku": "B", "qty": 200}]
