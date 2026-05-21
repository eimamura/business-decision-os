from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel


class OptimizationInput(BaseModel):
    sku_id: str
    moq: float = 100.0
    horizon_days: int = 90
    max_stockout_days: int = 30
    unit_cost: float = 10.0
    holding_cost_rate: float = 0.25
    shortage_penalty_per_day: float = 5.0


class CandidatePlan(BaseModel):
    order_qty: float
    total_supply_chain_cost: float
    constraints_satisfied: list[str]
    constraints_violated: list[str]
    simulation: dict[str, Any] = {}


class OptimizationOutput(BaseModel):
    candidates: list[CandidatePlan]


class OptimizationContext(BaseModel):
    session_id: UUID | None = None
    agent_step_id: UUID | None = None
    db_session: Any | None = None
    runner: Any | None = None

    model_config = {"arbitrary_types_allowed": True}


class Optimizer(Protocol):
    async def run(
        self, input: OptimizationInput, ctx: OptimizationContext
    ) -> OptimizationOutput: ...
