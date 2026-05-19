from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel


class SimulationInput(BaseModel):
    sku_id: str
    order_qty: float
    horizon_days: int = 90


class SimulationOutput(BaseModel):
    sku_id: str
    ending_on_hand: float
    stockout_days: int
    mean_lead_time_days: int
    daily_on_hand: list[float] | None = None


class SimulationContext(BaseModel):
    session_id: UUID | None = None
    db_session: Any | None = None

    model_config = {"arbitrary_types_allowed": True}


class Simulator(Protocol):
    async def run(self, input: SimulationInput, ctx: SimulationContext) -> SimulationOutput: ...
