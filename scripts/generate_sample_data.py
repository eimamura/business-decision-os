#!/usr/bin/env python3
"""Generate synthetic operational sample data for Business Decision OS.

Usage:
    uv run python scripts/generate_sample_data.py [--seed N]

Outputs written to data/sample/ (NOT ground_truth/).
"""
from __future__ import annotations

import argparse
import csv
import math
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

CsvRow = dict[str, str]

# START_DATE is relative to today so that demand_history always covers the last 365 days
# and the tools' 30-day rolling window always has data on re-seed.
START_DATE = date.today() - timedelta(days=365)

# ---------------------------------------------------------------------------
# Deterministic order-to-ship scenario constants (P87 T-541)
#
# Scenario assignment uses fixed indices so outcomes are independently
# verifiable without running the generator (P84 convention).
#
# SCENARIO_ORDER_IDS maps order_id → scenario label for documentation.
# The actual scenario is encoded in the data via status / shipment fields.
# ---------------------------------------------------------------------------

# SKUs that must have zero open supply orders (all supply rows are "delivered").
# analyze_shipment_delay_causes requires that inventory_shortage orders reference
# SKUs with NO open inbound supply — the presence of any open supply order
# would instead trigger upstream_supply_delay classification.
#
# These are P84 risk-band SKUs; forcing their supply to delivered does NOT affect
# list_stockout_risk because that tool only counts supply arriving within the
# 7-day horizon (today+7).  P84 pushes all non-delivered risk-SKU supply to
# today+10, which is already outside the horizon and counted as incoming_supply=0
# by that tool — so the risk-band invariant (2 critical + 2 high + 3 medium)
# is preserved regardless of whether those orders exist.
NO_OPEN_SUPPLY_SKUS: frozenset[str] = frozenset({"SKU-002", "SKU-004"})

# Orders whose SKU is in NO_OPEN_SUPPLY_SKUS so on_hand < quantity AND
# no open supply at all → inventory_shortage.
# SKU-002 and SKU-004 are both P84 risk-band SKUs (critical and high respectively)
# with on_hand set by DOC override in generate_inventory so on_hand << 200.
INVENTORY_SHORTAGE_ORDERS: list[dict[str, str]] = [
    {"order_id": "CO-0001", "customer_id": "CUST-001", "sku_id": "SKU-002",
     "ship_from_location_id": "WH-001", "region": "Kanto"},
    {"order_id": "CO-0002", "customer_id": "CUST-003", "sku_id": "SKU-004",
     "ship_from_location_id": "WH-001", "region": "Kansai"},
]

# Orders whose SKU has a pending inbound supply order arriving at today+10
# (set by P84 generate_supply) — the order is overdue (requested_ship_date=today-2)
# and on_hand < quantity, so the root cause is upstream supply delay.
# SKU-001 and SKU-003 are both P84 risk-band SKUs that always have open pending
# supply at today+10 (guaranteed by the risk-band supply override in generate_supply).
UPSTREAM_SUPPLY_DELAY_ORDERS: list[dict[str, str]] = [
    {"order_id": "CO-0003", "customer_id": "CUST-002", "sku_id": "SKU-001",
     "ship_from_location_id": "WH-001", "region": "Tohoku"},
    {"order_id": "CO-0004", "customer_id": "CUST-004", "sku_id": "SKU-003",
     "ship_from_location_id": "WH-001", "region": "Kyushu"},
]

# Orders that were shipped late: actual_ship_date > planned_ship_date
# (warehouse processing delay).
WAREHOUSE_DELAY_ORDERS: list[dict[str, str]] = [
    {"order_id": "CO-0005", "customer_id": "CUST-005", "sku_id": "SKU-010",
     "ship_from_location_id": "WH-001", "region": "Kanto"},
    {"order_id": "CO-0006", "customer_id": "CUST-006", "sku_id": "SKU-012",
     "ship_from_location_id": "WH-002", "region": "Kansai"},
]

# Orders shipped on time but delivered late: actual_delivery_date > planned_delivery_date
# (carrier delay).
CARRIER_DELAY_ORDERS: list[dict[str, str]] = [
    {"order_id": "CO-0007", "customer_id": "CUST-007", "sku_id": "SKU-015",
     "ship_from_location_id": "WH-001", "region": "Kanto"},
    {"order_id": "CO-0008", "customer_id": "CUST-008", "sku_id": "SKU-016",
     "ship_from_location_id": "WH-002", "region": "Chubu"},
]

# Demand-shift signal for P88 SPEC Q9 (customer/region demand).
# DEMAND_GROWTH_CUSTOMERS: order quantity in last 28 days clearly > prior 28 days.
# DEMAND_DECLINE_CUSTOMERS: order quantity in last 28 days clearly < prior 28 days.
#
# Prior period: today-56 to today-29; current period: today-28 to today-1.
# Growth customer CUST-009 orders 3 orders in current vs 1 in prior for region Kanto.
# Decline customer CUST-010 orders 1 order in current vs 3 in prior for region Kansai.
DEMAND_SHIFT_GROWTH_CUSTOMER = "CUST-009"
DEMAND_SHIFT_GROWTH_REGION = "Kanto"
DEMAND_SHIFT_DECLINE_CUSTOMER = "CUST-010"
DEMAND_SHIFT_DECLINE_REGION = "Kansai"

# ---------------------------------------------------------------------------
# Deterministic production plan scenario constants (P89 T-555)
#
# Weekly granularity: 8 weeks starting from the Monday of the current week.
# Locations: WH-001 and WH-002 (warehouse-type, used in P87/P88 scenarios).
# Fixed-index assignment — independently verifiable without running the generator.
#
# PRODUCTION_OVERPRODUCTION_SKU: a low-demand slow-moving SKU whose planned_qty
#   is far above its forward demand/forecast, creating a large overproduction gap.
#   SKU-026 has base_demand_mean=1.5 units/day → ~10 units/week.
#   planned_qty = 200 units/week → overproduction gap ≈ 190 units/week (≈ 19×).
#
# PRODUCTION_UNDERPRODUCTION_SKU: a P84 critical-risk SKU whose planned_qty is
#   far below weekly demand, connecting underproduction to the stockout narrative.
#   SKU-001 has base_demand_mean=10 units/day → ~70 units/week.
#   planned_qty = 10 units/week → underproduction gap ≈ -60 units/week.
#
# PRODUCTION_SATURATED_LOCATION: WH-001 in week 0 (this week's Monday).
#   capacity_units = 2000 for WH-001; normal weeks plan 15 standard SKUs at 100
#   units each (Σ = 1500, utilization = 0.75).
#   Saturated week 0: the 15 standard SKUs are planned at 150 units each
#   (Σ = 2250, utilization = 1.125 ≥ 1.0) → binding constraint for Q10.
#
# PRODUCTION_WEEKS: number of forward weeks generated (8 weeks).
# PRODUCTION_NORMAL_SKUS: fixed list of 15 standard SKUs used for normal rows.
#   Drawn from SKU-011..SKU-025 (all standard sku_type, non-risk-band).
# PRODUCTION_CAPACITY_WH001: weekly production capacity for WH-001.
# PRODUCTION_CAPACITY_WH002: weekly production capacity for WH-002.
# PRODUCTION_NORMAL_QTY: planned_qty for normal rows in non-saturated weeks.
# PRODUCTION_SATURATED_QTY: planned_qty for normal SKUs in the saturated week.
# ---------------------------------------------------------------------------

PRODUCTION_OVERPRODUCTION_SKU = "SKU-026"   # slow-moving, ~10 units/week demand
PRODUCTION_OVERPRODUCTION_PLANNED_QTY = 200  # >> demand; gap ≈ +190 units/week

PRODUCTION_UNDERPRODUCTION_SKU = "SKU-001"   # P84 critical-risk; ~70 units/week demand
PRODUCTION_UNDERPRODUCTION_PLANNED_QTY = 10  # << demand; gap ≈ -60 units/week

PRODUCTION_SATURATED_LOCATION = "WH-001"     # location where Σ planned ≥ capacity
PRODUCTION_SATURATED_WEEK_INDEX = 0          # week offset from this Monday (0 = current week)

PRODUCTION_WEEKS = 8                         # number of forward weeks

# 15 standard non-risk-band SKUs for normal production rows (SKU-011..SKU-025).
PRODUCTION_NORMAL_SKUS: list[str] = [f"SKU-{i:03d}" for i in range(11, 26)]

PRODUCTION_CAPACITY_WH001 = 2000             # units/week; WH-001
PRODUCTION_CAPACITY_WH002 = 1500             # units/week; WH-002

PRODUCTION_NORMAL_QTY = 100          # planned_qty for normal SKUs in non-saturated weeks
PRODUCTION_SATURATED_QTY = 150       # planned_qty for normal SKUs in saturated week 0
# Σ WH-001 week 0 = 15 × 150 = 2250 ≥ 2000 (utilization = 1.125)
# Σ WH-001 other  = 15 × 100 = 1500 < 2000 (utilization = 0.75)

DETERMINISTIC_NULL_SKUS = {"SKU-003", "SKU-005", "SKU-007"}
CONTIGUOUS_GAP_SKU = "SKU-001"
CONTIGUOUS_GAP_START_DAY = 60
CONTIGUOUS_GAP_LENGTH = 7

# Deterministic risk-band overrides for the demo query
# "Which products are at stockout risk this week?" (horizon_days=7, min_risk_level="medium").
#
# Days-of-cover (DOC) values chosen so that projected_ending_stock = on_hand - demand_7day
# lands squarely inside each band for all base_demand_mean values in sku_parameters.csv:
#   critical: DOC=2  → projected = daily*(2-7) = -daily*5 < 0               → critical
#   high:     DOC=7.4 → projected = daily*0.4,  ratio=0.4/7≈0.057 ∈ [0, 0.1) → high
#   medium:   DOC=9.0 → projected = daily*2.0,  ratio=2/7≈0.286  ∈ [0.1,0.5) → medium
# Supply orders for risk SKUs are pushed to today+10 (outside 7-day horizon) so incoming
# supply does not rescue the classification.
SKU_RISK_BANDS: dict[str, str] = {
    "SKU-001": "critical",
    "SKU-002": "critical",
    "SKU-003": "high",
    "SKU-004": "high",
    "SKU-005": "medium",
    "SKU-006": "medium",
    "SKU-007": "medium",
}

_RISK_DOC: dict[str, float] = {
    "critical": 2.0,
    "high": 7.4,
    "medium": 9.0,
}


@dataclass(frozen=True)
class SampleDataConfig:
    seed: int = 42
    sku_count: int = 30
    horizon_days: int = 365
    warehouse_count: int = 2
    missing_rate: float = 0.02

    @property
    def warehouses(self) -> list[str]:
        return [f"WH-{idx:03d}" for idx in range(1, self.warehouse_count + 1)]


def _load_csv(path: Path) -> list[CsvRow]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _neg_binom_demand(rng: random.Random, mu: float, dispersion: float) -> int:
    if mu <= 0:
        return 0
    variance = mu + (dispersion * mu) ** 2
    if variance <= mu:
        return max(0, int(rng.gauss(mu, mu**0.5)))
    sigma = variance**0.5
    return max(0, int(rng.gauss(mu, sigma)))


def _lognormal_lead_time(rng: random.Random, mean: float, std: float) -> int:
    if mean <= 0:
        return 1
    cv = std / mean if mean > 0 else 0.1
    sigma_log = math.log(1 + cv**2) ** 0.5
    mu_log = math.log(mean) - 0.5 * sigma_log**2
    sample = rng.gauss(mu_log, sigma_log)
    return max(1, int(math.exp(sample) + 0.5))


def _seasonal_factor(day: int, amplitude: float, period: float) -> float:
    if amplitude == 0.0:
        return 1.0
    return 1.0 + amplitude * math.sin(2 * math.pi * day / period)


def generate_sku_master(skus: list[CsvRow], out_dir: Path) -> None:
    fields = [
        "sku_id", "name", "category", "sku_type", "moq",
        "lead_time_days_mean", "lead_time_days_std", "holding_cost_pct", "unit_cost",
    ]
    with open(out_dir / "sku_master.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in skus:
            writer.writerow({k: row[k] for k in fields})


def generate_customers(customers: list[CsvRow], out_dir: Path) -> None:
    fields = ["customer_id", "segment", "sku_affinity_json"]
    with open(out_dir / "customer_master.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in customers:
            writer.writerow({k: row[k] for k in fields})


def compute_recent_avg(demand_rows: list[CsvRow], sku_id: str, window_days: int = 30) -> float:
    """Return the mean daily quantity over the last *window_days* non-missing rows for *sku_id*.

    Mirrors the SQL expression used by ``list_stockout_risk``:
        AVG(quantity) WHERE date >= CURRENT_DATE - 30 days AND is_missing IS NOT TRUE

    Returns 0.0 when no qualifying rows are found (matches the COALESCE(avg_daily, 0) in SQL).
    """
    cutoff = date.today() - timedelta(days=window_days)
    quantities = [
        int(r["quantity"])
        for r in demand_rows
        if r["sku_id"] == sku_id
        and r["is_missing"] not in ("True", "true", True)
        and r["quantity"] not in ("", None)
        and date.fromisoformat(r["date"]) >= cutoff
    ]
    return sum(quantities) / len(quantities) if quantities else 0.0


def generate_demand_history(
    skus: list[CsvRow], rng: random.Random, out_dir: Path, config: SampleDataConfig
) -> dict[str, float]:
    """Write demand_history.csv and return a {sku_id: recent_avg_daily} mapping.

    The returned mapping contains the actual 30-day rolling average for each SKU,
    computed the same way as ``list_stockout_risk``'s SQL query.  ``generate_inventory``
    uses these values to set ``on_hand`` for risk-band SKUs so the tool's risk
    classification is exact regardless of seasonal noise in the generated demand.
    """
    gap_end = CONTIGUOUS_GAP_START_DAY + CONTIGUOUS_GAP_LENGTH
    gap_days = set(range(CONTIGUOUS_GAP_START_DAY, gap_end))

    # Accumulate all rows in memory so we can compute per-SKU recent averages after writing.
    all_rows: list[CsvRow] = []

    fields = ["sku_id", "date", "quantity", "is_missing"]
    with open(out_dir / "demand_history.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for sku in skus:
            sku_id = sku["sku_id"]
            base_mean = float(sku["base_demand_mean"])
            dispersion = float(sku["demand_dispersion"])
            amplitude = float(sku["seasonal_amplitude"])
            period = float(sku["seasonal_period_days"])

            for day_idx in range(config.horizon_days):
                current_date = START_DATE + timedelta(days=day_idx)
                mu = base_mean * _seasonal_factor(day_idx, amplitude, period)
                qty = _neg_binom_demand(rng, mu, dispersion)

                is_missing = False

                if sku_id == CONTIGUOUS_GAP_SKU and day_idx in gap_days:
                    is_missing = True
                elif sku_id in DETERMINISTIC_NULL_SKUS and rng.random() < config.missing_rate:
                    is_missing = True
                elif sku_id not in DETERMINISTIC_NULL_SKUS and sku_id != CONTIGUOUS_GAP_SKU:
                    if rng.random() < config.missing_rate:
                        is_missing = True

                row: CsvRow = {
                    "sku_id": sku_id,
                    "date": current_date.isoformat(),
                    "quantity": "" if is_missing else str(qty),
                    "is_missing": str(is_missing),
                }
                writer.writerow(row)
                all_rows.append(row)

    # Build per-SKU recent average from the just-generated rows.
    sku_ids = [sku["sku_id"] for sku in skus]
    return {sid: compute_recent_avg(all_rows, sid) for sid in sku_ids}


def generate_inventory(
    skus: list[CsvRow],
    rng: random.Random,
    out_dir: Path,
    config: SampleDataConfig,
    recent_avg_by_sku: dict[str, float] | None = None,
) -> None:
    """Write inventory_snapshot.csv.

    For risk-band SKUs the ``on_hand`` is back-calculated from the actual recent
    demand average (``recent_avg_by_sku``) so the tool's projected ending stock
    ratio falls exactly within the intended risk band regardless of seasonal
    noise in the generated demand history.  When ``recent_avg_by_sku`` is ``None``
    or a SKU is absent from it, ``base_demand_mean`` is used as the fallback
    (preserving the old behaviour for callers that do not pass demand data).
    """
    # Snapshot is ~3 weeks before today to simulate a recent but not same-day snapshot.
    snapshot_date = (date.today() - timedelta(days=22)).isoformat()
    fields = ["sku_id", "warehouse_id", "on_hand", "on_order", "snapshot_date"]

    with open(out_dir / "inventory_snapshot.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for sku in skus:
            sku_id = sku["sku_id"]
            daily_demand = float(sku["base_demand_mean"])
            lt_mean = float(sku["lead_time_days_mean"])
            unit_cost = float(sku["unit_cost"])

            normal_on_hand = int(daily_demand * (lt_mean + 14))

            if sku_id in SKU_RISK_BANDS:
                # Deterministic risk-band override: back-calculate on_hand from the
                # *actual* recent daily average so the tool's formula
                #   demand_forecast = avg_daily * horizon_days
                #   projected = on_hand - demand_forecast  (incoming=0 for risk SKUs)
                # lands exactly within the intended band for every DOC value.
                doc = _RISK_DOC[SKU_RISK_BANDS[sku_id]]
                actual_avg = (
                    (recent_avg_by_sku or {}).get(sku_id) or daily_demand
                )
                # round() instead of int() avoids truncation pushing the high band
                # (DOC=7.4, margin ratio≈0.057) down into critical.
                total_on_hand = round(actual_avg * doc)
                wh_on_hand = [total_on_hand // config.warehouse_count] * config.warehouse_count
                # Assign any rounding remainder to the first warehouse.
                wh_on_hand[0] += total_on_hand - sum(wh_on_hand)
                for idx, wh in enumerate(config.warehouses):
                    writer.writerow({
                        "sku_id": sku_id,
                        "warehouse_id": wh,
                        "on_hand": wh_on_hand[idx],
                        "on_order": 0,
                        "snapshot_date": snapshot_date,
                    })
            else:
                for wh in config.warehouses:
                    roll = rng.random()
                    if roll < 0.15 and unit_cost > 100:
                        on_hand = int(daily_demand * 150)
                        on_order = 0
                    elif roll < 0.10:
                        on_hand = 0
                        on_order = max(1, int(daily_demand * lt_mean))
                    else:
                        on_hand = max(0, int(rng.gauss(normal_on_hand, normal_on_hand * 0.15)))
                        on_order = max(0, int(rng.gauss(daily_demand * 7, daily_demand * 2)))

                    writer.writerow({
                        "sku_id": sku_id,
                        "warehouse_id": wh,
                        "on_hand": on_hand,
                        "on_order": on_order,
                        "snapshot_date": snapshot_date,
                    })


def generate_supply(
    skus: list[CsvRow], suppliers: list[CsvRow], rng: random.Random, out_dir: Path
) -> None:
    fields = ["sku_id", "supplier_id", "order_date", "expected_arrival", "quantity", "status"]
    # Orders placed roughly 10 weeks ago; arrivals spread over the following 60-90 days
    # so they span delivered / in_transit / pending relative to today.
    base_order_date = date.today() - timedelta(days=70)
    # Status cutoffs relative to today: delivered if arrived >22 days ago,
    # in_transit if arrived within last 9 days, pending otherwise.
    _delivered_cutoff = date.today() - timedelta(days=22)
    _in_transit_cutoff = date.today() - timedelta(days=9)
    supplier_by_type = {s["sku_type"]: s for s in suppliers}

    with open(out_dir / "supply_orders.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for sku in skus:
            sku_id = sku["sku_id"]
            sku_type = sku["sku_type"]
            supplier = supplier_by_type[sku_type]
            supplier_id = supplier["supplier_id"]
            on_time_rate = float(supplier["on_time_delivery_rate"])
            avg_delay = float(supplier["avg_delay_days"])
            delay_std = float(supplier["delay_std_days"])
            moq = int(sku["moq"])
            lt_mean = float(sku["lead_time_days_mean"])
            lt_std = float(sku["lead_time_days_std"])

            num_orders = rng.randint(3, 5)
            for i in range(num_orders):
                order_offset = rng.randint(0, 45)
                order_date = base_order_date + timedelta(days=order_offset)
                lead_days = _lognormal_lead_time(rng, lt_mean, lt_std)
                if rng.random() > on_time_rate:
                    lead_days += max(0, int(rng.gauss(avg_delay, delay_std)))
                arrival_date = order_date + timedelta(days=lead_days)
                quantity = moq * rng.randint(1, 4)

                if arrival_date < _delivered_cutoff:
                    status = "delivered"
                elif arrival_date < _in_transit_cutoff:
                    status = "in_transit"
                else:
                    status = "pending"

                # NO_OPEN_SUPPLY_SKUS: force all supply to delivered (past arrival) so
                # analyze_shipment_delay_causes classifies CO-0001/CO-0002 as
                # inventory_shortage (no open inbound supply at all).
                # Use _delivered_cutoff - 1 to guarantee status=delivered regardless of
                # the random arrival date.
                if sku_id in NO_OPEN_SUPPLY_SKUS:
                    arrival_date = _delivered_cutoff - timedelta(days=1)
                    status = "delivered"
                # For risk-band SKUs (not in NO_OPEN_SUPPLY_SKUS), push any non-delivered
                # order to today+10 so the tool's incoming_supply window (horizon_days=7)
                # never includes it, preserving the intended risk classification.
                elif sku_id in SKU_RISK_BANDS and status != "delivered":
                    arrival_date = date.today() + timedelta(days=10)
                    status = "pending"

                writer.writerow({
                    "sku_id": sku_id,
                    "supplier_id": supplier_id,
                    "order_date": order_date.isoformat(),
                    "expected_arrival": arrival_date.isoformat(),
                    "quantity": quantity,
                    "status": status,
                })


def generate_cost(
    skus: list[CsvRow], rng: random.Random, out_dir: Path, config: SampleDataConfig
) -> None:
    # Cost period spans the same 365-day window as demand_history.
    period_start = (date.today() - timedelta(days=365)).isoformat()
    period_end = (date.today() - timedelta(days=1)).isoformat()
    fields = [
        "sku_id", "period_start", "period_end",
        "cogs", "holding_cost", "ordering_cost", "stockout_cost",
    ]

    with open(out_dir / "cost_master.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for sku in skus:
            sku_id = sku["sku_id"]
            unit_cost = float(sku["unit_cost"])
            holding_pct = float(sku["holding_cost_pct"])
            daily_demand = float(sku["base_demand_mean"])
            annual_demand = daily_demand * config.horizon_days

            cogs = round(annual_demand * unit_cost * rng.uniform(0.9, 1.1), 2)
            avg_inventory = daily_demand * float(sku["lead_time_days_mean"])
            holding_cost = round(
                avg_inventory * unit_cost * holding_pct * rng.uniform(0.85, 1.15), 2
            )
            ordering_cost = round(rng.uniform(50, 500) * rng.randint(12, 52), 2)
            stockout_cost = round(annual_demand * unit_cost * rng.uniform(0.01, 0.05), 2)

            writer.writerow({
                "sku_id": sku_id,
                "period_start": period_start,
                "period_end": period_end,
                "cogs": cogs,
                "holding_cost": holding_cost,
                "ordering_cost": ordering_cost,
                "stockout_cost": stockout_cost,
            })


def generate_location_master(locations: list[CsvRow], out_dir: Path) -> None:
    fields = [
        "location_id", "name", "region", "country", "location_type",
        "capacity_units", "handling_cost_per_unit", "lead_time_to_customer_days",
    ]
    with open(out_dir / "location_master.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in locations:
            writer.writerow({k: row[k] for k in fields})


def generate_forecast_history(
    skus: list[CsvRow], rng: random.Random, out_dir: Path, config: SampleDataConfig
) -> None:
    fields = ["sku_id", "forecast_date", "target_date", "forecast_qty", "model_version"]
    forecast_lead_days = 30
    num_months = max(1, config.horizon_days // 30)

    with open(out_dir / "forecast_history.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for sku in skus:
            sku_id = sku["sku_id"]
            base_mean = float(sku["base_demand_mean"])
            dispersion = float(sku["demand_dispersion"])
            amplitude = float(sku["seasonal_amplitude"])
            period = float(sku["seasonal_period_days"])
            model_version = "v2.0-seasonal" if amplitude > 0 else "v1.0-naive"

            for month_idx in range(num_months):
                day_idx = month_idx * 30
                target_date = START_DATE + timedelta(days=day_idx)
                forecast_date = target_date - timedelta(days=forecast_lead_days)
                monthly_mean = base_mean * 30 * _seasonal_factor(day_idx, amplitude, period)
                error_pct = rng.gauss(0, dispersion * 0.5)
                forecast_qty = max(0.0, monthly_mean * (1 + error_pct))
                writer.writerow({
                    "sku_id": sku_id,
                    "forecast_date": forecast_date.isoformat(),
                    "target_date": target_date.isoformat(),
                    "forecast_qty": round(forecast_qty, 2),
                    "model_version": model_version,
                })


def generate_customer_orders_and_shipments(
    skus: list[CsvRow],
    rng: random.Random,
    out_dir: Path,
    config: SampleDataConfig,
) -> None:
    """Write customer_orders.csv and shipments.csv with deterministic delay scenarios.

    Scenario index (fixed, independently verifiable — P84 convention):
      CO-0001, CO-0002 : inventory_shortage    (P84 critical SKUs at WH-001, status=open)
      CO-0003, CO-0004 : upstream_supply_delay (P84 critical SKUs, supply arrives today+10)
      CO-0005, CO-0006 : warehouse_delay       (shipped late: actual_ship > planned_ship)
      CO-0007, CO-0008 : carrier_delay         (shipped on time, delivered late)
      CO-0009 .. majority : fulfilled_on_time  (shipped + delivered, dates consistent)
      CO-demand-* : demand_shift signal for P88 (CUST-009 growth, CUST-010 decline)
    """
    today = date.today()
    order_fields = [
        "order_id", "customer_id", "sku_id", "ship_from_location_id",
        "region", "quantity", "order_date", "requested_ship_date", "status",
    ]
    shipment_fields = [
        "shipment_id", "order_id", "carrier", "planned_ship_date",
        "actual_ship_date", "planned_delivery_date", "actual_delivery_date", "status",
    ]
    orders: list[CsvRow] = []
    shipments: list[CsvRow] = []

    # ---- Scenario 1: inventory shortage (open, no shipment) ----
    for spec in INVENTORY_SHORTAGE_ORDERS:
        order_date = today - timedelta(days=5)
        requested_ship_date = today - timedelta(days=2)
        orders.append({
            "order_id": spec["order_id"],
            "customer_id": spec["customer_id"],
            "sku_id": spec["sku_id"],
            "ship_from_location_id": spec["ship_from_location_id"],
            "region": spec["region"],
            "quantity": "200",  # >> on_hand for critical SKUs (DOC=2 → tiny stock)
            "order_date": order_date.isoformat(),
            "requested_ship_date": requested_ship_date.isoformat(),
            "status": "open",
        })
        # No shipment row — unshipped

    # ---- Scenario 2: upstream supply delay (open, no shipment) ----
    # requested_ship_date=today-2 makes these orders overdue so _fetch_unshipped_delayed
    # picks them up.  The SKUs (SKU-001, SKU-003) have pending supply arriving at
    # today+10 (today+10 > today-2) → upstream_supply_delay classification.
    for spec in UPSTREAM_SUPPLY_DELAY_ORDERS:
        order_date = today - timedelta(days=5)
        requested_ship_date = today - timedelta(days=2)
        orders.append({
            "order_id": spec["order_id"],
            "customer_id": spec["customer_id"],
            "sku_id": spec["sku_id"],
            "ship_from_location_id": spec["ship_from_location_id"],
            "region": spec["region"],
            "quantity": "150",
            "order_date": order_date.isoformat(),
            "requested_ship_date": requested_ship_date.isoformat(),
            "status": "open",
        })
        # No shipment row — unshipped overdue, inbound supply arrives too late

    # ---- Scenario 3: warehouse processing delay (shipped late) ----
    for idx, spec in enumerate(WAREHOUSE_DELAY_ORDERS):
        order_date = today - timedelta(days=14)
        planned_ship = today - timedelta(days=7)
        actual_ship = today - timedelta(days=4)   # 3 days late vs planned
        planned_delivery = planned_ship + timedelta(days=3)
        actual_delivery = actual_ship + timedelta(days=3)
        order_id = spec["order_id"]
        orders.append({
            "order_id": order_id,
            "customer_id": spec["customer_id"],
            "sku_id": spec["sku_id"],
            "ship_from_location_id": spec["ship_from_location_id"],
            "region": spec["region"],
            "quantity": str(50 + idx * 20),
            "order_date": order_date.isoformat(),
            "requested_ship_date": planned_ship.isoformat(),
            "status": "shipped",
        })
        shipment_id = f"SH-{order_id}"
        shipments.append({
            "shipment_id": shipment_id,
            "order_id": order_id,
            "carrier": "CARRIER-A",
            "planned_ship_date": planned_ship.isoformat(),
            "actual_ship_date": actual_ship.isoformat(),
            "planned_delivery_date": planned_delivery.isoformat(),
            "actual_delivery_date": actual_delivery.isoformat(),
            "status": "delivered",
        })

    # ---- Scenario 4: carrier delay (shipped on time, delivered late) ----
    for idx, spec in enumerate(CARRIER_DELAY_ORDERS):
        order_date = today - timedelta(days=12)
        planned_ship = today - timedelta(days=6)
        actual_ship = today - timedelta(days=6)   # on time
        planned_delivery = planned_ship + timedelta(days=3)
        actual_delivery = planned_ship + timedelta(days=7)   # 4 days late
        order_id = spec["order_id"]
        orders.append({
            "order_id": order_id,
            "customer_id": spec["customer_id"],
            "sku_id": spec["sku_id"],
            "ship_from_location_id": spec["ship_from_location_id"],
            "region": spec["region"],
            "quantity": str(30 + idx * 10),
            "order_date": order_date.isoformat(),
            "requested_ship_date": planned_ship.isoformat(),
            "status": "shipped",
        })
        shipment_id = f"SH-{order_id}"
        shipments.append({
            "shipment_id": shipment_id,
            "order_id": order_id,
            "carrier": "CARRIER-B",
            "planned_ship_date": planned_ship.isoformat(),
            "actual_ship_date": actual_ship.isoformat(),
            "planned_delivery_date": planned_delivery.isoformat(),
            "actual_delivery_date": actual_delivery.isoformat(),
            "status": "delivered",
        })

    # ---- Scenario 5: majority on-time fulfilled orders ----
    # Use non-risk SKUs (SKU-008 to SKU-030) so they don't interfere with P84.
    # Fixed assignment: order index → customer, sku, location, region (deterministic).
    on_time_sku_pool = [
        sku["sku_id"] for sku in skus
        if sku["sku_id"] not in SKU_RISK_BANDS
    ][:10]  # cap at 10 to stay deterministic even when sku_count varies
    on_time_customers = [
        "CUST-001", "CUST-002", "CUST-003", "CUST-004", "CUST-005",
        "CUST-006", "CUST-007", "CUST-008", "CUST-001", "CUST-002",
    ]
    on_time_locations = ["WH-001", "WH-002", "WH-001", "WH-002", "WH-001",
                         "WH-002", "WH-001", "WH-002", "WH-001", "WH-002"]
    on_time_regions = ["Kanto", "Kansai", "Tohoku", "Kyushu", "Chubu",
                       "Kanto", "Kansai", "Tohoku", "Kanto", "Kansai"]
    num_on_time = min(len(on_time_sku_pool), 10)
    for idx in range(num_on_time):
        order_id = f"CO-{9 + idx:04d}"
        sku_id = on_time_sku_pool[idx % len(on_time_sku_pool)]
        customer_id = on_time_customers[idx]
        location_id = on_time_locations[idx]
        region = on_time_regions[idx]
        order_date = today - timedelta(days=20 + idx)
        planned_ship = today - timedelta(days=10 + idx)
        actual_ship = planned_ship
        planned_delivery = planned_ship + timedelta(days=3)
        actual_delivery = planned_delivery
        qty = 20 + idx * 5
        orders.append({
            "order_id": order_id,
            "customer_id": customer_id,
            "sku_id": sku_id,
            "ship_from_location_id": location_id,
            "region": region,
            "quantity": str(qty),
            "order_date": order_date.isoformat(),
            "requested_ship_date": planned_ship.isoformat(),
            "status": "shipped",
        })
        shipment_id = f"SH-{order_id}"
        shipments.append({
            "shipment_id": shipment_id,
            "order_id": order_id,
            "carrier": "CARRIER-A",
            "planned_ship_date": planned_ship.isoformat(),
            "actual_ship_date": actual_ship.isoformat(),
            "planned_delivery_date": planned_delivery.isoformat(),
            "actual_delivery_date": actual_delivery.isoformat(),
            "status": "delivered",
        })

    # ---- Demand-shift signal for P88 (SPEC Q9) ----
    # CUST-009 (region Kanto): 1 order in prior period (today-56 to today-29),
    #   3 orders in current period (today-28 to today-1) → clearly growing.
    # CUST-010 (region Kansai): 3 orders in prior period, 1 in current → declining.
    #
    # Use non-risk SKUs so P84 determinism is untouched.
    demand_shift_sku = on_time_sku_pool[0] if on_time_sku_pool else "SKU-008"
    demand_shift_loc = "WH-001"

    # CUST-009 growth: 1 prior order, 3 current orders
    orders.append({
        "order_id": "CO-DS01",
        "customer_id": DEMAND_SHIFT_GROWTH_CUSTOMER,
        "sku_id": demand_shift_sku,
        "ship_from_location_id": demand_shift_loc,
        "region": DEMAND_SHIFT_GROWTH_REGION,
        "quantity": "50",
        "order_date": (today - timedelta(days=45)).isoformat(),
        "requested_ship_date": (today - timedelta(days=40)).isoformat(),
        "status": "shipped",
    })
    for ds_idx in range(3):
        ds_order_id = f"CO-DS0{2 + ds_idx}"
        orders.append({
            "order_id": ds_order_id,
            "customer_id": DEMAND_SHIFT_GROWTH_CUSTOMER,
            "sku_id": demand_shift_sku,
            "ship_from_location_id": demand_shift_loc,
            "region": DEMAND_SHIFT_GROWTH_REGION,
            "quantity": "50",
            "order_date": (today - timedelta(days=20 - ds_idx * 5)).isoformat(),
            "requested_ship_date": (today - timedelta(days=15 - ds_idx * 5)).isoformat(),
            "status": "shipped",
        })

    # CUST-010 decline: 3 prior orders, 1 current order
    for ds_idx in range(3):
        ds_order_id = f"CO-DS0{5 + ds_idx}"
        orders.append({
            "order_id": ds_order_id,
            "customer_id": DEMAND_SHIFT_DECLINE_CUSTOMER,
            "sku_id": demand_shift_sku,
            "ship_from_location_id": "WH-002",
            "region": DEMAND_SHIFT_DECLINE_REGION,
            "quantity": "50",
            "order_date": (today - timedelta(days=50 - ds_idx * 5)).isoformat(),
            "requested_ship_date": (today - timedelta(days=45 - ds_idx * 5)).isoformat(),
            "status": "shipped",
        })
    orders.append({
        "order_id": "CO-DS08",
        "customer_id": DEMAND_SHIFT_DECLINE_CUSTOMER,
        "sku_id": demand_shift_sku,
        "ship_from_location_id": "WH-002",
        "region": DEMAND_SHIFT_DECLINE_REGION,
        "quantity": "50",
        "order_date": (today - timedelta(days=10)).isoformat(),
        "requested_ship_date": (today - timedelta(days=5)).isoformat(),
        "status": "shipped",
    })

    with open(out_dir / "customer_orders.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=order_fields)
        writer.writeheader()
        writer.writerows(orders)

    with open(out_dir / "shipments.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=shipment_fields)
        writer.writeheader()
        writer.writerows(shipments)

    # Summary for verification
    scenario_counts = {
        "inventory_shortage": len(INVENTORY_SHORTAGE_ORDERS),
        "upstream_supply_delay": len(UPSTREAM_SUPPLY_DELAY_ORDERS),
        "warehouse_delay": len(WAREHOUSE_DELAY_ORDERS),
        "carrier_delay": len(CARRIER_DELAY_ORDERS),
        "on_time": num_on_time,
        "demand_shift_growth": 4,   # 1 prior + 3 current for CUST-009
        "demand_shift_decline": 4,  # 3 prior + 1 current for CUST-010
    }
    total_orders = len(orders)
    total_shipments = len(shipments)
    print(
        f"customer_orders: {total_orders} rows — "
        + ", ".join(f"{k}={v}" for k, v in scenario_counts.items())
    )
    print(f"shipments: {total_shipments} rows")


def _this_week_monday() -> date:
    """Return the Monday of the current ISO week (date-relative, P82 convention)."""
    today = date.today()
    return today - timedelta(days=today.weekday())


def generate_production_data(out_dir: Path) -> None:
    """Write production_capacity.csv and production_plan.csv.

    Deterministic scenario assignment (P89 T-555, P84-style fixed-index constants):

    production_capacity rows:
      WH-001 and WH-002 × 8 weeks starting from this Monday.
      Capacities: WH-001 = PRODUCTION_CAPACITY_WH001, WH-002 = PRODUCTION_CAPACITY_WH002.

    production_plan scenarios:
      - PRODUCTION_OVERPRODUCTION_SKU (SKU-026) at WH-001 and WH-002:
          planned_qty = PRODUCTION_OVERPRODUCTION_PLANNED_QTY (200) for all 8 weeks.
          Weekly demand ≈ 10 units → gap ≈ +190 units/week (overproduction).
      - PRODUCTION_UNDERPRODUCTION_SKU (SKU-001) at WH-001:
          planned_qty = PRODUCTION_UNDERPRODUCTION_PLANNED_QTY (10) for all 8 weeks.
          Weekly demand ≈ 70 units → gap ≈ -60 units/week (underproduction).
          Connects to P84 critical-risk / stockout narrative.
      - PRODUCTION_NORMAL_SKUS (SKU-011..SKU-025) at WH-001 and WH-002:
          Week 0 (PRODUCTION_SATURATED_WEEK_INDEX) at WH-001:
              planned_qty = PRODUCTION_SATURATED_QTY (150) → Σ = 15×150 = 2250 ≥ 2000.
          All other location-weeks: planned_qty = PRODUCTION_NORMAL_QTY (100).
    """
    monday = _this_week_monday()
    locations = ["WH-001", "WH-002"]
    capacity_by_location = {
        "WH-001": PRODUCTION_CAPACITY_WH001,
        "WH-002": PRODUCTION_CAPACITY_WH002,
    }

    capacity_fields = ["location_id", "week_start", "capacity_units"]
    with open(out_dir / "production_capacity.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=capacity_fields)
        writer.writeheader()
        for loc in locations:
            for week_idx in range(PRODUCTION_WEEKS):
                week_start = monday + timedelta(weeks=week_idx)
                writer.writerow({
                    "location_id": loc,
                    "week_start": week_start.isoformat(),
                    "capacity_units": capacity_by_location[loc],
                })

    plan_fields = ["sku_id", "location_id", "week_start", "planned_qty"]
    with open(out_dir / "production_plan.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=plan_fields)
        writer.writeheader()

        for week_idx in range(PRODUCTION_WEEKS):
            week_start = monday + timedelta(weeks=week_idx)

            # Overproduction SKU: planned >> demand at both locations
            for loc in locations:
                writer.writerow({
                    "sku_id": PRODUCTION_OVERPRODUCTION_SKU,
                    "location_id": loc,
                    "week_start": week_start.isoformat(),
                    "planned_qty": PRODUCTION_OVERPRODUCTION_PLANNED_QTY,
                })

            # Underproduction SKU: planned << demand at WH-001 only
            writer.writerow({
                "sku_id": PRODUCTION_UNDERPRODUCTION_SKU,
                "location_id": "WH-001",
                "week_start": week_start.isoformat(),
                "planned_qty": PRODUCTION_UNDERPRODUCTION_PLANNED_QTY,
            })

            # Normal SKUs: majority rows, both locations
            # WH-001 week 0 uses PRODUCTION_SATURATED_QTY → Σ = 15×150 = 2250 ≥ 2000
            for loc in locations:
                is_saturated_week = (
                    loc == PRODUCTION_SATURATED_LOCATION
                    and week_idx == PRODUCTION_SATURATED_WEEK_INDEX
                )
                qty = PRODUCTION_SATURATED_QTY if is_saturated_week else PRODUCTION_NORMAL_QTY
                for sku_id in PRODUCTION_NORMAL_SKUS:
                    writer.writerow({
                        "sku_id": sku_id,
                        "location_id": loc,
                        "week_start": week_start.isoformat(),
                        "planned_qty": qty,
                    })

    # Summary counts for verification
    capacity_rows = PRODUCTION_WEEKS * len(locations)
    # Overproduction: 2 locs × 8 weeks = 16 rows
    # Underproduction: 1 loc × 8 weeks = 8 rows
    # Normal: 15 SKUs × 2 locs × 8 weeks = 240 rows
    normal_rows = len(PRODUCTION_NORMAL_SKUS) * 2 * PRODUCTION_WEEKS
    plan_rows = (2 * PRODUCTION_WEEKS) + PRODUCTION_WEEKS + normal_rows
    saturated_sum = len(PRODUCTION_NORMAL_SKUS) * PRODUCTION_SATURATED_QTY
    over_sku = PRODUCTION_OVERPRODUCTION_SKU
    over_qty = PRODUCTION_OVERPRODUCTION_PLANNED_QTY
    under_sku = PRODUCTION_UNDERPRODUCTION_SKU
    under_qty = PRODUCTION_UNDERPRODUCTION_PLANNED_QTY
    print(
        f"production_capacity: {capacity_rows} rows"
        f" (WH-001={PRODUCTION_CAPACITY_WH001}/week, WH-002={PRODUCTION_CAPACITY_WH002}/week,"
        f" {PRODUCTION_WEEKS} weeks)"
    )
    print(
        f"production_plan: {plan_rows} rows —"
        f" overproduction={over_sku}@{over_qty},"
        f" underproduction={under_sku}@{under_qty},"
        f" saturated=WH-001/week0(sum={saturated_sum}>={PRODUCTION_CAPACITY_WH001})"
    )


def generate(config: SampleDataConfig, out_dir: Path = Path("data/sample")) -> None:
    rng = random.Random(config.seed)

    gt_dir = Path("data/sample/ground_truth")
    out_dir.mkdir(parents=True, exist_ok=True)

    skus = _load_csv(gt_dir / "sku_parameters.csv")[: config.sku_count]
    customers = _load_csv(gt_dir / "customer_parameters.csv")
    suppliers = _load_csv(gt_dir / "supplier_parameters.csv")
    locations = _load_csv(gt_dir / "location_parameters.csv")[: config.warehouse_count]

    generate_sku_master(skus, out_dir)
    generate_location_master(locations, out_dir)
    generate_customers(customers, out_dir)
    recent_avg_by_sku = generate_demand_history(skus, rng, out_dir, config)
    generate_inventory(skus, rng, out_dir, config, recent_avg_by_sku)
    generate_supply(skus, suppliers, rng, out_dir)
    generate_cost(skus, rng, out_dir, config)
    generate_forecast_history(skus, rng, out_dir, config)
    generate_customer_orders_and_shipments(skus, rng, out_dir, config)
    generate_production_data(out_dir)

    print(
        f"Sample data generated in {out_dir}/ "
        f"(seed={config.seed}, sku_count={config.sku_count}, "
        f"horizon_days={config.horizon_days}, warehouse_count={config.warehouse_count}, "
        f"missing_rate={config.missing_rate})"
    )


def main(
    seed: int = 42,
    sku_count: int = 30,
    horizon_days: int = 365,
    warehouse_count: int = 2,
    missing_rate: float = 0.02,
) -> None:
    generate(
        SampleDataConfig(
            seed=seed,
            sku_count=sku_count,
            horizon_days=horizon_days,
            warehouse_count=warehouse_count,
            missing_rate=missing_rate,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic sample data")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    parser.add_argument("--sku-count", type=int, default=30, help="SKU count, 1..30 (default: 30)")
    parser.add_argument(
        "--horizon-days", type=int, default=365, help="Demand horizon days, 1..1095 (default: 365)"
    )
    parser.add_argument(
        "--warehouse-count", type=int, default=2, help="Warehouse count, 1..10 (default: 2)"
    )
    parser.add_argument(
        "--missing-rate",
        type=float,
        default=0.02,
        help="Demand missing rate, 0..0.25 (default: 0.02)",
    )
    args = parser.parse_args()
    main(
        seed=args.seed,
        sku_count=args.sku_count,
        horizon_days=args.horizon_days,
        warehouse_count=args.warehouse_count,
        missing_rate=args.missing_rate,
    )
