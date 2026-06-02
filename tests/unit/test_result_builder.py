from __future__ import annotations

from uuid import uuid4

from packages.agent.orchestrator.models import AgentRoute, SessionIntent, SessionResponse, SpecialistResult
from packages.agent.orchestrator.result_builder import build_response
from packages.schemas.recommendation import Candidate, KpiScore, TradeoffExplanation


def _make_candidate(candidate_id: str) -> Candidate:
    return Candidate(
        id=candidate_id,
        action={"order_qty": 100},
        kpi_scores=[
            KpiScore(name="service_level", value=0.9, unit="%", direction="higher_better")
        ],
        constraints_satisfied=["MOQ"],
        constraints_violated=[],
    )


def _make_intent(goal_text: str | None = "Replenish SKU-001") -> SessionIntent:
    return SessionIntent(
        category="decision_support",
        confidence=0.95,
        rationale="test",
        goal_text=goal_text,
    )


def _make_route() -> AgentRoute:
    return AgentRoute(
        mode="planned_execution",
        agents=["simulation_optimizer"],
        rationale="test route",
    )


def _make_tradeoff() -> TradeoffExplanation:
    return TradeoffExplanation(
        weight_vector={"service_level": 1.0},
        weight_source="default",
        primary_vs_alternative=[],
    )


def _make_specialist_result() -> SpecialistResult:
    return SpecialistResult(
        task_id=uuid4(),
        output={"candidates": []},
        tool_calls_made=[],
        status="completed",
    )


def test_build_response_returns_session_response() -> None:
    primary = _make_candidate("c1")
    alternatives = [_make_candidate("c2")]
    agent_results = {"simulation_optimizer": _make_specialist_result()}

    result = build_response(
        intent=_make_intent(),
        route=_make_route(),
        primary=primary,
        alternatives=alternatives,
        tradeoff=_make_tradeoff(),
        risk_level="low",
        requires_approval=False,
        agent_results=agent_results,
    )

    assert isinstance(result, SessionResponse)


def test_build_response_reply_contains_candidate_id() -> None:
    primary = _make_candidate("candidate-xyz-42")
    alternatives: list[Candidate] = []
    agent_results: dict[str, SpecialistResult] = {}

    result = build_response(
        intent=_make_intent("Optimize inventory"),
        route=_make_route(),
        primary=primary,
        alternatives=alternatives,
        tradeoff=_make_tradeoff(),
        risk_level="medium",
        requires_approval=True,
        agent_results=agent_results,
    )

    assert "candidate-xyz-42" in result.reply


def test_build_response_no_llm_calls() -> None:
    """build_response is a regular (sync) pure function — no async, no LLM."""
    import inspect

    primary = _make_candidate("c1")

    result = build_response(
        intent=_make_intent(),
        route=_make_route(),
        primary=primary,
        alternatives=[],
        tradeoff=_make_tradeoff(),
        risk_level="low",
        requires_approval=False,
        agent_results={},
    )

    # The function must not be a coroutine function (i.e. must be sync/pure).
    assert not inspect.iscoroutinefunction(build_response)
    # The return value must also not be a coroutine.
    assert not inspect.iscoroutine(result)


def test_build_response_goal_text_none_uses_na() -> None:
    """When intent.goal_text is None the reply must contain 'N/A'."""
    primary = _make_candidate("c1")

    result = build_response(
        intent=_make_intent(goal_text=None),
        route=_make_route(),
        primary=primary,
        alternatives=[],
        tradeoff=_make_tradeoff(),
        risk_level="low",
        requires_approval=False,
        agent_results={},
    )

    assert "N/A" in result.reply


def test_build_response_propagates_risk_and_approval() -> None:
    primary = _make_candidate("c1")

    result = build_response(
        intent=_make_intent(),
        route=_make_route(),
        primary=primary,
        alternatives=[],
        tradeoff=_make_tradeoff(),
        risk_level="high",
        requires_approval=True,
        agent_results={},
    )

    assert result.risk_level == "high"
    assert result.requires_approval is True
