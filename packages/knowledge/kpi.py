from __future__ import annotations

from packages.schemas.recommendation import KpiScore

DEFAULT_HORIZON_DAYS = 90

KPI_SERVICE_LEVEL: str = "service_level"
KPI_TOTAL_SUPPLY_CHAIN_COST: str = "total_supply_chain_cost"


def service_level(stockout_days: float, horizon_days: int = DEFAULT_HORIZON_DAYS) -> float:
    return 1 - stockout_days / horizon_days


def inventory_turnover(cost_of_goods_sold: float, avg_inventory_value: float) -> float:
    return cost_of_goods_sold / avg_inventory_value


def days_on_hand(avg_inventory_units: float, avg_daily_demand: float) -> float:
    return avg_inventory_units / avg_daily_demand


def fill_rate(units_filled: float, units_requested: float) -> float:
    return units_filled / units_requested


def total_supply_chain_cost(
    holding_cost: float,
    ordering_cost: float,
    stockout_cost: float,
) -> float:
    return holding_cost + ordering_cost + stockout_cost


def reorder_point(
    avg_daily_demand: float,
    lead_time_days: float,
    safety_stock: float,
) -> float:
    return avg_daily_demand * lead_time_days + safety_stock


def safety_stock(
    z_score: float,
    lead_time_std: float,
    demand_std: float,
) -> float:
    return z_score * (lead_time_std * demand_std)


def gross_margin_return_on_investment(
    gross_margin: float,
    avg_inventory_investment: float,
) -> float:
    return gross_margin / avg_inventory_investment


def make_stub_kpi_scores(order_qty: float, idx: int) -> list[KpiScore]:
    sl = max(0.0, 0.95 - idx * 0.05)
    fr = max(0.0, 0.90 - idx * 0.03)
    sr = min(1.0, 0.05 + idx * 0.03)
    total_cost = order_qty * 1.2
    return [
        KpiScore(name=KPI_SERVICE_LEVEL, value=sl, unit="%", direction="higher_better"),
        KpiScore(name="fill_rate", value=fr, unit="%", direction="higher_better"),
        KpiScore(name="stockout_rate", value=sr, unit="%", direction="lower_better"),
        KpiScore(name="inventory_turnover", value=4.0, unit="turns/year", direction="higher_better"),
        KpiScore(name="days_on_hand", value=30.0 + idx * 15, unit="days", direction="lower_better"),
        KpiScore(
            name="excess_inventory",
            value=max(0.0, order_qty * 0.1 * idx),
            unit="units",
            direction="lower_better",
        ),
        KpiScore(name="working_capital", value=total_cost * 0.5, unit="USD", direction="lower_better"),
        KpiScore(name=KPI_TOTAL_SUPPLY_CHAIN_COST, value=total_cost, unit="USD", direction="lower_better"),
    ]


def weighted_utility(kpi_scores: list[KpiScore], weights: dict[str, float]) -> float:
    total = 0.0
    for score in kpi_scores:
        weight = weights.get(score.name, 0.0)
        if score.direction == "higher_better":
            total += weight * score.value
        else:
            max_val = 100.0 if score.unit == "%" else 10000.0
            total += weight * max(0.0, 1.0 - score.value / max_val)
    return total
