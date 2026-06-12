"""T-486: Unit tests for P76 B-02/B-03 contract changes.

Covers:
- evaluator_tool: missing risk_thresholds.yaml → RuntimeError; present yaml → normal.
- supply order tools: >100 rows → capped at 100, truncated=True; ≤100 → truncated=False.
- _shared helpers: classify_stockout_risk boundary values; db_error_message variants.
- data_catalog_search: pool raising → output contains error key and degraded rows.
- missing_data population: finance holding cost (no cost_master → entry; happy path → []).
- DOI: registry count 32→31 (calculate_days_of_supply removed).
"""
from __future__ import annotations

import datetime
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from packages.tools.base import ToolContext
from packages.tools._shared import classify_stockout_risk, db_error_message


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_ctx() -> ToolContext:
    return ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="control",
        actor="test",
        correlation_id=uuid4(),
    )


def make_fetch_pool(rows: list) -> MagicMock:
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = rows
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_pool


def make_fetchrow_pool(row_value: object) -> MagicMock:
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = row_value
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_pool


# ===========================================================================
# evaluator_tool: T-478 — RuntimeError when risk_thresholds.yaml is missing
# ===========================================================================


def test_evaluator_missing_yaml_raises_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """_load_thresholds raises RuntimeError when risk_thresholds.yaml is absent."""
    from packages.tools import evaluator_tool

    monkeypatch.setattr(evaluator_tool, "_THRESHOLDS_PATH", "/nonexistent/risk_thresholds.yaml")
    with pytest.raises(RuntimeError, match="risk_thresholds.yaml not found"):
        evaluator_tool._load_thresholds()


def test_evaluator_present_yaml_returns_thresholds(monkeypatch: pytest.MonkeyPatch) -> None:
    """_load_thresholds succeeds with a valid yaml file and returns the thresholds dict."""
    import yaml
    from packages.tools import evaluator_tool

    thresholds_content = {
        "thresholds": {
            "high": {"service_level_max": 0.85},
            "medium": {"service_level_max": 0.95},
        }
    }
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False
    ) as tmp:
        yaml.dump(thresholds_content, tmp)
        tmp_path = tmp.name

    try:
        monkeypatch.setattr(evaluator_tool, "_THRESHOLDS_PATH", tmp_path)
        result = evaluator_tool._load_thresholds()
        assert "high" in result
        assert "medium" in result
    finally:
        os.unlink(tmp_path)


# ===========================================================================
# supply order tools: T-479 — LIMIT + truncated flag
# ===========================================================================


def _open_order_row(idx: int) -> dict:
    return {
        "sku_id": f"SKU-{idx}",
        "supplier_id": "SUP-1",
        "order_date": datetime.date(2026, 1, 1),
        "expected_arrival": datetime.date(2026, 2, 1),
        "quantity": 10.0,
        "status": "pending",
    }


def _delayed_order_row(idx: int) -> dict:
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    return {
        "id": str(uuid4()),
        "sku_id": f"SKU-{idx}",
        "supplier_id": "SUP-1",
        "expected_arrival": yesterday,
        "quantity": 5.0,
        "status": "pending",
    }


async def test_open_orders_above_100_rows_capped_and_truncated():
    """DB returns 101 rows → output capped at 100, truncated=True."""
    from packages.tools.supply_open_orders_tool import GetOpenSupplyOrdersTool

    rows = [_open_order_row(i) for i in range(101)]
    mock_pool = make_fetch_pool(rows)

    with patch("packages.tools.supply_open_orders_tool.get_pool", return_value=mock_pool):
        tool = GetOpenSupplyOrdersTool()
        result = await tool.handle({}, make_ctx())

    assert result.output["order_count"] == 100
    assert result.output["truncated"] is True
    assert len(result.output["orders"]) == 100


async def test_open_orders_at_or_below_100_rows_not_truncated():
    """DB returns exactly 100 rows → truncated=False."""
    from packages.tools.supply_open_orders_tool import GetOpenSupplyOrdersTool

    rows = [_open_order_row(i) for i in range(100)]
    mock_pool = make_fetch_pool(rows)

    with patch("packages.tools.supply_open_orders_tool.get_pool", return_value=mock_pool):
        tool = GetOpenSupplyOrdersTool()
        result = await tool.handle({}, make_ctx())

    assert result.output["order_count"] == 100
    assert result.output["truncated"] is False


async def test_delayed_orders_above_100_rows_capped_and_truncated():
    """DB returns 101 delayed rows → output capped at 100, truncated=True."""
    from packages.tools.supply_delayed_orders_tool import GetDelayedSupplyOrdersTool

    rows = [_delayed_order_row(i) for i in range(101)]
    mock_pool = make_fetch_pool(rows)

    with patch("packages.tools.supply_delayed_orders_tool.get_pool", return_value=mock_pool):
        tool = GetDelayedSupplyOrdersTool()
        result = await tool.handle({}, make_ctx())

    assert result.output["order_count"] == 100
    assert result.output["truncated"] is True
    assert len(result.output["orders"]) == 100


async def test_delayed_orders_below_100_rows_not_truncated():
    """DB returns 50 delayed rows → truncated=False."""
    from packages.tools.supply_delayed_orders_tool import GetDelayedSupplyOrdersTool

    rows = [_delayed_order_row(i) for i in range(50)]
    mock_pool = make_fetch_pool(rows)

    with patch("packages.tools.supply_delayed_orders_tool.get_pool", return_value=mock_pool):
        tool = GetDelayedSupplyOrdersTool()
        result = await tool.handle({}, make_ctx())

    assert result.output["order_count"] == 50
    assert result.output["truncated"] is False


# ===========================================================================
# _shared helpers: T-480 — classify_stockout_risk boundary values
# ===========================================================================


def test_classify_stockout_risk_zero_demand_returns_none() -> None:
    assert classify_stockout_risk(100.0, 0.0) == "none"


def test_classify_stockout_risk_negative_stock_returns_critical() -> None:
    assert classify_stockout_risk(-1.0, 10.0) == "critical"


def test_classify_stockout_risk_ratio_above_0_5_returns_low() -> None:
    # ratio = 50 / 100 = 0.5 → "low" (boundary: >= 0.5)
    assert classify_stockout_risk(50.0, 100.0) == "low"


def test_classify_stockout_risk_ratio_just_above_0_1_returns_medium() -> None:
    # ratio = 11 / 100 = 0.11 → "medium" (0.1 <= ratio < 0.5)
    assert classify_stockout_risk(11.0, 100.0) == "medium"


def test_classify_stockout_risk_ratio_just_below_0_1_returns_high() -> None:
    # ratio = 9 / 100 = 0.09 → "high" (ratio < 0.1)
    assert classify_stockout_risk(9.0, 100.0) == "high"


def test_classify_stockout_risk_ratio_exactly_0_1_returns_medium() -> None:
    # ratio = 10 / 100 = 0.1 → "medium" (boundary: >= 0.1)
    assert classify_stockout_risk(10.0, 100.0) == "medium"


# ===========================================================================
# _shared helpers: T-480 — db_error_message variants
# ===========================================================================


def test_db_error_message_database_url_runtime_error_returns_no_database_connection() -> None:
    """RuntimeError whose message contains 'database_url' returns 'no database connection'."""
    exc = RuntimeError("DATABASE_URL not configured")
    assert db_error_message(exc) == "no database connection"


def test_db_error_message_asyncpg_module_connection_error_returns_no_database_connection() -> None:
    """Exception from asyncpg module with 'connection' in class name returns 'no database connection'."""

    # Build an exception type that mimics asyncpg.exceptions._base so the module-name
    # and class-name guards in db_error_message both fire.
    AsyncpgConnectionError = type(
        "ConnectionDoError",
        (Exception,),
        {"__module__": "asyncpg.exceptions._base"},
    )
    exc = AsyncpgConnectionError("connect call failed")
    assert db_error_message(exc) == "no database connection"


def test_db_error_message_generic_exception_returns_str_exc() -> None:
    exc = ValueError("unexpected column type")
    assert db_error_message(exc) == "unexpected column type"


def test_db_error_message_runtime_error_without_database_url_returns_str_exc() -> None:
    exc = RuntimeError("something else went wrong")
    assert db_error_message(exc) == "something else went wrong"


# ===========================================================================
# data_catalog_search: T-481 — pool raising → error key + degraded rows
# ===========================================================================


async def test_data_catalog_search_db_error_returns_error_key_and_degraded_rows():
    """When list_tables_with_counts raises, output has error key and row_count=None."""
    from packages.tools.data_catalog_search_tool import DataCatalogSearchTool

    with patch(
        "packages.tools.data_catalog_search_tool.list_tables_with_counts",
        side_effect=RuntimeError("DATABASE_URL not configured"),
    ):
        tool = DataCatalogSearchTool()
        result = await tool.handle({}, make_ctx())

    assert "error" in result.output
    assert "database" in result.output["error"].lower()
    # Degraded rows: all registered tables appear with row_count=None
    assert isinstance(result.output["tables"], list)
    assert len(result.output["tables"]) > 0
    assert all(row["row_count"] is None for row in result.output["tables"])


async def test_data_catalog_search_success_no_error_key():
    """Successful DB call → no error key and missing_data is empty."""
    from packages.tools.data_catalog_search_tool import DataCatalogSearchTool

    fake_result = [{"table_name": "inventory_snapshot", "row_count": 500}]
    with patch(
        "packages.tools.data_catalog_search_tool.list_tables_with_counts",
        return_value=fake_result,
    ):
        tool = DataCatalogSearchTool()
        result = await tool.handle({}, make_ctx())

    assert "error" not in result.output
    assert result.output["missing_data"] == []


# ===========================================================================
# missing_data population: T-484 — finance holding cost tool
# ===========================================================================


async def test_holding_cost_no_cost_master_row_populates_missing_data():
    """No cost_master row → missing_data has an entry mentioning the SKU."""
    from packages.tools.finance_holding_cost_tool import CalculateHoldingCostImpactTool

    mock_pool = make_fetchrow_pool(None)

    with patch("packages.tools.finance_holding_cost_tool.get_pool", return_value=mock_pool):
        tool = CalculateHoldingCostImpactTool()
        result = await tool.handle({"sku_id": "SKU-MISSING", "excess_units": 50}, make_ctx())

    assert len(result.output["missing_data"]) > 0
    assert any("SKU-MISSING" in entry for entry in result.output["missing_data"])


async def test_holding_cost_happy_path_missing_data_is_empty():
    """When cost_master row is present, missing_data is []."""
    from packages.tools.finance_holding_cost_tool import CalculateHoldingCostImpactTool

    mock_row = {
        "holding_cost": 5.0,
        "period_start": datetime.date(2026, 1, 1),
    }
    mock_pool = make_fetchrow_pool(mock_row)

    with patch("packages.tools.finance_holding_cost_tool.get_pool", return_value=mock_pool):
        tool = CalculateHoldingCostImpactTool()
        result = await tool.handle({"sku_id": "SKU-X", "excess_units": 100}, make_ctx())

    assert result.output["missing_data"] == []


# ===========================================================================
# DOI missing_data: T-484 — no demand history → missing_data populated
# ===========================================================================


async def test_doi_no_demand_history_populates_missing_data():
    """When avg_daily_demand is None, missing_data has an entry."""
    from packages.tools.inventory_doi_tool import CalculateDaysOfInventoryTool

    mock_conn = AsyncMock()
    mock_conn.fetchrow.side_effect = [
        {"on_hand_qty": 100},
        {"avg_daily": None},
        {"lead_time_days_mean": None},
    ]
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch("packages.tools.inventory_doi_tool.get_pool", return_value=mock_pool):
        tool = CalculateDaysOfInventoryTool()
        result = await tool.handle({"sku_id": "SKU-NODEMAND"}, make_ctx())

    assert len(result.output["missing_data"]) > 0
    assert any("demand_history" in entry for entry in result.output["missing_data"])


async def test_doi_happy_path_missing_data_is_empty():
    """When all data is present, missing_data is []."""
    from packages.tools.inventory_doi_tool import CalculateDaysOfInventoryTool

    mock_conn = AsyncMock()
    mock_conn.fetchrow.side_effect = [
        {"on_hand_qty": 200},
        {"avg_daily": 10.0},
        {"lead_time_days_mean": 7},
    ]
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch("packages.tools.inventory_doi_tool.get_pool", return_value=mock_pool):
        tool = CalculateDaysOfInventoryTool()
        result = await tool.handle({"sku_id": "SKU-OK"}, make_ctx())

    assert result.output["missing_data"] == []


# ===========================================================================
# Registry count: T-483 — DOS removed, registry count 32→31
# ===========================================================================


def test_tool_registry_count_is_37_after_p89_b02() -> None:
    """Registry count must reflect current tools; updated in P89-B-02 (2 production tools added)."""
    from packages.tools import create_tool_registry

    registry = create_tool_registry()
    count = len(registry._tools)
    assert count == 37, (
        f"Expected 37 registered tools after P89-B-02 "
        "(analyze_production_plan_gap + identify_binding_constraint added), got {count}. "
        "Update this test if tools are intentionally added/removed."
    )


def test_calculate_days_of_supply_not_in_registry() -> None:
    """calculate_days_of_supply must no longer be in the tool registry (T-483)."""
    from packages.tools import create_tool_registry

    registry = create_tool_registry()
    assert "calculate_days_of_supply" not in registry._tools
