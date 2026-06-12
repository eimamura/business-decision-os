"""identify_binding_constraint — T-558

Ranks supply-chain constraint candidates by estimated negative financial impact.

## Constraint candidate classes

Three classes are evaluated.  Each produces zero or more candidate records.
All candidates across all classes are merged, sorted by impact, and returned
as a ranked list.

### 1. Production capacity overload (class: production_capacity)

  For each (location_id, week_start) in production_capacity:

    utilization    = Σ planned_qty / capacity_units
    overload_units = max(0, Σ planned_qty - capacity_units)

  Impact estimate = overload_units × avg_stockout_cost

  avg_stockout_cost is the average cost_master.stockout_cost of SKUs that are
  planned at that location in that week.  This is a deliberate simplification:
  because the agent cannot know which units will actually be cut when capacity
  is exceeded, the average cost across the planned SKU mix is used as a
  reasonable upper-bound proxy.

  Evidence payload: {location_id, week_start, capacity_units, planned_units,
                     utilization, overload_units, avg_stockout_cost}

### 2. Inbound supply gap (class: supply_gap)

  Reuses the supply-gap pattern from supply_gap_tool.py:

    For each SKU in supply_orders with open status (pending/confirmed/in_transit):
      on_hand        = Σ inventory_snapshot.on_hand
      incoming_qty   = Σ supply_orders.quantity (open, arriving within horizon)
      avg_daily      = AVG(demand_history.quantity) over last 30 days
      forecast_demand = avg_daily × horizon_days
      supply_gap_units = max(0, forecast_demand - (on_hand + incoming_qty))

    Impact estimate = supply_gap_units × cost_master.stockout_cost

  Only SKUs with supply_gap_units > 0 produce a constraint record.
  The horizon used is 7 days (one week) — matching the production cadence.

  Evidence payload: {sku_id, on_hand, incoming_qty, forecast_demand,
                     supply_gap_units, stockout_cost}

### 3. Inventory-driven lost-sales (class: inventory_stockout)

  Uses the stockout-risk pattern from list_stockout_risk_tool.py:

    For each SKU in inventory_snapshot:
      projected_ending_stock = on_hand + incoming_supply - forecast_demand
      (30-day avg_daily × 7 days horizon)

    Only critical / high risk SKUs are included (using the classify_stockout_risk
    thresholds from _shared.py).

    shortfall_units = max(0, -projected_ending_stock)
    Impact estimate = shortfall_units × cost_master.stockout_cost

  Evidence payload: {sku_id, projected_ending_stock, shortfall_units, stockout_cost}

## Ranking formula (documented)

All constraint records are merged and sorted by impact_estimate descending.
Deterministic tie-break: impact_estimate DESC, then subject (location/sku) ASC.

## Output contract (hybrid)

- ``constraints`` : ranked list of constraint records, capped to ROW_CAP with
                    ``truncated`` flag.
- ``missing_data``: SKUs or locations that could not be fully evaluated because
                    cost_master rows are absent.
- ANALYTICAL OUTPUT ONLY.  No recommendations, no "you should" wording anywhere
  in output fields or descriptions.  The Control Agent concludes.

## Constraints

No LLM calls. All SQL parameterized. Tables used:
  production_capacity, production_plan, inventory_snapshot, supply_orders,
  demand_history, cost_master
All are in ALLOWED_READ_TABLES.

Output follows the hybrid tool output contract
(ADR docs/adr/2026-06-10-tool-output-contract-hybrid.md).
"""
from __future__ import annotations

import logging
from typing import Any, Literal

from packages.persistence.db import get_pool
from packages.tools._shared import classify_stockout_risk, db_error_message
from packages.tools.base import ToolContext, ToolResult

_log = logging.getLogger(__name__)

# Row cap for returned constraint records.
_ROW_CAP = 50

# Supply-gap horizon in days (aligns with weekly production cadence).
_SUPPLY_HORIZON_DAYS = 7

# Open supply order statuses.
_OPEN_STATUSES = ["pending", "confirmed", "in_transit"]

# Risk levels treated as high-concern for inventory-stockout class.
_HIGH_RISK_LEVELS = {"critical", "high"}

# Demand history look-back for run-rate (days).
_RUNRATE_LOOKBACK_DAYS = 30


class IdentifyBindingConstraintTool:
    """Rank supply-chain constraint candidates by estimated negative financial impact.

    Evaluates three candidate classes: production capacity overload, inbound supply gap,
    and inventory-driven lost-sales exposure.  Returns a ranked list of constraints
    with impact estimates and evidence numbers.

    Analytical output only — no recommendations.  No LLM calls — deterministic SQL only.
    """

    name = "identify_binding_constraint"
    description = (
        "Rank supply-chain constraint candidates by estimated negative impact. "
        "Three candidate classes are evaluated: "
        "(1) production_capacity: capacity overload per location-week "
        "(overload_units × avg stockout cost); "
        "(2) supply_gap: inbound supply shortfall per SKU over a 7-day horizon "
        "(gap_units × stockout cost); "
        "(3) inventory_stockout: critical/high-risk SKU shortfall "
        "(shortfall × stockout cost). "
        "Returns ranked constraints with impact_estimate and evidence numbers. "
        "Call this for SPEC Q10 — 'which constraint has the biggest negative impact?'. "
        "Analytical output only — does not recommend actions."
    )
    safety_level: Literal["read_only", "write", "hitl"] = "read_only"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "location_id": {
                "type": "string",
                "description": (
                    "Optional: restrict production-capacity analysis to a specific "
                    "location_id. Supply-gap and stockout analysis remain global."
                ),
            },
        },
        "required": [],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "constraints": {
                "type": "array",
                "description": (
                    "Constraint candidates ranked by impact_estimate descending. "
                    "Tie-break: subject ASC."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "constraint_type": {
                            "type": "string",
                            "enum": [
                                "production_capacity",
                                "supply_gap",
                                "inventory_stockout",
                            ],
                        },
                        "subject": {
                            "type": "string",
                            "description": (
                                "location_id for production_capacity; "
                                "sku_id for supply_gap and inventory_stockout."
                            ),
                        },
                        "impact_estimate": {
                            "type": "number",
                            "description": "Estimated financial impact in cost units.",
                        },
                        "evidence": {
                            "type": "object",
                            "description": "Numbers used to derive impact_estimate.",
                        },
                    },
                    "required": [
                        "constraint_type",
                        "subject",
                        "impact_estimate",
                        "evidence",
                    ],
                },
            },
            "truncated": {"type": "boolean"},
            "missing_data": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "SKUs or locations that could not be evaluated because "
                    "cost_master rows are absent."
                ),
            },
        },
        "required": ["constraints", "truncated", "missing_data"],
    }

    def __init__(self, db_session: Any | None = None) -> None:
        pass

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:  # noqa: A002
        location_filter: str | None = input.get("location_id") or None

        try:
            cost_map, cost_missing_skus = await _fetch_cost_map()
        except Exception as exc:
            return ToolResult(
                output={"error": db_error_message(exc)},
                audit_payload={"location_id": location_filter},
            )

        constraints: list[dict[str, Any]] = []
        missing_data: list[str] = []
        missing_data.extend(cost_missing_skus)

        # --- Class 1: Production capacity overload ---
        try:
            cap_constraints, cap_missing = await _evaluate_capacity_overload(
                location_filter, cost_map
            )
            constraints.extend(cap_constraints)
            missing_data.extend(cap_missing)
        except Exception as exc:
            _log.warning("Capacity overload evaluation failed: %s", exc)
            missing_data.append(f"production_capacity evaluation error: {db_error_message(exc)}")

        # --- Class 2: Inbound supply gap ---
        try:
            supply_constraints, supply_missing = await _evaluate_supply_gap(cost_map)
            constraints.extend(supply_constraints)
            missing_data.extend(supply_missing)
        except Exception as exc:
            _log.warning("Supply gap evaluation failed: %s", exc)
            missing_data.append(f"supply_gap evaluation error: {db_error_message(exc)}")

        # --- Class 3: Inventory-driven lost-sales ---
        try:
            inv_constraints, inv_missing = await _evaluate_inventory_stockout(cost_map)
            constraints.extend(inv_constraints)
            missing_data.extend(inv_missing)
        except Exception as exc:
            _log.warning("Inventory stockout evaluation failed: %s", exc)
            missing_data.append(f"inventory_stockout evaluation error: {db_error_message(exc)}")

        # Ranking: impact_estimate DESC, subject ASC (deterministic tie-break)
        constraints.sort(key=lambda c: (-c["impact_estimate"], c["subject"]))

        truncated = len(constraints) > _ROW_CAP
        constraints = constraints[:_ROW_CAP]

        return ToolResult(
            output={
                "constraints": constraints,
                "truncated": truncated,
                "missing_data": missing_data,
            },
            audit_payload={
                "location_id": location_filter,
                "constraint_count": len(constraints),
                "truncated": truncated,
            },
        )


# ---------------------------------------------------------------------------
# SQL helpers — cost_master
# ---------------------------------------------------------------------------


async def _fetch_cost_map() -> tuple[dict[str, float], list[str]]:
    """Return ({sku_id: stockout_cost}, missing_notes).

    missing_notes is populated when the cost_master table exists but is empty.
    Cost rows are optional for each SKU — absent SKUs get a 0.0 cost (noted in
    missing_data by the constraint evaluators).
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT sku_id, COALESCE(stockout_cost, 0) AS stockout_cost
            FROM cost_master
            WHERE stockout_cost IS NOT NULL AND stockout_cost > 0
            """
        )
        cost_map: dict[str, float] = {str(r["sku_id"]): float(r["stockout_cost"]) for r in rows}
        missing_notes: list[str] = []
        if not cost_map:
            missing_notes.append("cost_master: no rows with stockout_cost > 0 found")
        return cost_map, missing_notes


# ---------------------------------------------------------------------------
# Class 1 — Production capacity overload
# ---------------------------------------------------------------------------


async def _evaluate_capacity_overload(
    location_filter: str | None,
    cost_map: dict[str, float],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Produce constraint records for overloaded location-weeks.

    Impact = overload_units × avg_stockout_cost of SKUs planned at that location-week.

    Strategy: aggregate production_plan per (location_id, week_start), then join
    with production_capacity to detect overloads.  Separately, compute avg
    stockout_cost for SKUs in the plan for each overloaded location-week.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Step 1: aggregate planned_qty per location-week, join capacity
        if location_filter:
            rows = await conn.fetch(
                """
                SELECT
                    pc.location_id,
                    pc.week_start,
                    pc.capacity_units,
                    COALESCE(SUM(pp.planned_qty), 0) AS planned_units
                FROM production_capacity pc
                LEFT JOIN production_plan pp
                       ON pp.location_id = pc.location_id
                      AND pp.week_start  = pc.week_start
                WHERE pc.location_id = $1
                GROUP BY pc.location_id, pc.week_start, pc.capacity_units
                ORDER BY pc.week_start, pc.location_id
                """,
                location_filter,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT
                    pc.location_id,
                    pc.week_start,
                    pc.capacity_units,
                    COALESCE(SUM(pp.planned_qty), 0) AS planned_units
                FROM production_capacity pc
                LEFT JOIN production_plan pp
                       ON pp.location_id = pc.location_id
                      AND pp.week_start  = pc.week_start
                GROUP BY pc.location_id, pc.week_start, pc.capacity_units
                ORDER BY pc.week_start, pc.location_id
                """
            )

        # Step 2: for overloaded rows, compute avg stockout cost from plan
        constraints: list[dict[str, Any]] = []
        missing_notes: list[str] = []

        for row in rows:
            capacity_units = float(row["capacity_units"])
            planned_units = float(row["planned_units"])

            if capacity_units <= 0:
                continue

            utilization = planned_units / capacity_units
            overload_units = max(0.0, planned_units - capacity_units)

            if overload_units <= 0:
                continue

            # Avg stockout cost of SKUs in this location-week
            location_id: str = str(row["location_id"])
            week_start: str = str(row["week_start"])

            sku_rows = await conn.fetch(
                """
                SELECT sku_id
                FROM production_plan
                WHERE location_id = $1
                  AND week_start  = $2
                  AND planned_qty > 0
                """,
                location_id,
                row["week_start"],
            )
            sku_ids_in_plan = [str(r["sku_id"]) for r in sku_rows]

            if not sku_ids_in_plan:
                missing_notes.append(
                    f"production_capacity {location_id} {week_start}: "
                    "no SKU plan rows found for cost estimation"
                )
                continue

            costs = [cost_map.get(s, 0.0) for s in sku_ids_in_plan]
            known_costs = [c for c in costs if c > 0]

            if not known_costs:
                missing_notes.append(
                    f"production_capacity {location_id} {week_start}: "
                    f"no cost_master rows for {len(sku_ids_in_plan)} planned SKUs"
                )
                avg_cost = 0.0
            else:
                avg_cost = sum(known_costs) / len(known_costs)

            impact_estimate = overload_units * avg_cost

            constraints.append(
                {
                    "constraint_type": "production_capacity",
                    "subject": f"{location_id}:{week_start}",
                    "impact_estimate": round(impact_estimate, 4),
                    "evidence": {
                        "location_id": location_id,
                        "week_start": week_start,
                        "capacity_units": capacity_units,
                        "planned_units": planned_units,
                        "utilization": round(utilization, 4),
                        "overload_units": overload_units,
                        "avg_stockout_cost": round(avg_cost, 4),
                    },
                }
            )

    return constraints, missing_notes


# ---------------------------------------------------------------------------
# Class 2 — Inbound supply gap
# ---------------------------------------------------------------------------


async def _evaluate_supply_gap(
    cost_map: dict[str, float],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Produce constraint records for SKUs with inbound supply gaps.

    Follows the pattern from supply_gap_tool.py: on_hand + incoming - forecast_demand.
    Horizon = SUPPLY_HORIZON_DAYS (7 days, weekly cadence).

    Impact = supply_gap_units × cost_master.stockout_cost.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                inv.sku_id,
                COALESCE(inv.on_hand_qty, 0)     AS on_hand,
                COALESCE(so.incoming_qty, 0)      AS incoming_qty,
                COALESCE(dh.avg_daily, 0)         AS avg_daily
            FROM (
                SELECT sku_id, SUM(on_hand) AS on_hand_qty
                FROM inventory_snapshot
                GROUP BY sku_id
            ) inv
            LEFT JOIN (
                SELECT sku_id, SUM(quantity) AS incoming_qty
                FROM supply_orders
                WHERE status = ANY($1)
                  AND expected_arrival <= CURRENT_DATE + ($2 * INTERVAL '1 day')
                GROUP BY sku_id
            ) so ON so.sku_id = inv.sku_id
            LEFT JOIN (
                SELECT sku_id, AVG(quantity) AS avg_daily
                FROM demand_history
                WHERE date >= CURRENT_DATE - ($3 * INTERVAL '1 day')
                  AND is_missing IS NOT TRUE
                GROUP BY sku_id
            ) dh ON dh.sku_id = inv.sku_id
            ORDER BY inv.sku_id
            """,
            _OPEN_STATUSES,
            _SUPPLY_HORIZON_DAYS,
            _RUNRATE_LOOKBACK_DAYS,
        )

    constraints: list[dict[str, Any]] = []
    missing_notes: list[str] = []

    for row in rows:
        sku_id: str = str(row["sku_id"])
        on_hand = float(row["on_hand"])
        incoming_qty = float(row["incoming_qty"])
        avg_daily = float(row["avg_daily"])

        forecast_demand = avg_daily * _SUPPLY_HORIZON_DAYS
        total_available = on_hand + incoming_qty
        supply_gap_units = max(0.0, forecast_demand - total_available)

        if supply_gap_units <= 0:
            continue

        stockout_cost = cost_map.get(sku_id, 0.0)
        if stockout_cost == 0.0 and sku_id not in cost_map:
            missing_notes.append(
                f"supply_gap {sku_id}: no cost_master row — impact_estimate is 0"
            )

        impact_estimate = supply_gap_units * stockout_cost

        constraints.append(
            {
                "constraint_type": "supply_gap",
                "subject": sku_id,
                "impact_estimate": round(impact_estimate, 4),
                "evidence": {
                    "sku_id": sku_id,
                    "on_hand": on_hand,
                    "incoming_qty": incoming_qty,
                    "forecast_demand": forecast_demand,
                    "supply_gap_units": supply_gap_units,
                    "stockout_cost": stockout_cost,
                },
            }
        )

    return constraints, missing_notes


# ---------------------------------------------------------------------------
# Class 3 — Inventory-driven lost-sales
# ---------------------------------------------------------------------------


async def _evaluate_inventory_stockout(
    cost_map: dict[str, float],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Produce constraint records for critical/high-risk SKUs.

    Follows list_stockout_risk_tool.py pattern:
      avg_daily = 30-day demand history run-rate
      demand_forecast = avg_daily × 7 days
      projected_ending_stock = on_hand + incoming_supply - demand_forecast
      shortfall_units = max(0, -projected_ending_stock)

    Impact = shortfall_units × stockout_cost.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                inv.sku_id,
                COALESCE(inv.on_hand_qty, 0)     AS on_hand_qty,
                COALESCE(dh.avg_daily, 0)         AS avg_daily,
                COALESCE(so.incoming_supply, 0)   AS incoming_supply
            FROM (
                SELECT sku_id, SUM(on_hand) AS on_hand_qty
                FROM inventory_snapshot
                GROUP BY sku_id
            ) inv
            LEFT JOIN (
                SELECT sku_id, AVG(quantity) AS avg_daily
                FROM demand_history
                WHERE date >= CURRENT_DATE - ($1 * INTERVAL '1 day')
                  AND is_missing IS NOT TRUE
                GROUP BY sku_id
            ) dh ON dh.sku_id = inv.sku_id
            LEFT JOIN (
                SELECT sku_id, SUM(quantity) AS incoming_supply
                FROM supply_orders
                WHERE status = ANY($2)
                  AND expected_arrival <= CURRENT_DATE + ($3 * INTERVAL '1 day')
                GROUP BY sku_id
            ) so ON so.sku_id = inv.sku_id
            ORDER BY inv.sku_id
            """,
            _RUNRATE_LOOKBACK_DAYS,
            _OPEN_STATUSES,
            _SUPPLY_HORIZON_DAYS,
        )

    constraints: list[dict[str, Any]] = []
    missing_notes: list[str] = []

    for row in rows:
        sku_id = str(row["sku_id"])
        on_hand_qty = float(row["on_hand_qty"])
        avg_daily = float(row["avg_daily"])
        incoming_supply = float(row["incoming_supply"])

        demand_forecast = avg_daily * _SUPPLY_HORIZON_DAYS
        projected_ending_stock = on_hand_qty + incoming_supply - demand_forecast

        risk_level = classify_stockout_risk(projected_ending_stock, demand_forecast)

        if risk_level not in _HIGH_RISK_LEVELS:
            continue

        shortfall_units = max(0.0, -projected_ending_stock)

        stockout_cost = cost_map.get(sku_id, 0.0)
        if stockout_cost == 0.0 and sku_id not in cost_map:
            missing_notes.append(
                f"inventory_stockout {sku_id}: no cost_master row — impact_estimate is 0"
            )

        impact_estimate = shortfall_units * stockout_cost

        constraints.append(
            {
                "constraint_type": "inventory_stockout",
                "subject": sku_id,
                "impact_estimate": round(impact_estimate, 4),
                "evidence": {
                    "sku_id": sku_id,
                    "projected_ending_stock": projected_ending_stock,
                    "shortfall_units": shortfall_units,
                    "stockout_cost": stockout_cost,
                    "risk_level": risk_level,
                },
            }
        )

    return constraints, missing_notes
