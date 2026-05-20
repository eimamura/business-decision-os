from __future__ import annotations

import pytest

from packages.agent.job_runner import InProcessJobRunner, JobSpec
from packages.optimization import (
    OptimizationContext,
    OptimizationInput,
    OptimizationOutput,
    ReplenishmentOptimizer,
)
from packages.tools.base import ToolContext
from uuid import uuid4


def _make_tool_ctx() -> ToolContext:
    return ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="sim_opt",
        actor="test",
        correlation_id=uuid4(),
    )


def _default_input(**kwargs) -> OptimizationInput:
    defaults = {"sku_id": "SKU-001", "moq": 100.0, "horizon_days": 90}
    defaults.update(kwargs)
    return OptimizationInput(**defaults)


def _no_job_ctx() -> OptimizationContext:
    return OptimizationContext(db_session=None)


@pytest.mark.asyncio
async def test_returns_exactly_3_candidates():
    optimizer = ReplenishmentOptimizer()
    result = await optimizer.run(_default_input(), _no_job_ctx())
    assert isinstance(result, OptimizationOutput)
    assert len(result.candidates) == 3


@pytest.mark.asyncio
async def test_candidates_sorted_by_cost_ascending():
    optimizer = ReplenishmentOptimizer()
    result = await optimizer.run(_default_input(), _no_job_ctx())
    costs = [c.total_supply_chain_cost for c in result.candidates]
    assert costs == sorted(costs)


@pytest.mark.asyncio
async def test_feasible_candidates_preferred():
    optimizer = ReplenishmentOptimizer()
    result = await optimizer.run(_default_input(max_stockout_days=90), _no_job_ctx())
    for candidate in result.candidates:
        assert not candidate.constraints_violated, (
            f"Expected all selected to be feasible, got violated={candidate.constraints_violated}"
        )


@pytest.mark.asyncio
async def test_moq_constraint_in_satisfied():
    optimizer = ReplenishmentOptimizer()
    result = await optimizer.run(_default_input(), _no_job_ctx())
    for candidate in result.candidates:
        if candidate.order_qty >= 100.0:
            assert "MOQ" in candidate.constraints_satisfied


@pytest.mark.asyncio
async def test_order_qty_is_moq_multiple():
    moq = 150.0
    optimizer = ReplenishmentOptimizer()
    result = await optimizer.run(_default_input(moq=moq), _no_job_ctx())
    for candidate in result.candidates:
        remainder = candidate.order_qty % moq
        assert remainder == pytest.approx(0.0, abs=1e-9)


@pytest.mark.asyncio
async def test_total_cost_positive_for_nonzero_qty():
    optimizer = ReplenishmentOptimizer()
    result = await optimizer.run(_default_input(), _no_job_ctx())
    for candidate in result.candidates:
        if candidate.order_qty > 0:
            assert candidate.total_supply_chain_cost > 0


@pytest.mark.asyncio
async def test_simulation_dict_present():
    optimizer = ReplenishmentOptimizer()
    result = await optimizer.run(_default_input(), _no_job_ctx())
    for candidate in result.candidates:
        assert isinstance(candidate.simulation, dict)
        assert "estimated_stockout_days" in candidate.simulation


@pytest.mark.asyncio
async def test_inprocess_runner_optimization():
    runner = InProcessJobRunner()
    spec = JobSpec(
        kind="optimization",
        payload={"sku_id": "SKU-002", "moq": 200.0, "horizon_days": 60, "max_stockout_days": 30},
        idempotency_key="test-opt-1",
    )
    ctx = _make_tool_ctx()
    handle = await runner.submit(spec, ctx)
    result = await runner.result(handle.job_id, wait=True)

    assert result.status == "succeeded"
    assert result.output is not None
    assert "candidates" in result.output
    assert len(result.output["candidates"]) == 3
