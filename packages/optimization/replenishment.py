from __future__ import annotations

import pulp

from packages.optimization.interfaces import (
    CandidatePlan,
    OptimizationContext,
    OptimizationInput,
    OptimizationOutput,
)


def _compute_stockout_days(order_qty: float, horizon_days: int, moq: float) -> int:
    daily_demand = moq / horizon_days
    if daily_demand <= 0:
        return 0
    days_covered = int(order_qty / daily_demand)
    return max(0, horizon_days - days_covered)


def _compute_cost(inp: OptimizationInput, order_qty: float, stockout_days: int) -> float:
    holding_cost = order_qty * inp.unit_cost * inp.holding_cost_rate * (inp.horizon_days / 365)
    order_cost = order_qty * inp.unit_cost if order_qty > 0 else 0.0
    stockout_penalty = stockout_days * inp.shortage_penalty_per_day
    return holding_cost + order_cost + stockout_penalty


def _build_candidate(inp: OptimizationInput, m: int) -> CandidatePlan:
    order_qty = inp.moq * m
    stockout_days = _compute_stockout_days(order_qty, inp.horizon_days, inp.moq)
    total_cost = _compute_cost(inp, order_qty, stockout_days)

    satisfied: list[str] = []
    violated: list[str] = []

    if m >= 1:
        satisfied.append("MOQ")
    else:
        violated.append("MOQ")

    if stockout_days <= inp.max_stockout_days:
        satisfied.append("stockout_limit")
    else:
        violated.append("stockout_limit")

    return CandidatePlan(
        order_qty=order_qty,
        total_supply_chain_cost=total_cost,
        constraints_satisfied=satisfied,
        constraints_violated=violated,
        simulation={"estimated_stockout_days": stockout_days},
    )


def _select_top3_via_pulp(candidates: list[CandidatePlan]) -> list[CandidatePlan]:
    feasible_indices = [i for i, c in enumerate(candidates) if not c.constraints_violated]

    if len(feasible_indices) < 3:
        return sorted(candidates, key=lambda c: c.total_supply_chain_cost)[:3]

    prob = pulp.LpProblem("select_top3", pulp.LpMinimize)
    x = [pulp.LpVariable(f"x_{i}", cat="Binary") for i in range(len(candidates))]

    infeasible_indices = {i for i in range(len(candidates)) if candidates[i].constraints_violated}
    for i in infeasible_indices:
        prob += x[i] == 0

    prob += pulp.lpSum(x) == 3
    prob += pulp.lpSum(x[i] * candidates[i].total_supply_chain_cost for i in range(len(candidates)))

    prob.solve(pulp.PULP_CBC_CMD(msg=0))

    selected = [candidates[i] for i in range(len(candidates)) if pulp.value(x[i]) == 1.0]

    if len(selected) != 3:
        return sorted(candidates, key=lambda c: c.total_supply_chain_cost)[:3]

    return selected


class ReplenishmentOptimizer:
    async def run(self, input: OptimizationInput, ctx: OptimizationContext) -> OptimizationOutput:
        candidates = [_build_candidate(input, m) for m in range(6)]
        selected = _select_top3_via_pulp(candidates)
        selected.sort(key=lambda c: c.total_supply_chain_cost)
        return OptimizationOutput(candidates=selected)
