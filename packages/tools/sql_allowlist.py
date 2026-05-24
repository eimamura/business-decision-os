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
])

_WRITE_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE)\b", re.IGNORECASE
)
_TABLE_PATTERN = re.compile(r"\bFROM\s+(\w+)|\bJOIN\s+(\w+)", re.IGNORECASE)


def check_allowed(table_name: str) -> bool:
    return table_name.lower() in ALLOWED_READ_TABLES


def validate_query(sql: str) -> None:
    """Raises ValueError if the query touches non-allowlisted tables or performs writes."""
    if _WRITE_KEYWORDS.search(sql):
        raise ValueError("Write statements are not allowed")
    for match in _TABLE_PATTERN.finditer(sql):
        table = (match.group(1) or match.group(2)).lower()
        if table not in ALLOWED_READ_TABLES:
            raise ValueError(f"Table '{table}' is not in the allowlist")
