from __future__ import annotations

import pytest

from packages.agent.orchestrator.decision import _rank_candidates


def test_rank_candidates_empty_raises_value_error() -> None:
    with pytest.raises(ValueError, match="No candidates were generated"):
        _rank_candidates([], weights={})


def test_rank_candidates_returns_primary_and_others() -> None:
    raw = [
        {
            "id": "c1",
            "action": {"order_qty": 100.0},
            "kpi_scores": [
                {"name": "service_level", "value": 0.9, "unit": "%", "direction": "higher_better"}
            ],
            "constraints_satisfied": ["MOQ"],
            "constraints_violated": [],
        },
        {
            "id": "c2",
            "action": {"order_qty": 200.0},
            "kpi_scores": [
                {"name": "service_level", "value": 0.7, "unit": "%", "direction": "higher_better"}
            ],
            "constraints_satisfied": ["MOQ"],
            "constraints_violated": [],
        },
    ]
    weights = {"service_level": 1.0}
    primary, others = _rank_candidates(raw, weights)
    assert primary.id == "c1"
    assert len(others) == 1
    assert others[0].id == "c2"
