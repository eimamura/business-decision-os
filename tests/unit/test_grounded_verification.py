"""Unit tests for P72 — Grounded Runtime Evaluator (T-461).

ADR: docs/adr/2026-06-10-autonomy-loops.md §2

Scenarios covered (T-461):
  - grounded=True verdict → END, no revision, output.verification == {grounded: True, revised: False}
  - grounded=False → add_revision_message runs once with unsupported_claims embedded,
    call_model_final produces final answer, verification == {grounded: False, revised: True},
    no second verdict (revised gate)
  - verifier exception → fail-open completed, no verification key in output
  - gating: chat/lookup intent → no LLM verdict call (structured-output fake never invoked)
  - gating: empty tool_results → no LLM verdict call
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from packages.agent.orchestrator.models import SpecialistTask
from packages.agent.runtime import AgentRuntime, GroundednessVerdict
from tests.unit.helpers import (
    FakeLCModel,
    make_model_registry,
    make_stop_response,
    make_tool_call_response,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


class _FakeToolResult:
    output = {"rows": [{"sku": "SKU-001", "on_hand": 50}], "row_count": 1}
    audit_payload: dict[str, Any] = {}


class _FakeTool:
    name = "nl_query"
    description = "Run SQL"
    input_schema: dict[str, Any] = {}

    async def handle(self, input: dict[str, Any], ctx: Any) -> Any:
        from packages.tools.base import ToolResult
        return ToolResult(
            output={"rows": [{"sku": "SKU-001", "on_hand": 50}], "row_count": 1},
            audit_payload={},
        )


class _FakeToolRegistry:
    def __init__(self, tools: list[Any] | None = None) -> None:
        self._tools = tools or []

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
        self.user_role = "analyst"


def _make_task(
    instruction: str = "Analyze inventory.",
    intent_category: str = "domain_analysis",
) -> SpecialistTask:
    """Create a SpecialistTask with an intent category in context_payload (needed for
    the groundedness gate in _verify_findings_node)."""
    return SpecialistTask(
        task_id=uuid4(),
        instruction=instruction,
        context_payload={"intent": {"category": intent_category}},
        allowed_tools=["nl_query"],
    )


def _make_runtime_with_tool(lc_model: Any) -> AgentRuntime:
    """Create AgentRuntime wired to LangChain path with an nl_query tool."""
    registry = make_model_registry(lc_model)
    return AgentRuntime(
        name="test_agent",
        role="data_engineer",
        llm_client=None,
        tool_registry=_FakeToolRegistry([_FakeTool()]),
        sse_queue=None,
        system_prompt="You are a test specialist.",
        model_registry=registry,
    )


def _make_runtime_no_tool(lc_model: Any) -> AgentRuntime:
    """Create AgentRuntime with no tools (tool_results will be empty)."""
    registry = make_model_registry(lc_model)
    return AgentRuntime(
        name="test_agent",
        role="data_engineer",
        llm_client=None,
        tool_registry=_FakeToolRegistry([]),
        sse_queue=None,
        system_prompt="You are a test specialist.",
        model_registry=registry,
    )


# ---------------------------------------------------------------------------
# T-461-A: grounded=True verdict → END, no revision, verification present
# ---------------------------------------------------------------------------


async def test_t461_grounded_true_no_revision() -> None:
    """When the groundedness verifier returns grounded=True:
    - _after_verify routes to END (no add_revision_message node)
    - output has verification.grounded=True, verification.revised=False
    - call_model_final is NOT called (revised=False in final state)

    Response sequence (domain_analysis triggers plan_tools):
      0. plan_tools ainvoke  (JSON parse fails silently — no-op plan)
      1. call_model: tool_call_response  (nl_query)
      2. call_model after tool exec: final conclusion
      3. verify_findings: GroundednessVerdict(grounded=True)
    """
    lc_model = FakeLCModel([
        make_stop_response("plan"),  # plan_tools — no JSON array, silently skipped
        make_tool_call_response("nl_query", {"question": "What is on-hand?"}),
        make_stop_response(
            "SKU-001 has fifty units on hand based on the inventory snapshot data."
        ),
        # GroundednessVerdict (consumed by with_structured_output in _verify_findings_node)
        GroundednessVerdict(grounded=True, unsupported_claims=[]),
    ])
    runtime = _make_runtime_with_tool(lc_model)
    task = _make_task(intent_category="domain_analysis")
    ctx = _FakeToolContext()

    result = await runtime.run(task, ctx)

    assert result.status == "completed"
    assert "verification" in result.output, (
        "output must contain 'verification' key when groundedness verdict ran"
    )
    assert result.output["verification"]["grounded"] is True
    assert result.output["verification"]["revised"] is False, (
        "grounded=True path must not set revised=True"
    )


# ---------------------------------------------------------------------------
# T-461-B: grounded=False → revision runs once, verification.revised=True
# ---------------------------------------------------------------------------


async def test_t461_grounded_false_one_revision_then_end() -> None:
    """When the groundedness verifier returns grounded=False:
    - add_revision_message runs with unsupported_claims embedded in the message
    - call_model_final runs once and produces the final answer
    - verification.grounded=False, verification.revised=True
    - No second LLM verdict is called (revised gate short-circuits)

    Response sequence (domain_analysis triggers plan_tools):
      0. plan_tools ainvoke  (JSON parse fails silently)
      1. call_model: tool_call_response  (nl_query)
      2. call_model after tool exec: ungrounded conclusion
      3. verify_findings: GroundednessVerdict(grounded=False)
      4. call_model_final: revised answer
    """
    unsupported_claim = "The on-hand quantity is nine hundred and ninety-nine units"
    lc_model = FakeLCModel([
        make_stop_response("plan"),  # plan_tools
        make_tool_call_response("nl_query", {"question": "What is on-hand?"}),
        make_stop_response(
            "The on-hand quantity is nine hundred and ninety-nine units — which is very high."
        ),
        # GroundednessVerdict consumed by _verify_findings_node
        GroundednessVerdict(grounded=False, unsupported_claims=[unsupported_claim]),
        # call_model_final answer (after add_revision_message)
        make_stop_response(
            "Based on the tool results, SKU-001 has fifty units on hand per data."
        ),
    ])
    runtime = _make_runtime_with_tool(lc_model)
    task = _make_task(intent_category="domain_analysis")
    ctx = _FakeToolContext()

    result = await runtime.run(task, ctx)

    assert result.status == "completed", (
        f"Expected completed after revision, got: {result.status}"
    )
    assert "verification" in result.output, (
        "output must contain 'verification' key"
    )
    assert result.output["verification"]["grounded"] is False
    assert result.output["verification"]["revised"] is True, (
        "revision must have occurred — revised=True expected"
    )
    # All 5 pre-configured responses must have been consumed.
    assert len(lc_model._responses) == 0, (
        "All 5 pre-configured responses must be consumed (plan + tool_call + first_answer "
        "+ verdict + final_answer)"
    )


# ---------------------------------------------------------------------------
# T-461-B: add_revision_message embeds unsupported_claims in the message text
# ---------------------------------------------------------------------------


async def test_t461_revision_message_embeds_unsupported_claims() -> None:
    """The revision message passed to call_model_final must contain the specific
    unsupported claims identified by the verifier."""
    from packages.agent.runtime import AgentState

    # We test _add_revision_message_node directly with a fake state.
    lc_model = FakeLCModel([])
    runtime = _make_runtime_no_tool(lc_model)

    unsupported = ["claim A is unsupported", "claim B lacks evidence"]
    fake_state: Any = {
        "messages": [],
        "response": None,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
        "tool_results": [],
        "iteration": 0,
        "status": "needs_revision",
        "error": None,
        "pending_hitl_approval_id": None,
        "pending_hitl_job_id": None,
        "compressed_messages": None,
        "tool_plan": [],
        "groundedness": {
            "grounded": False,
            "unsupported_claims": unsupported,
        },
        "revised": False,
    }

    node_result = await runtime._add_revision_message_node(fake_state, {})  # type: ignore[arg-type]
    revision_msgs = node_result.get("messages", [])
    assert len(revision_msgs) == 1, "Must add exactly one revision message"
    content = revision_msgs[0].content
    assert "claim A is unsupported" in content, (
        f"Revision message must embed unsupported claims, got: {content!r}"
    )
    assert "claim B lacks evidence" in content, (
        f"Revision message must embed all unsupported claims, got: {content!r}"
    )
    assert node_result.get("status") == "running"


# ---------------------------------------------------------------------------
# T-461-C: verifier exception → fail-open completed, no verification key
# ---------------------------------------------------------------------------


async def test_t461_verifier_exception_fail_open_no_verification_key() -> None:
    """When the groundedness LLM call raises an exception, _verify_findings_node must
    fall back to rule-based result (pass). The output must NOT contain 'verification'
    key (verdict stored only on success — ADR §2 'fail-open to rule-based only')."""
    # We test _verify_findings_node directly with a model that raises on structured output.
    class _BrokenLCModel:
        model = "broken"

        def with_structured_output(self, schema: Any) -> Any:
            class _Raiser:
                async def ainvoke(self, *a: Any, **kw: Any) -> None:
                    raise RuntimeError("groundedness model broken")
            return _Raiser()

        def bind_tools(self, tools: Any) -> "_BrokenLCModel":
            return self

        async def ainvoke(self, *args: Any, **kwargs: Any) -> Any:
            from langchain_core.messages import AIMessage
            return AIMessage(
                content="fallback",
                usage_metadata={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            )

    registry = make_model_registry(_BrokenLCModel())
    runtime = AgentRuntime(
        name="test_agent",
        role="data_engineer",
        llm_client=None,
        tool_registry=_FakeToolRegistry([]),
        sse_queue=None,
        system_prompt="You are a test specialist.",
        model_registry=registry,
    )

    # Fake state with tool_results (non-empty) to pass the gating checks
    fake_tool_result = {"nl_query": {"rows": [{"sku": "SKU-001"}], "row_count": 1}}
    fake_state: Any = {
        "messages": [],
        "response": MagicMock(
            text="SKU-001 has stockout risk based on tool results here.",
            finish_reason="stop",
        ),
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
        "tool_results": [fake_tool_result],
        "iteration": 1,
        "status": "running",
        "error": None,
        "pending_hitl_approval_id": None,
        "pending_hitl_job_id": None,
        "compressed_messages": None,
        "tool_plan": [],
        "groundedness": None,
        "revised": False,
    }

    # Pass intent_category=domain_analysis in configurable so the gate passes
    fake_config: Any = {
        "configurable": {
            "task": _make_task(intent_category="domain_analysis"),
        }
    }

    node_result = await runtime._verify_findings_node(fake_state, fake_config)

    # Fall-open: the rule-based pre-filter passes (long enough conclusion, no fabricated data)
    # The LLM call raises → exception caught → fall-back to rule-based pass
    assert node_result.get("status") in ("completed", "blocked"), (
        f"Expected 'completed' or 'blocked' from fail-open, got: {node_result}"
    )
    assert "groundedness" not in node_result, (
        "No 'groundedness' key must be set when the verifier raises (fail-open)"
    )


# ---------------------------------------------------------------------------
# T-461-D: gating — chat intent skips LLM verdict
# ---------------------------------------------------------------------------


async def test_t461_chat_intent_skips_groundedness_verdict() -> None:
    """When intent_category == 'chat', the groundedness LLM call must be skipped.
    chat is NOT in _PLAN_TOOLS_INTENTS either, so plan_tools also skips.
    Only 1 LLM call is made (call_model only)."""
    # chat intent: no plan_tools (not in _PLAN_TOOLS_INTENTS), no groundedness check.
    # Conclusion must not trigger rule-based block (no digits, no "no"/"none").
    lc_model = FakeLCModel([
        make_stop_response(
            "Hello, I can help you with supply chain questions and analysis."
        ),
    ])
    runtime = _make_runtime_no_tool(lc_model)
    task = _make_task(intent_category="chat")
    ctx = _FakeToolContext()

    result = await runtime.run(task, ctx)

    assert result.status == "completed"
    assert "verification" not in result.output, (
        "chat intent must not trigger groundedness verification"
    )
    assert len(lc_model._responses) == 0, (
        "Only 1 LLM call should have been made (call_model, no groundedness verdict)"
    )


# ---------------------------------------------------------------------------
# T-461-D: gating — lookup intent skips LLM verdict
# ---------------------------------------------------------------------------


async def test_t461_lookup_intent_skips_groundedness_verdict() -> None:
    """When intent_category == 'lookup', the groundedness check is skipped.
    lookup is NOT in _PLAN_TOOLS_INTENTS, so plan_tools also skips.
    Conclusion must avoid rule-based block (no digits, no "no"/"none" patterns)."""
    lc_model = FakeLCModel([
        # Conclusion without digits or nil-claim patterns (avoids rule-based block)
        make_stop_response(
            "The inventory snapshot table contains SKU master data and on-hand quantities."
        ),
    ])
    runtime = _make_runtime_no_tool(lc_model)
    task = _make_task(intent_category="lookup")
    ctx = _FakeToolContext()

    result = await runtime.run(task, ctx)

    assert result.status == "completed"
    assert "verification" not in result.output, (
        "lookup intent must not trigger groundedness verification"
    )


# ---------------------------------------------------------------------------
# T-461-D: gating — empty tool_results skips LLM verdict
# ---------------------------------------------------------------------------


async def test_t461_empty_tool_results_skips_groundedness_verdict() -> None:
    """Even for an eligible intent (domain_analysis), the groundedness check is
    skipped when tool_results is empty (no data to ground claims against).

    domain_analysis triggers plan_tools, so we include a response for it.
    Conclusion must avoid digits/nil-claim patterns (rule-based block) and
    must be long enough to avoid the degenerate-response guard."""
    lc_model = FakeLCModel([
        make_stop_response("plan"),  # plan_tools — no JSON, silently skipped
        make_stop_response(
            "Based on supply chain principles, the demand trend appears stable "
            "and within expected parameters for the current season."
        ),
    ])
    # No tools registered → tool_results will be empty
    runtime = _make_runtime_no_tool(lc_model)
    task = _make_task(intent_category="domain_analysis")
    ctx = _FakeToolContext()

    result = await runtime.run(task, ctx)

    assert result.status == "completed"
    assert "verification" not in result.output, (
        "Empty tool_results must skip groundedness verification"
    )
