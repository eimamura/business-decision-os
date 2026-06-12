"""Unit tests for list_today_exceptions_tool (T-538).

Covers:
- Severity ordering: critical > high > medium across mixed domains
- Per-domain counts correctness
- Cap at 50 + truncated flag set/unset
- missing_data populated when a source screen has no evaluable data (zero-demand SKUs)
- missing_data populated on screen-level DB errors
- Empty-DB shape: all four screens empty -> exceptions: [], counts zeroed, valid contract
- data_quality screen delegates to catalog_repo.get_null_profile (no f-string SQL in tool)
"""
from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from packages.tools.base import ToolContext
from packages.tools.list_today_exceptions_tool import ListTodayExceptionsTool


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


def _stockout_row(
    sku_id: str = "SKU-A",
    on_hand_qty: float = 100.0,
    avg_daily: float = 10.0,
    incoming_supply: float = 0.0,
) -> dict:
    return {
        "sku_id": sku_id,
        "on_hand_qty": on_hand_qty,
        "avg_daily": avg_daily,
        "incoming_supply": incoming_supply,
    }


def _supply_order_row(
    sku_id: str = "SKU-A",
    supplier_id: str = "SUP-1",
    quantity: float = 50.0,
    status: str = "pending",
    days_overdue: int = 1,
    row_id: str | None = None,
) -> dict:
    expected_arrival = datetime.date.today() - datetime.timedelta(days=days_overdue)
    return {
        "id": row_id or str(uuid4()),
        "sku_id": sku_id,
        "supplier_id": supplier_id,
        "expected_arrival": expected_arrival,
        "quantity": quantity,
        "status": status,
    }


def _demand_row(
    sku_id: str = "SKU-A",
    quantity: float = 10.0,
    days_ago: int = 1,
    is_missing: bool = False,
) -> dict:
    return {
        "sku_id": sku_id,
        "date": datetime.date.today() - datetime.timedelta(days=days_ago),
        "quantity": quantity,
        "is_missing": is_missing,
    }


def _make_pool_multi(side_effects: list) -> MagicMock:
    """Build a pool mock whose conn.fetch returns results from a side-effects list in order."""
    mock_conn = AsyncMock()
    mock_conn.fetch.side_effect = side_effects
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_pool


def _make_pool(fetch_return: list) -> MagicMock:
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = fetch_return
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_pool


def _null_profile_no_issues(table_name: str) -> dict:
    return {"total_rows": 100, "columns": [{"column_name": "sku_id", "null_count": 0, "null_pct": 0.0}]}


def _null_profile_with_issue(table_name: str) -> dict:
    return {
        "total_rows": 100,
        "columns": [{"column_name": "supplier_id", "null_count": 5, "null_pct": 5.0}],
    }


def _null_profile_empty_table(table_name: str) -> dict:
    return {"total_rows": 0, "columns": []}


# ---------------------------------------------------------------------------
# (1) Severity ordering: critical > high > medium across mixed domains
# ---------------------------------------------------------------------------


async def test_exceptions_sorted_critical_before_high_before_medium_across_domains():
    # stockout_risk screen: one critical SKU (avg_daily=10, on_hand=5, horizon=7 -> ending=-65)
    # supply_delays screen: high (days_overdue=1 < 7)
    # demand_anomalies: medium (missing anomaly type)
    # data_quality: medium

    stockout_rows = [
        _stockout_row("SKU-CRIT", on_hand_qty=5.0, avg_daily=10.0),
    ]
    # Supply delay row with days_overdue=1 -> high severity
    supply_rows = [_supply_order_row("SKU-A", days_overdue=1)]

    # Demand anomaly rows that will produce a "missing" type (medium severity)
    # 3+ rows per SKU needed; use is_missing=True to trigger "missing" anomaly
    demand_rows = [
        _demand_row("SKU-B", days_ago=3, is_missing=True),
        _demand_row("SKU-B", days_ago=2, quantity=5.0),
        _demand_row("SKU-B", days_ago=1, quantity=5.0),
    ]

    pool_stockout = _make_pool(stockout_rows)
    pool_supply = _make_pool(supply_rows)
    pool_demand = _make_pool(demand_rows)

    # data_quality: no issues
    async def mock_get_null_profile(table_name: str) -> dict:
        return _null_profile_no_issues(table_name)

    with (
        patch("packages.tools.list_today_exceptions_tool._fetch_all_stockout_risk") as mock_stockout,
        patch("packages.tools.list_today_exceptions_tool._fetch_delayed_orders") as mock_supply,
        patch("packages.tools.list_today_exceptions_tool._fetch_skus_with_recent_anomalies") as mock_demand,
        patch("packages.tools.list_today_exceptions_tool._fetch_data_quality_issues") as mock_quality,
    ):
        mock_stockout.return_value = stockout_rows
        mock_supply.return_value = supply_rows
        mock_demand.return_value = [
            {
                "sku_id": "SKU-B",
                "date": "2026-01-01",
                "quantity": None,
                "z_score": None,
                "anomaly_type": "missing",
            }
        ]
        mock_quality.return_value = []

        tool = ListTodayExceptionsTool()
        result = await tool.handle({}, make_ctx())

    exceptions = result.output["exceptions"]
    severities = [e["severity"] for e in exceptions]

    # critical must come before high, high before medium
    assert "critical" in severities
    assert "high" in severities
    assert "medium" in severities

    first_critical = severities.index("critical")
    first_high = severities.index("high")
    first_medium = severities.index("medium")
    assert first_critical < first_high
    assert first_high < first_medium


async def test_exceptions_all_same_severity_grouped_by_domain():
    """When all exceptions have the same severity they are grouped alphabetically by domain."""
    with (
        patch("packages.tools.list_today_exceptions_tool._fetch_all_stockout_risk") as mock_stockout,
        patch("packages.tools.list_today_exceptions_tool._fetch_delayed_orders") as mock_supply,
        patch("packages.tools.list_today_exceptions_tool._fetch_skus_with_recent_anomalies") as mock_demand,
        patch("packages.tools.list_today_exceptions_tool._fetch_data_quality_issues") as mock_quality,
    ):
        # Both screens return medium anomalies
        mock_stockout.return_value = []
        mock_supply.return_value = []
        mock_demand.return_value = [
            {
                "sku_id": "SKU-A",
                "date": "2026-01-01",
                "quantity": 0.0,
                "z_score": None,
                "anomaly_type": "stockout",
            }
        ]
        mock_quality.return_value = [
            {
                "table_name": "inventory_snapshot",
                "column_name": "sku_id",
                "null_count": 1,
                "null_pct": 1.0,
                "total_rows": 100,
            }
        ]

        tool = ListTodayExceptionsTool()
        result = await tool.handle({}, make_ctx())

    exceptions = result.output["exceptions"]
    # all medium — domains should be alphabetically sorted
    domains = [e["domain"] for e in exceptions]
    assert domains == sorted(domains)


# ---------------------------------------------------------------------------
# (2) Per-domain counts correctness
# ---------------------------------------------------------------------------


async def test_counts_per_domain_match_actual_exceptions():
    """counts[domain] must equal the number of exceptions with that domain."""
    with (
        patch("packages.tools.list_today_exceptions_tool._fetch_all_stockout_risk") as mock_stockout,
        patch("packages.tools.list_today_exceptions_tool._fetch_delayed_orders") as mock_supply,
        patch("packages.tools.list_today_exceptions_tool._fetch_skus_with_recent_anomalies") as mock_demand,
        patch("packages.tools.list_today_exceptions_tool._fetch_data_quality_issues") as mock_quality,
    ):
        # 2 critical stockout exceptions
        mock_stockout.return_value = [
            _stockout_row("SKU-CRIT1", on_hand_qty=5.0, avg_daily=10.0),
            _stockout_row("SKU-CRIT2", on_hand_qty=3.0, avg_daily=10.0),
        ]
        # 1 supply delay exception
        mock_supply.return_value = [_supply_order_row("SKU-A", days_overdue=3)]
        # 0 demand anomalies
        mock_demand.return_value = []
        # 2 data quality exceptions
        mock_quality.return_value = [
            {
                "table_name": "demand_history",
                "column_name": "quantity",
                "null_count": 10,
                "null_pct": 5.0,
                "total_rows": 200,
            },
            {
                "table_name": "supply_orders",
                "column_name": "supplier_id",
                "null_count": 2,
                "null_pct": 1.0,
                "total_rows": 200,
            },
        ]

        tool = ListTodayExceptionsTool()
        result = await tool.handle({}, make_ctx())

    counts = result.output["counts"]
    assert counts["stockout_risk"] == 2
    assert counts["supply_delays"] == 1
    assert counts.get("demand_anomalies", 0) == 0
    assert counts["data_quality"] == 2


async def test_counts_are_computed_on_all_exceptions_before_cap():
    """counts reflect pre-cap totals even when the list is truncated."""
    # Generate 60 stockout exceptions (> 50 cap) and 5 supply delays
    stockout_rows = [
        _stockout_row(f"SKU-{i:03d}", on_hand_qty=5.0, avg_daily=10.0) for i in range(60)
    ]
    supply_rows = [_supply_order_row(f"SKU-D{i}", days_overdue=1) for i in range(5)]

    with (
        patch("packages.tools.list_today_exceptions_tool._fetch_all_stockout_risk") as mock_stockout,
        patch("packages.tools.list_today_exceptions_tool._fetch_delayed_orders") as mock_supply,
        patch("packages.tools.list_today_exceptions_tool._fetch_skus_with_recent_anomalies") as mock_demand,
        patch("packages.tools.list_today_exceptions_tool._fetch_data_quality_issues") as mock_quality,
    ):
        mock_stockout.return_value = stockout_rows
        mock_supply.return_value = supply_rows
        mock_demand.return_value = []
        mock_quality.return_value = []

        tool = ListTodayExceptionsTool()
        result = await tool.handle({}, make_ctx())

    counts = result.output["counts"]
    # counts must reflect all 60 stockout + 5 supply, not just the capped 50
    assert counts["stockout_risk"] == 60
    assert counts["supply_delays"] == 5


# ---------------------------------------------------------------------------
# (3) Cap at 50 + truncated flag
# ---------------------------------------------------------------------------


async def test_cap_at_50_sets_truncated_true_when_exceeding():
    """When total exceptions > 50, exceptions list is capped at 50 and truncated=True."""
    # 51 stockout exceptions
    stockout_rows = [
        _stockout_row(f"SKU-{i:03d}", on_hand_qty=5.0, avg_daily=10.0) for i in range(51)
    ]

    with (
        patch("packages.tools.list_today_exceptions_tool._fetch_all_stockout_risk") as mock_stockout,
        patch("packages.tools.list_today_exceptions_tool._fetch_delayed_orders") as mock_supply,
        patch("packages.tools.list_today_exceptions_tool._fetch_skus_with_recent_anomalies") as mock_demand,
        patch("packages.tools.list_today_exceptions_tool._fetch_data_quality_issues") as mock_quality,
    ):
        mock_stockout.return_value = stockout_rows
        mock_supply.return_value = []
        mock_demand.return_value = []
        mock_quality.return_value = []

        tool = ListTodayExceptionsTool()
        result = await tool.handle({}, make_ctx())

    assert len(result.output["exceptions"]) == 50
    assert result.output["truncated"] is True


async def test_truncated_false_when_under_50():
    """When total exceptions <= 50, truncated must be False."""
    stockout_rows = [
        _stockout_row(f"SKU-{i:03d}", on_hand_qty=5.0, avg_daily=10.0) for i in range(10)
    ]

    with (
        patch("packages.tools.list_today_exceptions_tool._fetch_all_stockout_risk") as mock_stockout,
        patch("packages.tools.list_today_exceptions_tool._fetch_delayed_orders") as mock_supply,
        patch("packages.tools.list_today_exceptions_tool._fetch_skus_with_recent_anomalies") as mock_demand,
        patch("packages.tools.list_today_exceptions_tool._fetch_data_quality_issues") as mock_quality,
    ):
        mock_stockout.return_value = stockout_rows
        mock_supply.return_value = []
        mock_demand.return_value = []
        mock_quality.return_value = []

        tool = ListTodayExceptionsTool()
        result = await tool.handle({}, make_ctx())

    assert len(result.output["exceptions"]) == 10
    assert result.output["truncated"] is False


async def test_truncated_false_when_exactly_50():
    """When total exceptions == 50, truncated must be False (not > 50)."""
    stockout_rows = [
        _stockout_row(f"SKU-{i:03d}", on_hand_qty=5.0, avg_daily=10.0) for i in range(50)
    ]

    with (
        patch("packages.tools.list_today_exceptions_tool._fetch_all_stockout_risk") as mock_stockout,
        patch("packages.tools.list_today_exceptions_tool._fetch_delayed_orders") as mock_supply,
        patch("packages.tools.list_today_exceptions_tool._fetch_skus_with_recent_anomalies") as mock_demand,
        patch("packages.tools.list_today_exceptions_tool._fetch_data_quality_issues") as mock_quality,
    ):
        mock_stockout.return_value = stockout_rows
        mock_supply.return_value = []
        mock_demand.return_value = []
        mock_quality.return_value = []

        tool = ListTodayExceptionsTool()
        result = await tool.handle({}, make_ctx())

    assert len(result.output["exceptions"]) == 50
    assert result.output["truncated"] is False


# ---------------------------------------------------------------------------
# (4) missing_data populated when a source screen has no evaluable data
# ---------------------------------------------------------------------------


async def test_missing_data_populated_for_zero_demand_skus():
    """Stockout screen: SKUs with avg_daily=0 contribute missing_data entries."""
    stockout_rows = [
        _stockout_row("SKU-NO-DEMAND-1", on_hand_qty=100.0, avg_daily=0.0),
        _stockout_row("SKU-NO-DEMAND-2", on_hand_qty=200.0, avg_daily=0.0),
    ]

    with (
        patch("packages.tools.list_today_exceptions_tool._fetch_all_stockout_risk") as mock_stockout,
        patch("packages.tools.list_today_exceptions_tool._fetch_delayed_orders") as mock_supply,
        patch("packages.tools.list_today_exceptions_tool._fetch_skus_with_recent_anomalies") as mock_demand,
        patch("packages.tools.list_today_exceptions_tool._fetch_data_quality_issues") as mock_quality,
    ):
        mock_stockout.return_value = stockout_rows
        mock_supply.return_value = []
        mock_demand.return_value = []
        mock_quality.return_value = []

        tool = ListTodayExceptionsTool()
        result = await tool.handle({}, make_ctx())

    missing = result.output["missing_data"]
    assert len(missing) == 2
    # Each entry must identify the SKU
    for entry in missing:
        assert "SKU-NO-DEMAND-1" in entry or "SKU-NO-DEMAND-2" in entry


async def test_missing_data_only_for_zero_demand_skus_not_valid_ones():
    """Only zero-demand SKUs appear in missing_data; positive-demand SKUs are evaluated."""
    stockout_rows = [
        _stockout_row("SKU-OK", on_hand_qty=5.0, avg_daily=10.0),  # critical risk
        _stockout_row("SKU-ZERO", on_hand_qty=100.0, avg_daily=0.0),  # no demand
    ]

    with (
        patch("packages.tools.list_today_exceptions_tool._fetch_all_stockout_risk") as mock_stockout,
        patch("packages.tools.list_today_exceptions_tool._fetch_delayed_orders") as mock_supply,
        patch("packages.tools.list_today_exceptions_tool._fetch_skus_with_recent_anomalies") as mock_demand,
        patch("packages.tools.list_today_exceptions_tool._fetch_data_quality_issues") as mock_quality,
    ):
        mock_stockout.return_value = stockout_rows
        mock_supply.return_value = []
        mock_demand.return_value = []
        mock_quality.return_value = []

        tool = ListTodayExceptionsTool()
        result = await tool.handle({}, make_ctx())

    missing = result.output["missing_data"]
    # Only the zero-demand SKU should appear
    assert len(missing) == 1
    assert "SKU-ZERO" in missing[0]

    # SKU-OK must still appear in exceptions
    sku_ids = {e["sku_id"] for e in result.output["exceptions"]}
    assert "SKU-OK" in sku_ids


# ---------------------------------------------------------------------------
# (5) missing_data populated on screen-level DB errors
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "failing_screen,expected_prefix",
    [
        ("_fetch_all_stockout_risk", "stockout_risk screen unavailable"),
        ("_fetch_delayed_orders", "supply_delays screen unavailable"),
        ("_fetch_skus_with_recent_anomalies", "demand_anomalies screen unavailable"),
        ("_fetch_data_quality_issues", "data_quality screen unavailable"),
    ],
)
async def test_missing_data_populated_on_screen_db_error(
    failing_screen: str, expected_prefix: str
) -> None:
    """Each screen's DB error is captured in missing_data; other screens still run."""
    all_screens = {
        "_fetch_all_stockout_risk": [],
        "_fetch_delayed_orders": [],
        "_fetch_skus_with_recent_anomalies": [],
        "_fetch_data_quality_issues": [],
    }

    patchers = {}
    for screen_fn, default_return in all_screens.items():
        patcher = patch(f"packages.tools.list_today_exceptions_tool.{screen_fn}")
        patchers[screen_fn] = patcher

    mocks = {}
    for screen_fn, patcher in patchers.items():
        mocks[screen_fn] = patcher.start()
        if screen_fn == failing_screen:
            mocks[screen_fn].side_effect = RuntimeError("database_url not set")
        else:
            mocks[screen_fn].return_value = []

    try:
        tool = ListTodayExceptionsTool()
        result = await tool.handle({}, make_ctx())
    finally:
        for patcher in patchers.values():
            patcher.stop()

    missing = result.output["missing_data"]
    assert any(m.startswith(expected_prefix) for m in missing), (
        f"Expected missing_data entry starting with '{expected_prefix}', got {missing}"
    )
    # The tool must still return a valid contract shape
    assert "exceptions" in result.output
    assert "counts" in result.output
    assert "truncated" in result.output


# ---------------------------------------------------------------------------
# (6) Empty-DB shape
# ---------------------------------------------------------------------------


async def test_empty_db_returns_valid_contract_shape():
    """When all four screens return empty, the output has exceptions=[], counts={}, truncated=False."""
    with (
        patch("packages.tools.list_today_exceptions_tool._fetch_all_stockout_risk") as mock_stockout,
        patch("packages.tools.list_today_exceptions_tool._fetch_delayed_orders") as mock_supply,
        patch("packages.tools.list_today_exceptions_tool._fetch_skus_with_recent_anomalies") as mock_demand,
        patch("packages.tools.list_today_exceptions_tool._fetch_data_quality_issues") as mock_quality,
    ):
        mock_stockout.return_value = []
        mock_supply.return_value = []
        mock_demand.return_value = []
        mock_quality.return_value = []

        tool = ListTodayExceptionsTool()
        result = await tool.handle({}, make_ctx())

    output = result.output
    assert output["exceptions"] == []
    assert output["counts"] == {}
    assert output["truncated"] is False
    assert isinstance(output["missing_data"], list)


async def test_empty_db_output_has_all_required_contract_keys():
    """Output must always contain all four required keys from the output_schema."""
    with (
        patch("packages.tools.list_today_exceptions_tool._fetch_all_stockout_risk") as mock_stockout,
        patch("packages.tools.list_today_exceptions_tool._fetch_delayed_orders") as mock_supply,
        patch("packages.tools.list_today_exceptions_tool._fetch_skus_with_recent_anomalies") as mock_demand,
        patch("packages.tools.list_today_exceptions_tool._fetch_data_quality_issues") as mock_quality,
    ):
        mock_stockout.return_value = []
        mock_supply.return_value = []
        mock_demand.return_value = []
        mock_quality.return_value = []

        tool = ListTodayExceptionsTool()
        result = await tool.handle({}, make_ctx())

    required_keys = {"exceptions", "counts", "truncated", "missing_data"}
    assert required_keys <= result.output.keys()


# ---------------------------------------------------------------------------
# (7) data_quality screen delegates to catalog_repo.get_null_profile
# ---------------------------------------------------------------------------


async def test_data_quality_delegates_to_get_null_profile_not_raw_sql():
    """_fetch_data_quality_issues calls get_null_profile, not raw f-string SQL."""
    call_log: list[str] = []

    async def mock_get_null_profile(table_name: str) -> dict:
        call_log.append(table_name)
        return _null_profile_no_issues(table_name)

    with (
        patch("packages.tools.list_today_exceptions_tool._fetch_all_stockout_risk") as mock_stockout,
        patch("packages.tools.list_today_exceptions_tool._fetch_delayed_orders") as mock_supply,
        patch("packages.tools.list_today_exceptions_tool._fetch_skus_with_recent_anomalies") as mock_demand,
        patch(
            "packages.persistence.catalog_repo.get_null_profile",
            side_effect=mock_get_null_profile,
        ),
        patch(
            "packages.tools.list_today_exceptions_tool.get_null_profile",
            side_effect=mock_get_null_profile,
        ),
    ):
        mock_stockout.return_value = []
        mock_supply.return_value = []
        mock_demand.return_value = []

        tool = ListTodayExceptionsTool()
        await tool.handle({}, make_ctx())

    # get_null_profile must have been called at least once (once per ALLOWED_READ_TABLE)
    assert len(call_log) > 0


async def test_data_quality_issues_appear_in_exceptions():
    """Quality issues (null_count > 0) produce exception items in the output."""
    with (
        patch("packages.tools.list_today_exceptions_tool._fetch_all_stockout_risk") as mock_stockout,
        patch("packages.tools.list_today_exceptions_tool._fetch_delayed_orders") as mock_supply,
        patch("packages.tools.list_today_exceptions_tool._fetch_skus_with_recent_anomalies") as mock_demand,
        patch("packages.tools.list_today_exceptions_tool._fetch_data_quality_issues") as mock_quality,
    ):
        mock_stockout.return_value = []
        mock_supply.return_value = []
        mock_demand.return_value = []
        mock_quality.return_value = [
            {
                "table_name": "demand_history",
                "column_name": "quantity",
                "null_count": 15,
                "null_pct": 7.5,
                "total_rows": 200,
            }
        ]

        tool = ListTodayExceptionsTool()
        result = await tool.handle({}, make_ctx())

    exceptions = result.output["exceptions"]
    assert len(exceptions) == 1
    exc = exceptions[0]
    assert exc["domain"] == "data_quality"
    assert exc["severity"] == "medium"
    assert "15" in exc["headline_metric"]
    assert exc["sku_id"] is None
    assert exc["order_ref"] is None


async def test_data_quality_zero_total_rows_table_skipped():
    """Tables with zero rows are skipped even if get_null_profile says 0 rows."""
    async def mock_get_null_profile(table_name: str) -> dict:
        # All tables have zero rows
        return _null_profile_empty_table(table_name)

    with (
        patch("packages.tools.list_today_exceptions_tool._fetch_all_stockout_risk") as mock_stockout,
        patch("packages.tools.list_today_exceptions_tool._fetch_delayed_orders") as mock_supply,
        patch("packages.tools.list_today_exceptions_tool._fetch_skus_with_recent_anomalies") as mock_demand,
        patch(
            "packages.tools.list_today_exceptions_tool.get_null_profile",
            side_effect=mock_get_null_profile,
        ),
    ):
        mock_stockout.return_value = []
        mock_supply.return_value = []
        mock_demand.return_value = []

        tool = ListTodayExceptionsTool()
        result = await tool.handle({}, make_ctx())

    # No data quality exceptions since all tables are empty
    dq_exceptions = [e for e in result.output["exceptions"] if e["domain"] == "data_quality"]
    assert dq_exceptions == []


# ---------------------------------------------------------------------------
# (8) Exception item schema: required fields always present
# ---------------------------------------------------------------------------


async def test_exception_items_have_required_fields():
    """Every exception item must have domain, severity, headline_metric, detail."""
    stockout_rows = [_stockout_row("SKU-CRIT", on_hand_qty=5.0, avg_daily=10.0)]
    supply_rows = [_supply_order_row("SKU-A", days_overdue=2)]

    with (
        patch("packages.tools.list_today_exceptions_tool._fetch_all_stockout_risk") as mock_stockout,
        patch("packages.tools.list_today_exceptions_tool._fetch_delayed_orders") as mock_supply,
        patch("packages.tools.list_today_exceptions_tool._fetch_skus_with_recent_anomalies") as mock_demand,
        patch("packages.tools.list_today_exceptions_tool._fetch_data_quality_issues") as mock_quality,
    ):
        mock_stockout.return_value = stockout_rows
        mock_supply.return_value = supply_rows
        mock_demand.return_value = []
        mock_quality.return_value = []

        tool = ListTodayExceptionsTool()
        result = await tool.handle({}, make_ctx())

    required_keys = {"domain", "severity", "headline_metric", "detail"}
    for item in result.output["exceptions"]:
        assert required_keys <= item.keys(), f"Missing keys in {item}"


# ---------------------------------------------------------------------------
# (9) Supply delays: severity based on days_overdue (critical >= 7 days, else high)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "days_overdue,expected_severity",
    [
        (1, "high"),
        (6, "high"),
        (7, "critical"),
        (10, "critical"),
    ],
)
async def test_supply_delay_severity_based_on_days_overdue(
    days_overdue: int, expected_severity: str
) -> None:
    """Supply delay severity: critical if >= 7 days overdue, else high."""
    supply_rows = [_supply_order_row("SKU-A", days_overdue=days_overdue)]

    with (
        patch("packages.tools.list_today_exceptions_tool._fetch_all_stockout_risk") as mock_stockout,
        patch("packages.tools.list_today_exceptions_tool._fetch_delayed_orders") as mock_supply,
        patch("packages.tools.list_today_exceptions_tool._fetch_skus_with_recent_anomalies") as mock_demand,
        patch("packages.tools.list_today_exceptions_tool._fetch_data_quality_issues") as mock_quality,
    ):
        mock_stockout.return_value = []
        mock_supply.return_value = supply_rows
        mock_demand.return_value = []
        mock_quality.return_value = []

        tool = ListTodayExceptionsTool()
        result = await tool.handle({}, make_ctx())

    assert len(result.output["exceptions"]) == 1
    assert result.output["exceptions"][0]["severity"] == expected_severity


# ---------------------------------------------------------------------------
# (10) Stockout risk screen: high vs critical severity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "on_hand,avg_daily,expected_severity",
    [
        # critical: projected < 0 (on_hand=5, demand=70 -> ending=-65)
        (5.0, 10.0, "critical"),
        # high: 0 <= ratio < 0.1 (on_hand=100, demand=70 -> ending=30, ratio=0.43 -> medium)
        # To get "high": on_hand=105, avg_daily=10 -> demand=70 (horizon 7) -> ending=35, ratio=0.5 -> "low"
        # Need on_hand such that 0 <= ending < 0.1*demand, demand=70:
        # ending=5, on_hand=75: ratio=0.07 -> "high"
        (75.0, 10.0, "high"),
    ],
)
async def test_stockout_risk_severity_classification(
    on_hand: float, avg_daily: float, expected_severity: str
) -> None:
    """Stockout screen only surfaces high and critical risk levels."""
    stockout_rows = [_stockout_row("SKU-A", on_hand_qty=on_hand, avg_daily=avg_daily)]

    with (
        patch("packages.tools.list_today_exceptions_tool._fetch_all_stockout_risk") as mock_stockout,
        patch("packages.tools.list_today_exceptions_tool._fetch_delayed_orders") as mock_supply,
        patch("packages.tools.list_today_exceptions_tool._fetch_skus_with_recent_anomalies") as mock_demand,
        patch("packages.tools.list_today_exceptions_tool._fetch_data_quality_issues") as mock_quality,
    ):
        mock_stockout.return_value = stockout_rows
        mock_supply.return_value = []
        mock_demand.return_value = []
        mock_quality.return_value = []

        tool = ListTodayExceptionsTool()
        result = await tool.handle({}, make_ctx())

    exceptions = [e for e in result.output["exceptions"] if e["domain"] == "stockout_risk"]
    assert len(exceptions) == 1
    assert exceptions[0]["severity"] == expected_severity


async def test_stockout_risk_medium_and_low_excluded_from_exceptions():
    """Medium and low stockout risk do not appear in the exceptions list."""
    stockout_rows = [
        # medium: on_hand=120, avg_daily=10 -> demand=70, ending=50, ratio=0.71 -> "low"
        # Actually for "medium": ratio=0.3 -> ending=21, on_hand=91
        _stockout_row("SKU-MED", on_hand_qty=91.0, avg_daily=10.0),   # medium
        _stockout_row("SKU-LOW", on_hand_qty=600.0, avg_daily=10.0),  # low
    ]

    with (
        patch("packages.tools.list_today_exceptions_tool._fetch_all_stockout_risk") as mock_stockout,
        patch("packages.tools.list_today_exceptions_tool._fetch_delayed_orders") as mock_supply,
        patch("packages.tools.list_today_exceptions_tool._fetch_skus_with_recent_anomalies") as mock_demand,
        patch("packages.tools.list_today_exceptions_tool._fetch_data_quality_issues") as mock_quality,
    ):
        mock_stockout.return_value = stockout_rows
        mock_supply.return_value = []
        mock_demand.return_value = []
        mock_quality.return_value = []

        tool = ListTodayExceptionsTool()
        result = await tool.handle({}, make_ctx())

    stockout_exceptions = [e for e in result.output["exceptions"] if e["domain"] == "stockout_risk"]
    assert stockout_exceptions == []


# ---------------------------------------------------------------------------
# (11) All-errors shape: every screen fails -> exceptions=[], counts={}, missing_data populated
# ---------------------------------------------------------------------------


async def test_all_screens_fail_returns_valid_contract_with_all_missing():
    """When all four screens raise errors, output still has valid contract shape."""
    with (
        patch(
            "packages.tools.list_today_exceptions_tool._fetch_all_stockout_risk",
            side_effect=RuntimeError("database_url not set"),
        ),
        patch(
            "packages.tools.list_today_exceptions_tool._fetch_delayed_orders",
            side_effect=RuntimeError("database_url not set"),
        ),
        patch(
            "packages.tools.list_today_exceptions_tool._fetch_skus_with_recent_anomalies",
            side_effect=RuntimeError("database_url not set"),
        ),
        patch(
            "packages.tools.list_today_exceptions_tool._fetch_data_quality_issues",
            side_effect=RuntimeError("database_url not set"),
        ),
    ):
        tool = ListTodayExceptionsTool()
        result = await tool.handle({}, make_ctx())

    output = result.output
    assert output["exceptions"] == []
    assert output["counts"] == {}
    assert output["truncated"] is False
    assert len(output["missing_data"]) == 4
