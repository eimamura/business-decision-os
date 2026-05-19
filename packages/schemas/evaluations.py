from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from packages.schemas.recommendation import KpiScore


class EvaluationCriteria(BaseModel):
    kpi_names: list[str]
    weights: dict[str, float]
    risk_thresholds: dict


class EvaluationResult(BaseModel):
    candidate_id: str
    kpi_scores: list[KpiScore]
    risk_level: Literal["low", "medium", "high"]
