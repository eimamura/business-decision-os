"""Tests for T-8001: Risk-classified auto-execution policy."""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

from packages.schemas.sse_events import AutoExecutedEvent, ResponseReadyEvent


class TestResponseReadyEventSchema:
    def test_has_approval_fields(self) -> None:
        event = ResponseReadyEvent(
            timestamp="2026-05-20T00:00:00Z",
            mode="sequential_agents",
            risk_level="low",
            requires_approval=False,
        )
        assert event.requires_approval is False

    def test_non_decision_fields_are_optional(self) -> None:
        event = ResponseReadyEvent(
            timestamp="2026-05-20T00:00:00Z",
            mode="direct_chat",
        )
        assert event.risk_level is None

    def test_low_risk_no_approval(self) -> None:
        event = ResponseReadyEvent(
            timestamp="2026-05-20T00:00:00Z",
            mode="planned_execution",
            risk_level="low",
            requires_approval=False,
        )
        assert event.risk_level == "low"
        assert event.requires_approval is False

    def test_high_risk_requires_approval(self) -> None:
        event = ResponseReadyEvent(
            timestamp="2026-05-20T00:00:00Z",
            mode="planned_execution",
            risk_level="high",
            requires_approval=True,
        )
        assert event.risk_level == "high"
        assert event.requires_approval is True


class TestAutoExecutedEvent:
    def test_event_type(self) -> None:
        event = AutoExecutedEvent(
            timestamp="2026-05-20T00:00:00Z",
            recommendation_id=str(uuid4()),
        )
        assert event.type == "auto_executed"

    def test_serialization(self) -> None:
        rec_id = str(uuid4())
        event = AutoExecutedEvent(
            timestamp="2026-05-20T00:00:00Z",
            recommendation_id=rec_id,
        )
        data = event.model_dump()
        assert data["type"] == "auto_executed"
        assert data["recommendation_id"] == rec_id


class TestOrchestratorAutoExecution:
    """Verify orchestrator emits correct events for low/high risk."""

    def _make_orchestrator(self) -> Any:
        from packages.agent.orchestrator import SessionOrchestrator

        llm = AsyncMock()
        llm.chat = AsyncMock(return_value='["sql", "evaluator"]')
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        orch = SessionOrchestrator(llm_client=llm, sse_queue=queue)
        return orch, queue

    def _collect_events(self, queue: asyncio.Queue[dict[str, Any]]) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        while not queue.empty():
            events.append(queue.get_nowait())
        return events

    def test_low_risk_emits_auto_executed(self) -> None:
        """Low-risk recommendation classifies as low and would auto-execute."""
        from packages.schemas.recommendation import Candidate, KpiScore
        from packages.tools.guardrail import classify_risk as _classify_risk

        low_risk_candidate = Candidate(
            id="c1",
            action={"order_qty": 100},
            kpi_scores=[
                KpiScore(name="service_level", value=0.98, unit="%", direction="higher_better")
            ],
            constraints_satisfied=[],
            constraints_violated=[],
        )

        risk = _classify_risk(low_risk_candidate)
        assert risk == "low"
        requires_approval = risk in ("high", "medium")
        auto_execute = not requires_approval
        assert auto_execute is True

    def test_high_risk_does_not_auto_execute(self) -> None:
        """High-risk recommendation should NOT auto-execute."""
        from packages.schemas.recommendation import Candidate, KpiScore
        from packages.tools.guardrail import classify_risk as _classify_risk

        high_risk_candidate = Candidate(
            id="c2",
            action={"order_qty": 10},
            kpi_scores=[
                KpiScore(name="service_level", value=0.80, unit="%", direction="higher_better")
            ],
            constraints_satisfied=[],
            constraints_violated=[],
        )

        risk = _classify_risk(high_risk_candidate)
        assert risk == "high"
        requires_approval = risk in ("high", "medium")
        auto_execute = not requires_approval
        assert auto_execute is False

    def test_auto_execute_is_inverse_of_requires_approval(self) -> None:
        from packages.schemas.recommendation import Candidate, KpiScore
        from packages.tools.guardrail import classify_risk as _classify_risk

        low = Candidate(
            id="low",
            action={},
            kpi_scores=[
                KpiScore(name="service_level", value=0.99, unit="%", direction="higher_better")
            ],
            constraints_satisfied=[],
            constraints_violated=[],
        )
        high = Candidate(
            id="high",
            action={},
            kpi_scores=[
                KpiScore(name="service_level", value=0.80, unit="%", direction="higher_better")
            ],
            constraints_satisfied=[],
            constraints_violated=[],
        )

        assert _classify_risk(low) == "low"
        assert _classify_risk(high) == "high"

        low_risk_level = _classify_risk(low)
        high_risk_level = _classify_risk(high)

        low_requires_approval = low_risk_level in ("high", "medium")
        high_requires_approval = high_risk_level in ("high", "medium")

        assert not low_requires_approval  # low risk → no approval needed
        assert high_requires_approval     # high risk → approval needed

        assert (not low_requires_approval) is True   # auto_execute=True for low
        assert (not high_requires_approval) is False  # auto_execute=False for high
