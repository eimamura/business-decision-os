from __future__ import annotations

from uuid import uuid4

import pytest

from packages.schemas.recommendation import Candidate, KpiScore, Recommendation, TradeoffExplanation
from packages.schemas.evaluations import EvaluationCriteria, EvaluationResult
from packages.schemas.sse_events import (
    SessionStartedEvent,
    ToolCalledEvent,
    RecommendationReadyEvent,
    ErrorEvent,
    DoneEvent,
    SseEvent,
)


def _make_kpi_score() -> KpiScore:
    return KpiScore(name="service_level", value=0.95, unit="%", direction="higher_better")


def _make_candidate() -> Candidate:
    return Candidate(
        id="c1",
        action={"order_qty": 100},
        kpi_scores=[_make_kpi_score()],
        constraints_satisfied=["MOQ"],
        constraints_violated=[],
    )


def test_kpi_score_schema():
    score = _make_kpi_score()
    assert score.name == "service_level"
    assert score.direction == "higher_better"


def test_recommendation_schema():
    candidate = _make_candidate()
    tradeoff = TradeoffExplanation(
        weight_vector={"service_level": 0.30},
        weight_source="default",
        primary_vs_alternative=[],
    )
    rec = Recommendation(
        primary=candidate,
        alternatives=[candidate],
        tradeoff=tradeoff,
        rationale="Test rationale",
        risk_level="low",
        requires_approval=False,
    )
    assert rec.risk_level == "low"
    assert len(rec.alternatives) == 1


def test_evaluation_criteria_schema():
    criteria = EvaluationCriteria(
        kpi_names=["service_level"],
        weights={"service_level": 1.0},
        risk_thresholds={},
    )
    assert criteria.kpi_names == ["service_level"]


def test_evaluation_result_schema():
    result = EvaluationResult(
        candidate_id="c1",
        kpi_scores=[_make_kpi_score()],
        risk_level="medium",
    )
    assert result.risk_level == "medium"


def test_sse_session_started():
    event = SessionStartedEvent(session_id=uuid4(), timestamp="2026-01-01T00:00:00Z")
    assert event.event == "session_started"


def test_sse_done():
    event = DoneEvent(session_id=uuid4(), timestamp="2026-01-01T00:00:00Z")
    assert event.event == "done"


def test_sse_error():
    event = ErrorEvent(
        session_id=uuid4(),
        timestamp="2026-01-01T00:00:00Z",
        code="TOOL_FAILURE",
        message="Tool failed",
        recoverable=False,
    )
    assert event.event == "error"
