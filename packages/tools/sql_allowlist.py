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

# Legacy table names that small LLMs generate from training data.
# Applied before guardrail validation so queries still succeed.
_LEGACY_TABLE_MAP: dict[str, str] = {
    "inventory": "inventory_snapshot",
    "supply": "supply_orders",
    "cost": "cost_master",
    "customers": "customer_master",
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
