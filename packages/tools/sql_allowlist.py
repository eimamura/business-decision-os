from __future__ import annotations

import re

ALLOWED_READ_TABLES: frozenset[str] = frozenset([
    "sku_master",
    "location_master",
    "customer_master",
    "inventory_snapshot",
    "demand_history",
    "supply_orders",
    "cost_master",
    "forecast_history",
    "customer_orders",
    "shipments",
    "production_capacity",
    "production_plan",
])

# Legacy table names that small LLMs generate from training data.
# Applied before guardrail validation so queries still succeed.
#
# "orders" → "customer_orders": safe because the regex uses \b word boundaries,
# so "supply_orders" contains "orders" as a suffix but NOT as a whole word —
# the boundary before "o" in "supply_orders" is not a word boundary (preceded by "_").
# Verified: re.sub(r'\borders\b', ..., 'supply_orders') → 'supply_orders' (unchanged).
_LEGACY_TABLE_MAP: dict[str, str] = {
    "inventory": "inventory_snapshot",
    "supply": "supply_orders",
    "cost": "cost_master",
    "customers": "customer_master",
    "orders": "customer_orders",
}

_LEGACY_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _LEGACY_TABLE_MAP) + r")\b",
    re.IGNORECASE,
)


def canonicalize_table_names(sql: str) -> str:
    """Replace legacy table names with their current canonical names."""
    return _LEGACY_PATTERN.sub(
        lambda m: _LEGACY_TABLE_MAP[m.group(0).lower()], sql
    )


def check_allowed(table_name: str) -> bool:
    return table_name.lower() in ALLOWED_READ_TABLES
