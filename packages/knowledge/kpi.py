from __future__ import annotations

DEFAULT_HORIZON_DAYS = 90


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
