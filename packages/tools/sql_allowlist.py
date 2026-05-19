from __future__ import annotations

ALLOWED_READ_TABLES: frozenset[str] = frozenset([
    "sku_master",
    "inventory",
    "demand_history",
    "supply",
    "cost",
    "customers",
])


def check_allowed(table_name: str) -> bool:
    return table_name.lower() in ALLOWED_READ_TABLES


def validate_query(sql: str) -> None:
    """Raises ValueError if the query touches non-allowlisted tables or performs writes."""
    raise NotImplementedError("Phase 1 — SQL validation")
