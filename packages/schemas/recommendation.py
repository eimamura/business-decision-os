from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class KpiScore(BaseModel):
    name: str
    value: float
    unit: str
    direction: Literal["higher_better", "lower_better"]


class Candidate(BaseModel):
    id: str
    action: dict[str, Any]
    kpi_scores: list[KpiScore]
    constraints_satisfied: list[str]
    constraints_violated: list[str]


class TradeoffExplanation(BaseModel):
    weight_vector: dict[str, float]
    weight_source: Literal["default", "user_policy", "session_goal", "critical_sku"]
    primary_vs_alternative: list[dict[str, Any]]


class Recommendation(BaseModel):
    primary: Candidate | None = None
    alternatives: list[Candidate] = []
    tradeoff: TradeoffExplanation | None = None
    rationale: str
    risk_level: Literal["low", "medium", "high"] = "low"
    requires_approval: bool = False
    direct_reply: str | None = None
