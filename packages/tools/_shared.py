"""Shared helpers for tools in packages/tools/.

Canonical single implementations of utilities that were previously
copy-pasted across every tool module.
"""
from __future__ import annotations


def db_error_message(exc: Exception) -> str:
    """Return a human-readable error string for a DB exception.

    Returns "no database connection" for asyncpg connection errors and
    missing DATABASE_URL configuration; falls back to str(exc) otherwise.
    """
    message = str(exc).lower()
    class_name = exc.__class__.__name__.lower()
    module_name = exc.__class__.__module__.lower()
    if isinstance(exc, RuntimeError) and "database_url" in message:
        return "no database connection"
    if "asyncpg" in module_name and (
        "connection" in class_name
        or "connection" in message
        or "connect call failed" in message
    ):
        return "no database connection"
    return str(exc)


def classify_stockout_risk(projected_ending_stock: float, demand_forecast: float) -> str:
    """Classify stockout risk level from projected ending stock and demand forecast.

    Returns one of: "none", "low", "medium", "high", "critical".

    Thresholds:
      - demand_forecast == 0                         → "none"
      - projected_ending_stock < 0                   → "critical"
      - ratio = projected / demand >= 0.5            → "low"
      - ratio >= 0.1                                 → "medium"
      - ratio < 0.1                                  → "high"
    """
    if demand_forecast == 0:
        return "none"
    if projected_ending_stock < 0:
        return "critical"
    ratio = projected_ending_stock / demand_forecast
    if ratio >= 0.5:
        return "low"
    if ratio >= 0.1:
        return "medium"
    return "high"
