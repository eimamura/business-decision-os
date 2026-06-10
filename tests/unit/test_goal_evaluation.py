"""Unit tests for P71 — Goal Evaluation Loop (T-455, T-456).

ADR: docs/adr/2026-06-10-autonomy-loops.md §1

Scenarios covered:
  T-455:
    - satisfied verdict → exactly one run_sequential execution, goal_evaluation present in
      SessionResponse
    - unsatisfied verdict → exactly one refinement pass (run_sequential runs twice), then END
      even if still unsatisfied (cap at refine_count >= 1)
    - chat intent bypasses set_goal and evaluate_goal (no GoalSpec consumption)
    - verdict call raising → fail-open satisfied=True, single run_sequential execution

  T-456:
    - reroute_category valid + different → intent category updated on refinement pass
    - reroute_category invalid / chat / same → ignored
    - refinement_feedback ("Additional guidance") reaches the agent instruction
"""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from packages.agent.orchestrator import SessionOrchestrator, SessionUserQuery
from packages.agent.orchestrator.models import (
    AgentRoute,
    AskUserDecision,
    GoalEvaluation,
    GoalSpec,
    SessionIntent,
    SessionResponse,
)
from packages.memory import StubMemoryStore
from packages.tools import create_tool_registry
from tests.unit.helpers import MultiRoleModelRegistry, StructuredOutputFakeModel


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_SESSION_ID = uuid4()


def _mock_repo() -> MagicMock:
    repo = MagicMock()
    repo.update_status = AsyncMock()
    return repo


def _patch_repo(repo: MagicMock):
    return patch(
        "packages.agent.orchestrator.session_orchestrator.DecisionSessionRepository",
        return_value=repo,
    )


def _patch_run_agents(reply: str = "Analysis complete.") -> Any:
    """Patch _run_agents_in_order to skip agent execution and return a stub result."""
    stub_result = MagicMock()
    stub_result.output = {"text": reply}
    stub_result.status = "completed"
    stub_result.usage = {}
    return patch(
        "packages.agent.orchestrator.session_orchestrator._run_agents_in_order",
        new=AsyncMock(return_value=[stub_result]),
    )


def _patch_synthesize(reply: str = "Analysis complete.") -> Any:
    """Patch _synthesize_response to return a minimal SessionResponse."""

    def _build_response(*args: Any, **kwargs: Any) -> SessionResponse:
        intent = args[3] if len(args) > 3 else None
        route = args[4] if len(args) > 4 else None
        return SessionResponse(
            mode="single_agent",
            reply=reply,
            intent=intent or SessionIntent(
                category="decision_support", confidence=0.9, rationale="stub"
            ),
            route=route or AgentRoute(
                mode="single_agent", agents=["control"],
                requires_planning=False, requires_dag=False, rationale="stub",
            ),
        )

    return patch(
        "packages.agent.orchestrator.session_orchestrator._synthesize_response",
        new=AsyncMock(side_effect=_build_response),
    )


def _make_orchestrator(orchestrator_model: Any) -> SessionOrchestrator:
    registry = MultiRoleModelRegistry({"orchestrator": orchestrator_model})
    return SessionOrchestrator(
        llm_client=MagicMock(_model="stub"),
        tool_registry=create_tool_registry(),
        memory_store=StubMemoryStore(),
        model_registry=registry,
    )


# ---------------------------------------------------------------------------
# T-455: satisfied verdict → single run, goal_evaluation present
# ---------------------------------------------------------------------------


async def test_t455_satisfied_verdict_single_run_sequential() -> None:
    """When evaluate_goal returns satisfied=True, run_sequential executes exactly once
    and goal_evaluation is populated in SessionResponse."""
    # decision_support: set_goal consumes GoalSpec, prepare_ask_user consumes
    # AskUserDecision, select_mode consumes AgentRoute, evaluate_goal consumes
    # GoalEvaluation (satisfied=True).
    orchestrator_model = StructuredOutputFakeModel([
        SessionIntent(
            category="decision_support", confidence=0.9,
            rationale="needs analysis", goal_text="optimize replenishment",
        ),
        GoalSpec(goal_text="optimize replenishment", success_criteria=["lower cost"]),
        AskUserDecision(needs_input=False, question=None, suggestions=None),
        AgentRoute(
            mode="single_agent", agents=["control"],
            requires_planning=False, requires_dag=False, rationale="single",
        ),
        GoalEvaluation(satisfied=True, missing=None, reroute_category=None),
    ])
    orchestrator = _make_orchestrator(orchestrator_model)

    run_agents_call_count = 0

    async def _counting_run_agents(*args: Any, **kwargs: Any) -> list[Any]:
        nonlocal run_agents_call_count
        run_agents_call_count += 1
        stub = MagicMock()
        stub.output = {"text": "Analysis complete."}
        stub.status = "completed"
        stub.usage = {}
        return [stub]

    with (
        _patch_repo(_mock_repo()),
        patch(
            "packages.agent.orchestrator.session_orchestrator._run_agents_in_order",
            new=AsyncMock(side_effect=_counting_run_agents),
        ),
        _patch_synthesize("Analysis complete."),
    ):
        response = await orchestrator.run(_SESSION_ID, SessionUserQuery(text="optimize replenishment"))
        await asyncio.sleep(0)

    assert run_agents_call_count == 1, (
        f"Expected exactly 1 run_sequential execution, got {run_agents_call_count}"
    )
    assert isinstance(response, SessionResponse)
    assert response.goal_evaluation is not None, (
        "goal_evaluation must be populated in SessionResponse when satisfied"
    )
    assert response.goal_evaluation.get("satisfied") is True


# ---------------------------------------------------------------------------
# T-455: unsatisfied → exactly one refinement (run_sequential twice) then END
# ---------------------------------------------------------------------------


async def test_t455_unsatisfied_verdict_exactly_one_refinement_then_end() -> None:
    """When evaluate_goal returns satisfied=False (refine_count=0), run_sequential
    executes again (refinement pass). After the second run, evaluate_goal fires
    again; regardless of its verdict, refine_count >= 1 means END (cap enforced)."""
    orchestrator_model = StructuredOutputFakeModel([
        SessionIntent(
            category="decision_support", confidence=0.9,
            rationale="needs analysis", goal_text="optimize replenishment",
        ),
        GoalSpec(goal_text="optimize replenishment", success_criteria=["lower cost"]),
        AskUserDecision(needs_input=False, question=None, suggestions=None),
        AgentRoute(
            mode="single_agent", agents=["control"],
            requires_planning=False, requires_dag=False, rationale="single",
        ),
        # First evaluate_goal: unsatisfied
        GoalEvaluation(satisfied=False, missing="needs cost breakdown", reroute_category=None),
        # Second evaluate_goal (post-refinement): still unsatisfied — cap must fire
        GoalEvaluation(satisfied=False, missing="still missing", reroute_category=None),
    ])
    orchestrator = _make_orchestrator(orchestrator_model)

    run_agents_call_count = 0

    async def _counting_run_agents(*args: Any, **kwargs: Any) -> list[Any]:
        nonlocal run_agents_call_count
        run_agents_call_count += 1
        stub = MagicMock()
        stub.output = {"text": "Analysis complete."}
        stub.status = "completed"
        stub.usage = {}
        return [stub]

    with (
        _patch_repo(_mock_repo()),
        patch(
            "packages.agent.orchestrator.session_orchestrator._run_agents_in_order",
            new=AsyncMock(side_effect=_counting_run_agents),
        ),
        _patch_synthesize("Analysis complete."),
    ):
        response = await orchestrator.run(
            _SESSION_ID, SessionUserQuery(text="optimize replenishment")
        )
        await asyncio.sleep(0)

    assert run_agents_call_count == 2, (
        f"Expected exactly 2 run_sequential executions (original + 1 refinement), "
        f"got {run_agents_call_count}"
    )
    assert isinstance(response, SessionResponse)


# ---------------------------------------------------------------------------
# T-455: chat intent bypasses set_goal and evaluate_goal
# ---------------------------------------------------------------------------


async def test_t455_chat_intent_bypasses_goal_loop() -> None:
    """chat intent must not trigger set_goal (no GoalSpec consumed) or evaluate_goal.
    The graph flows classify_intent → set_goal(skip) → … → run_direct_chat → END.

    Verification:
    - goal_evaluation is None in the response (evaluate_goal skipped/no-op for chat)
    - No GoalSpec is consumed from the stub (type-aware fake would raise on unexpected use)
    - run_sequential is never called
    """
    # chat intent: set_goal returns goal=None without consuming GoalSpec.
    # No GoalSpec in the list — if set_goal tried to consume one, the LookupError
    # would be raised, caught as fail-open, and we'd still get a response, but we
    # can verify goal_evaluation is None.
    orchestrator_model = StructuredOutputFakeModel([
        SessionIntent(
            category="chat", confidence=0.99,
            rationale="greeting", goal_text=None,
        ),
        # select_mode will consume AgentRoute for direct_chat
        AgentRoute(
            mode="direct_chat", agents=[],
            requires_planning=False, requires_dag=False, rationale="chat",
        ),
    ])

    class _ChatLLMClient:
        """Minimal LLM client for direct_chat path — implements astream as an async generator."""

        _model = "stub"

        async def astream(self, messages: Any, config: Any = None, **kwargs: Any) -> Any:
            """Async generator that yields a single chunk."""
            from types import SimpleNamespace
            yield SimpleNamespace(content="Hello! How can I help?")

        async def complete(self, *args: Any, **kwargs: Any) -> Any:
            from decimal import Decimal

            from packages.agent.llm import LLMResponse, LLMUsage
            return LLMResponse(
                text="Hello! How can I help?",
                tool_calls=[],
                finish_reason="stop",
                usage=LLMUsage(
                    input_tokens=0, output_tokens=0, total_cost_usd=Decimal("0")
                ),
                model="stub",
                request_id=str(uuid4()),
                latency_ms=0,
            )

    registry = MultiRoleModelRegistry({"orchestrator": orchestrator_model})
    orchestrator = SessionOrchestrator(
        llm_client=_ChatLLMClient(),
        tool_registry=create_tool_registry(),
        memory_store=StubMemoryStore(),
        model_registry=registry,
    )

    run_sequential_called = False

    async def _run_sequential_spy(*args: Any, **kwargs: Any) -> list[Any]:
        nonlocal run_sequential_called
        run_sequential_called = True
        stub = MagicMock()
        stub.output = {"text": "stub"}
        stub.status = "completed"
        stub.usage = {}
        return [stub]

    with (
        _patch_repo(_mock_repo()),
        patch(
            "packages.agent.orchestrator.session_orchestrator._run_agents_in_order",
            new=AsyncMock(side_effect=_run_sequential_spy),
        ),
    ):
        response = await orchestrator.run(uuid4(), SessionUserQuery(text="Hello!"))
        await asyncio.sleep(0)

    assert isinstance(response, SessionResponse)
    assert response.mode == "direct_chat"
    assert response.goal_evaluation is None, (
        "chat intent must not produce goal_evaluation"
    )
    assert not run_sequential_called, (
        "run_sequential must not be called for chat intent"
    )


# ---------------------------------------------------------------------------
# T-455: verdict call raising → fail-open satisfied=True, single run
# ---------------------------------------------------------------------------


async def test_t455_verdict_raising_fail_open_single_run() -> None:
    """When the GoalEvaluation LLM call raises inside _node_evaluate_goal, the
    fail-open path must catch it and return GoalEvaluation(satisfied=True).
    We test this directly on the node method (unit-testing the fail-open contract)
    and also verify the full-graph path does not produce a refinement pass.
    """
    from packages.agent.orchestrator.models import AgentRoute, SessionIntent, SessionResponse

    orchestrator_model = StructuredOutputFakeModel([
        SessionIntent(
            category="decision_support", confidence=0.9,
            rationale="needs analysis", goal_text="optimize replenishment",
        ),
        GoalSpec(goal_text="optimize replenishment", success_criteria=[]),
        AskUserDecision(needs_input=False, question=None, suggestions=None),
        AgentRoute(
            mode="single_agent", agents=["control"],
            requires_planning=False, requires_dag=False, rationale="single",
        ),
        # GoalEvaluation deliberately omitted — _TypeAwareFakeStructured will raise
        # LookupError when GoalEvaluation is requested, which the except-block catches.
    ])
    orchestrator = _make_orchestrator(orchestrator_model)

    # --- Unit test: verify fail-open contract on the node directly ---
    mock_result = SessionResponse(
        mode="single_agent",
        reply="Analysis complete.",
        intent=SessionIntent(category="decision_support", confidence=0.9, rationale="stub"),
        route=AgentRoute(
            mode="single_agent", agents=["control"],
            requires_planning=False, requires_dag=False, rationale="stub",
        ),
    )
    fake_state: Any = {
        "intent": SessionIntent(
            category="decision_support", confidence=0.9,
            rationale="stub", goal_text="optimize",
        ),
        "goal": {"goal_text": "optimize", "success_criteria": []},
        "result": mock_result,
        "session_id": str(_SESSION_ID),
    }
    # The orchestrator_model's GoalEvaluation slot is empty — ainvoke will raise LookupError.
    node_result = await orchestrator._node_evaluate_goal(fake_state, {})  # type: ignore[arg-type]
    assert node_result.get("goal_eval", {}).get("satisfied") is True, (
        "Fail-open must return satisfied=True when the LLM call raises"
    )

    # --- Integration test: full graph produces exactly 1 run_sequential ---
    orchestrator2 = _make_orchestrator(StructuredOutputFakeModel([
        SessionIntent(
            category="decision_support", confidence=0.9,
            rationale="needs analysis", goal_text="optimize replenishment",
        ),
        GoalSpec(goal_text="optimize replenishment", success_criteria=[]),
        AskUserDecision(needs_input=False, question=None, suggestions=None),
        AgentRoute(
            mode="single_agent", agents=["control"],
            requires_planning=False, requires_dag=False, rationale="single",
        ),
        # GoalEvaluation omitted — fail-open fires
    ]))

    run_agents_call_count = 0

    async def _counting_run_agents(*args: Any, **kwargs: Any) -> list[Any]:
        nonlocal run_agents_call_count
        run_agents_call_count += 1
        stub = MagicMock()
        stub.output = {"text": "Analysis complete."}
        stub.status = "completed"
        stub.usage = {}
        return [stub]

    with (
        _patch_repo(_mock_repo()),
        patch(
            "packages.agent.orchestrator.session_orchestrator._run_agents_in_order",
            new=AsyncMock(side_effect=_counting_run_agents),
        ),
        _patch_synthesize("Analysis complete."),
    ):
        response = await orchestrator2.run(
            _SESSION_ID, SessionUserQuery(text="optimize replenishment")
        )
        await asyncio.sleep(0)

    assert run_agents_call_count == 1, (
        f"Fail-open must yield a single run_sequential execution (no refinement), "
        f"got {run_agents_call_count}"
    )
    assert isinstance(response, SessionResponse)


# ---------------------------------------------------------------------------
# T-456: reroute_category valid + different → intent category updated on refinement
# ---------------------------------------------------------------------------


async def test_t456_reroute_category_updates_intent_on_refinement() -> None:
    """When evaluate_goal returns a valid, different reroute_category, the intent
    category must be updated before the refinement run_sequential, and the tool
    subset must follow (route updated to match the new mode)."""
    orchestrator_model = StructuredOutputFakeModel([
        SessionIntent(
            category="lookup", confidence=0.8,
            rationale="initial classification", goal_text="check stockout",
        ),
        GoalSpec(goal_text="check stockout", success_criteria=[]),
        AskUserDecision(needs_input=False, question=None, suggestions=None),
        AgentRoute(
            mode="single_agent", agents=["control"],
            requires_planning=False, requires_dag=False, rationale="initial",
        ),
        # First evaluate_goal: unsatisfied, re-route to supply_chain
        GoalEvaluation(
            satisfied=False,
            missing="need full supply chain analysis",
            reroute_category="supply_chain",
        ),
        # Second evaluate_goal (post-refinement): satisfied — cap also would fire
        GoalEvaluation(satisfied=True, missing=None, reroute_category=None),
    ])
    orchestrator = _make_orchestrator(orchestrator_model)

    captured_intents: list[str] = []

    async def _capturing_run_agents(orch: Any, session_id: Any, query: Any, agents: Any, intent: Any) -> list[Any]:
        captured_intents.append(intent.category)
        stub = MagicMock()
        stub.output = {"text": "Analysis complete."}
        stub.status = "completed"
        stub.usage = {}
        return [stub]

    with (
        _patch_repo(_mock_repo()),
        patch(
            "packages.agent.orchestrator.session_orchestrator._run_agents_in_order",
            new=AsyncMock(side_effect=_capturing_run_agents),
        ),
        _patch_synthesize("Analysis complete."),
    ):
        response = await orchestrator.run(
            _SESSION_ID, SessionUserQuery(text="check stockout risk")
        )
        await asyncio.sleep(0)

    assert len(captured_intents) == 2, (
        f"Expected 2 run_sequential calls (original + refinement), got {captured_intents}"
    )
    assert captured_intents[0] == "lookup", (
        f"First run must use original intent 'lookup', got '{captured_intents[0]}'"
    )
    assert captured_intents[1] == "supply_chain", (
        f"Refinement run must use re-routed intent 'supply_chain', got '{captured_intents[1]}'"
    )


# ---------------------------------------------------------------------------
# T-456: invalid reroute_category is ignored
# ---------------------------------------------------------------------------


async def test_t456_invalid_reroute_category_ignored() -> None:
    """reroute_category with an unknown value must be silently ignored — intent
    stays the same on the refinement pass."""
    orchestrator_model = StructuredOutputFakeModel([
        SessionIntent(
            category="decision_support", confidence=0.9,
            rationale="needs analysis", goal_text="optimize",
        ),
        GoalSpec(goal_text="optimize", success_criteria=[]),
        AskUserDecision(needs_input=False, question=None, suggestions=None),
        AgentRoute(
            mode="single_agent", agents=["control"],
            requires_planning=False, requires_dag=False, rationale="single",
        ),
        GoalEvaluation(
            satisfied=False, missing="more detail needed",
            reroute_category="nonexistent_category_xyz",
        ),
        GoalEvaluation(satisfied=True, missing=None, reroute_category=None),
    ])
    orchestrator = _make_orchestrator(orchestrator_model)

    captured_intents: list[str] = []

    async def _capturing_run_agents(orch: Any, session_id: Any, query: Any, agents: Any, intent: Any) -> list[Any]:
        captured_intents.append(intent.category)
        stub = MagicMock()
        stub.output = {"text": "Analysis complete."}
        stub.status = "completed"
        stub.usage = {}
        return [stub]

    with (
        _patch_repo(_mock_repo()),
        patch(
            "packages.agent.orchestrator.session_orchestrator._run_agents_in_order",
            new=AsyncMock(side_effect=_capturing_run_agents),
        ),
        _patch_synthesize("Analysis complete."),
    ):
        response = await orchestrator.run(
            _SESSION_ID, SessionUserQuery(text="optimize supply chain")
        )
        await asyncio.sleep(0)

    assert len(captured_intents) == 2
    # Both passes must use the original intent — invalid reroute is ignored
    assert captured_intents[0] == "decision_support"
    assert captured_intents[1] == "decision_support", (
        f"Invalid reroute must be ignored; second pass must stay 'decision_support', "
        f"got '{captured_intents[1]}'"
    )


# ---------------------------------------------------------------------------
# T-456: reroute_category == 'chat' is ignored
# ---------------------------------------------------------------------------


async def test_t456_reroute_category_chat_ignored() -> None:
    """reroute_category='chat' must be ignored (ADR: chat bypasses the loop entirely)."""
    orchestrator_model = StructuredOutputFakeModel([
        SessionIntent(
            category="decision_support", confidence=0.9,
            rationale="needs analysis", goal_text="optimize",
        ),
        GoalSpec(goal_text="optimize", success_criteria=[]),
        AskUserDecision(needs_input=False, question=None, suggestions=None),
        AgentRoute(
            mode="single_agent", agents=["control"],
            requires_planning=False, requires_dag=False, rationale="single",
        ),
        GoalEvaluation(
            satisfied=False, missing="add context",
            reroute_category="chat",
        ),
        GoalEvaluation(satisfied=True, missing=None, reroute_category=None),
    ])
    orchestrator = _make_orchestrator(orchestrator_model)

    captured_intents: list[str] = []

    async def _capturing_run_agents(orch: Any, session_id: Any, query: Any, agents: Any, intent: Any) -> list[Any]:
        captured_intents.append(intent.category)
        stub = MagicMock()
        stub.output = {"text": "Analysis complete."}
        stub.status = "completed"
        stub.usage = {}
        return [stub]

    with (
        _patch_repo(_mock_repo()),
        patch(
            "packages.agent.orchestrator.session_orchestrator._run_agents_in_order",
            new=AsyncMock(side_effect=_capturing_run_agents),
        ),
        _patch_synthesize("Analysis complete."),
    ):
        response = await orchestrator.run(
            _SESSION_ID, SessionUserQuery(text="optimize supply chain")
        )
        await asyncio.sleep(0)

    assert len(captured_intents) == 2
    assert captured_intents[1] == "decision_support", (
        f"reroute_category='chat' must be ignored; intent stays 'decision_support', "
        f"got '{captured_intents[1]}'"
    )


# ---------------------------------------------------------------------------
# T-456: reroute_category same as current → no change
# ---------------------------------------------------------------------------


async def test_t456_reroute_category_same_as_current_ignored() -> None:
    """reroute_category matching the current intent category must be ignored."""
    orchestrator_model = StructuredOutputFakeModel([
        SessionIntent(
            category="decision_support", confidence=0.9,
            rationale="needs analysis", goal_text="optimize",
        ),
        GoalSpec(goal_text="optimize", success_criteria=[]),
        AskUserDecision(needs_input=False, question=None, suggestions=None),
        AgentRoute(
            mode="single_agent", agents=["control"],
            requires_planning=False, requires_dag=False, rationale="single",
        ),
        GoalEvaluation(
            satisfied=False, missing="add context",
            reroute_category="decision_support",  # same as current
        ),
        GoalEvaluation(satisfied=True, missing=None, reroute_category=None),
    ])
    orchestrator = _make_orchestrator(orchestrator_model)

    captured_intents: list[str] = []

    async def _capturing_run_agents(orch: Any, session_id: Any, query: Any, agents: Any, intent: Any) -> list[Any]:
        captured_intents.append(intent.category)
        stub = MagicMock()
        stub.output = {"text": "Analysis complete."}
        stub.status = "completed"
        stub.usage = {}
        return [stub]

    with (
        _patch_repo(_mock_repo()),
        patch(
            "packages.agent.orchestrator.session_orchestrator._run_agents_in_order",
            new=AsyncMock(side_effect=_capturing_run_agents),
        ),
        _patch_synthesize("Analysis complete."),
    ):
        response = await orchestrator.run(
            _SESSION_ID, SessionUserQuery(text="optimize supply chain")
        )
        await asyncio.sleep(0)

    assert len(captured_intents) == 2
    assert captured_intents[0] == captured_intents[1] == "decision_support", (
        "Same-category reroute must be a no-op"
    )


# ---------------------------------------------------------------------------
# T-456: refinement_feedback reaches agent instruction
# ---------------------------------------------------------------------------


async def test_t456_refinement_feedback_reaches_instruction() -> None:
    """The 'missing' text from GoalEvaluation must be appended as 'Additional guidance'
    to the intent instruction passed to _run_agents_in_order on the refinement pass."""
    orchestrator_model = StructuredOutputFakeModel([
        SessionIntent(
            category="decision_support", confidence=0.9,
            rationale="needs analysis", goal_text="optimize replenishment",
        ),
        GoalSpec(goal_text="optimize replenishment", success_criteria=[]),
        AskUserDecision(needs_input=False, question=None, suggestions=None),
        AgentRoute(
            mode="single_agent", agents=["control"],
            requires_planning=False, requires_dag=False, rationale="single",
        ),
        GoalEvaluation(
            satisfied=False,
            missing="please include cost breakdown per SKU",
            reroute_category=None,
        ),
        GoalEvaluation(satisfied=True, missing=None, reroute_category=None),
    ])
    orchestrator = _make_orchestrator(orchestrator_model)

    captured_goal_texts: list[str] = []

    async def _capturing_run_agents(orch: Any, session_id: Any, query: Any, agents: Any, intent: Any) -> list[Any]:
        captured_goal_texts.append(intent.goal_text or "")
        stub = MagicMock()
        stub.output = {"text": "Analysis complete."}
        stub.status = "completed"
        stub.usage = {}
        return [stub]

    with (
        _patch_repo(_mock_repo()),
        patch(
            "packages.agent.orchestrator.session_orchestrator._run_agents_in_order",
            new=AsyncMock(side_effect=_capturing_run_agents),
        ),
        _patch_synthesize("Analysis complete."),
    ):
        response = await orchestrator.run(
            _SESSION_ID, SessionUserQuery(text="optimize replenishment")
        )
        await asyncio.sleep(0)

    assert len(captured_goal_texts) == 2, (
        f"Expected 2 run_sequential calls, got {len(captured_goal_texts)}"
    )
    assert "Additional guidance" in captured_goal_texts[1], (
        f"Refinement pass must contain 'Additional guidance' in goal_text, "
        f"got: {captured_goal_texts[1]!r}"
    )
    assert "please include cost breakdown per SKU" in captured_goal_texts[1], (
        f"Refinement pass must include the missing text, got: {captured_goal_texts[1]!r}"
    )
