from __future__ import annotations

from packages.simulation.interfaces import (
    SimulationContext,
    SimulationInput,
    SimulationOutput,
)


class InventorySimulator:
    async def run(self, input: SimulationInput, ctx: SimulationContext) -> SimulationOutput:
        if ctx.db_session is not None:
            return await self._run_with_db(input, ctx)
        return await self._run_no_db(input)

    async def _run_no_db(self, input: SimulationInput) -> SimulationOutput:
        daily_demand = input.order_qty / input.horizon_days
        mean_lead_time_days = 14

        on_hand = [0.0] * (input.horizon_days + 1)
        on_hand[0] = input.order_qty

        for t in range(input.horizon_days):
            arrivals = 0.0
            on_hand[t + 1] = max(0.0, on_hand[t] + arrivals - daily_demand)

        daily_on_hand = on_hand[1:]
        ending_on_hand = daily_on_hand[-1] if daily_on_hand else 0.0
        stockout_days = sum(1 for v in daily_on_hand if v == 0.0)

        return SimulationOutput(
            sku_id=input.sku_id,
            ending_on_hand=ending_on_hand,
            stockout_days=stockout_days,
            mean_lead_time_days=mean_lead_time_days,
            daily_on_hand=daily_on_hand,
        )

    async def _run_with_db(
        self, input: SimulationInput, ctx: SimulationContext
    ) -> SimulationOutput:
        from sqlalchemy import text

        assert ctx.db_session is not None
        session = ctx.db_session

        demand_row = await session.execute(
            text(
                "SELECT AVG(quantity) as mean_demand FROM demand_history "
                "WHERE sku_id = :sku_id AND quantity IS NOT NULL"
            ),
            {"sku_id": input.sku_id},
        )
        row = demand_row.fetchone()
        daily_demand = float(row.mean_demand) if row and row.mean_demand is not None else (
            input.order_qty / input.horizon_days
        )

        inventory_row = await session.execute(
            text("SELECT on_hand FROM inventory WHERE sku_id = :sku_id LIMIT 1"),
            {"sku_id": input.sku_id},
        )
        inv = inventory_row.fetchone()
        initial_on_hand = float(inv.on_hand) if inv and inv.on_hand is not None else input.order_qty

        lead_row = await session.execute(
            text(
                "SELECT lead_time_days_mean as mean_lt FROM sku_master "
                "WHERE sku_id = :sku_id"
            ),
            {"sku_id": input.sku_id},
        )
        lt_row = lead_row.fetchone()
        mean_lead_time_days = int(lt_row.mean_lt) if lt_row and lt_row.mean_lt is not None else 14

        on_hand = [0.0] * (input.horizon_days + 1)
        on_hand[0] = initial_on_hand + input.order_qty

        for t in range(input.horizon_days):
            on_hand[t + 1] = max(0.0, on_hand[t] - daily_demand)

        daily_on_hand = on_hand[1:]
        ending_on_hand = daily_on_hand[-1] if daily_on_hand else 0.0
        stockout_days = sum(1 for v in daily_on_hand if v == 0.0)

        return SimulationOutput(
            sku_id=input.sku_id,
            ending_on_hand=ending_on_hand,
            stockout_days=stockout_days,
            mean_lead_time_days=mean_lead_time_days,
            daily_on_hand=daily_on_hand,
        )
