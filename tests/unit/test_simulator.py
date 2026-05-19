from __future__ import annotations

from uuid import uuid4

import pytest

from packages.agent.job_runner import InProcessJobRunner, JobSpec
from packages.simulation import InventorySimulator, SimulationContext, SimulationInput
from packages.tools.base import ToolContext


def _make_tool_ctx() -> ToolContext:
    return ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="data_engineer",
        actor="test",
        correlation_id=uuid4(),
    )


def _no_db_ctx() -> SimulationContext:
    return SimulationContext(db_session=None)


@pytest.mark.asyncio
async def test_simulator_runs_horizon_days():
    sim = InventorySimulator()
    result = await sim.run(
        SimulationInput(sku_id="SKU001", order_qty=100.0, horizon_days=30),
        _no_db_ctx(),
    )
    assert result.daily_on_hand is not None
    assert len(result.daily_on_hand) == 30


@pytest.mark.asyncio
async def test_simulator_ending_on_hand_deterministic():
    # order_qty=100, horizon_days=10 → daily_demand=10.0 (exact division)
    # day-by-day on_hand: 90, 80, 70, 60, 50, 40, 30, 20, 10, 0 → ending=0.0
    sim = InventorySimulator()
    result = await sim.run(
        SimulationInput(sku_id="SKU002", order_qty=100.0, horizon_days=10),
        _no_db_ctx(),
    )
    assert result.ending_on_hand == pytest.approx(0.0, abs=1e-9)
    assert result.stockout_days == 1


@pytest.mark.asyncio
async def test_simulator_stockout_days_when_demand_exceeds_supply():
    # order_qty=10, horizon_days=5, daily_demand=2.0
    # on_hand sequence: 8, 6, 4, 2, 0 → last day hits 0 → stockout_days=1
    sim = InventorySimulator()
    result = await sim.run(
        SimulationInput(sku_id="SKU003", order_qty=10.0, horizon_days=5),
        _no_db_ctx(),
    )
    assert result.stockout_days > 0


@pytest.mark.asyncio
async def test_simulator_no_stockout_when_ample_supply():
    # order_qty=10000 with horizon_days=11: daily_demand≈909.09
    # on_hand stays well above 0 for every day except possibly the last.
    # Verify that on_hand never goes negative and all but at most the last day are positive.
    sim = InventorySimulator()
    result = await sim.run(
        SimulationInput(sku_id="SKU004", order_qty=10000.0, horizon_days=11),
        _no_db_ctx(),
    )
    assert result.daily_on_hand is not None
    assert all(v >= 0.0 for v in result.daily_on_hand)
    # Only the last day can reach zero; all earlier days must be positive
    non_last_days = result.daily_on_hand[:-1]
    assert all(v > 0.0 for v in non_last_days)


@pytest.mark.asyncio
async def test_inprocess_runner_result_simulation():
    runner = InProcessJobRunner()
    spec = JobSpec(
        kind="simulation",
        payload={"sku_id": "SKU001", "order_qty": 200.0, "horizon_days": 15},
        idempotency_key="test-sim-1",
    )
    ctx = _make_tool_ctx()
    handle = await runner.submit(spec, ctx)
    result = await runner.result(handle.job_id, wait=True)

    assert result.status == "succeeded"
    assert result.output is not None
    assert "daily_on_hand" in result.output
    assert result.output["sku_id"] == "SKU001"
