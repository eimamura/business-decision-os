"""Integration tests for ListStockoutRiskTool against a real PostgreSQL database.

Requires a running PostgreSQL instance reachable via DATABASE_URL.
Run with:
    docker compose up -d db && uv run pytest tests/integration/test_list_stockout_risk_tool_integration.py -v

Without a live DB these tests are skipped automatically when DATABASE_URL is unset.
"""
from __future__ import annotations

import os
from uuid import uuid4

import pytest

from packages.tools.base import ToolContext
from packages.tools.list_stockout_risk_tool import ListStockoutRiskTool

_HAS_DB = bool(os.environ.get("DATABASE_URL"))
_SKIP_NO_DB = pytest.mark.skipif(not _HAS_DB, reason="DATABASE_URL not set")

_REQUIRED_ITEM_KEYS = {
    "sku_id",
    "on_hand_qty",
    "demand_forecast",
    "incoming_supply",
    "projected_ending_stock",
    "risk_level",
    "stockout_date_estimate",
}

_VALID_RISK_LEVELS = {"none", "low", "medium", "high", "critical"}


def _ctx() -> ToolContext:
    return ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="control",
        actor="integration_test",
        correlation_id=uuid4(),
    )


@pytest.fixture(autouse=True)
async def reset_db_pool() -> None:  # type: ignore[misc]
    """Reset the global asyncpg pool before and after each test.

    pytest-asyncio creates a new event loop per test function. The global pool
    singleton in packages/persistence/db.py is bound to the event loop in which
    it was created, so reusing it across tests causes 'loop is closed' errors.
    Resetting the module-level variable forces pool recreation in the current loop.
    """
    import packages.persistence.db as db_module

    db_module._pool = None
    yield  # type: ignore[misc]
    if db_module._pool is not None:
        await db_module._pool.close()
        db_module._pool = None


@_SKIP_NO_DB
async def test_list_stockout_risk_returns_list_and_count_match() -> None:
    """Tool returns a list; count field matches len(items)."""
    tool = ListStockoutRiskTool()
    result = await tool.handle({"horizon_days": 7, "min_risk_level": "low"}, _ctx())

    assert "error" not in result.output, f"Unexpected error: {result.output.get('error')}"
    assert isinstance(result.output["items"], list)
    assert result.output["count"] == len(result.output["items"])


@_SKIP_NO_DB
async def test_list_stockout_risk_items_have_required_keys() -> None:
    """Each returned item contains all required output schema keys."""
    tool = ListStockoutRiskTool()
    result = await tool.handle({"horizon_days": 7, "min_risk_level": "low"}, _ctx())

    assert "error" not in result.output
    for item in result.output["items"]:
        missing = _REQUIRED_ITEM_KEYS - item.keys()
        assert not missing, f"Item missing keys {missing}: {item}"


@_SKIP_NO_DB
async def test_list_stockout_risk_risk_levels_are_valid() -> None:
    """All returned risk_level values are within the expected enumeration."""
    tool = ListStockoutRiskTool()
    result = await tool.handle({"horizon_days": 7, "min_risk_level": "low"}, _ctx())

    assert "error" not in result.output
    for item in result.output["items"]:
        assert item["risk_level"] in _VALID_RISK_LEVELS, (
            f"Unexpected risk_level '{item['risk_level']}' for sku_id={item['sku_id']}"
        )


@_SKIP_NO_DB
async def test_list_stockout_risk_min_critical_filters_correctly() -> None:
    """Items returned with min_risk_level='critical' all have risk_level='critical'."""
    tool = ListStockoutRiskTool()
    result = await tool.handle({"horizon_days": 7, "min_risk_level": "critical"}, _ctx())

    assert "error" not in result.output
    for item in result.output["items"]:
        assert item["risk_level"] == "critical", (
            f"Expected critical, got '{item['risk_level']}' for sku_id={item['sku_id']}"
        )


@_SKIP_NO_DB
async def test_list_stockout_risk_default_params_succeed() -> None:
    """Tool succeeds when called with no explicit parameters (uses defaults)."""
    tool = ListStockoutRiskTool()
    result = await tool.handle({}, _ctx())

    assert "error" not in result.output
    assert "items" in result.output
    assert "count" in result.output
    assert isinstance(result.output["count"], int)
