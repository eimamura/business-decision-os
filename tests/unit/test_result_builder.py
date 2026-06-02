from __future__ import annotations

from uuid import uuid4

from packages.agent.orchestrator.models import AgentRoute, SessionIntent, SessionResponse, SpecialistResult
from packages.agent.orchestrator.result_builder import build_job_result_reply, build_response
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


def test_build_job_result_reply_contains_job_type() -> None:
    reply = build_job_result_reply(job_type="simulate", result=None, files=[])
    assert "simulate" in reply


def test_build_job_result_reply_includes_scalar_result_fields() -> None:
    result = {"status": "ok", "items": 42, "cost": 3.14, "nested": {"a": 1}}
    reply = build_job_result_reply(job_type="optimize", result=result, files=[])
    assert "status: ok" in reply
    assert "items: 42" in reply
    assert "cost: 3.14" in reply
    # nested dict must not appear (not a scalar)
    assert "nested" not in reply


def test_build_job_result_reply_at_most_three_scalar_fields() -> None:
    result = {"a": 1, "b": 2, "c": 3, "d": 4}
    reply = build_job_result_reply(job_type="forecast", result=result, files=[])
    # Only 3 of the 4 scalar fields should appear
    shown = sum(1 for k in ("a", "b", "c", "d") if f"- {k}:" in reply)
    assert shown == 3


def test_build_job_result_reply_includes_file_links() -> None:
    files = [
        {"file_name": "report.csv", "download_url": "https://example.com/report.csv"},
        {"file_name": "summary.pdf", "download_url": "https://example.com/summary.pdf"},
    ]
    reply = build_job_result_reply(job_type="simulate", result=None, files=files)
    assert "[report.csv](https://example.com/report.csv)" in reply
    assert "[summary.pdf](https://example.com/summary.pdf)" in reply
    assert "2 file(s) generated" in reply


def test_build_job_result_reply_file_without_url_shows_name_only() -> None:
    files = [{"file_name": "output.csv", "download_url": ""}]
    reply = build_job_result_reply(job_type="simulate", result=None, files=files)
    assert "- output.csv" in reply
    # no markdown link syntax when url is empty
    assert "[output.csv](" not in reply


def test_build_job_result_reply_no_files_no_file_section() -> None:
    reply = build_job_result_reply(job_type="forecast", result={"score": 0.9}, files=[])
    assert "file(s) generated" not in reply


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
