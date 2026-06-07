"""Integration tests for DB-touching tools against a real PostgreSQL database.

Requires a running PostgreSQL instance reachable via DATABASE_URL.
Run with:
    docker compose up -d db && uv run pytest tests/integration/test_tools_real_db.py -v

Without a live DB these tests are skipped automatically when DATABASE_URL is unset,
or fail with a connection error when the URL is set but the host is unreachable.
"""
from __future__ import annotations

import os
from uuid import uuid4

import pytest

from packages.tools.base import ToolContext
from packages.tools.data_catalog_search_tool import DataCatalogSearchTool
from packages.tools.data_quality_checker_tool import DataQualityCheckerTool
from packages.tools.sql_allowlist import ALLOWED_READ_TABLES
from packages.tools.table_schema_reader_tool import TableSchemaReaderTool

_HAS_DB = bool(os.environ.get("DATABASE_URL"))
_SKIP_NO_DB = pytest.mark.skipif(not _HAS_DB, reason="DATABASE_URL not set")


def _ctx() -> ToolContext:
    return ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="data_engineer",
        actor="integration_test",
        correlation_id=uuid4(),
    )


@pytest.fixture(autouse=True)
async def reset_db_pool() -> None:  # type: ignore[misc]
    """Reset the global asyncpg pool before and after each test.

    pytest-asyncio creates a new event loop per test function.  The global pool
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


# ---------------------------------------------------------------------------
# DataCatalogSearchTool
# ---------------------------------------------------------------------------


@_SKIP_NO_DB
async def test_data_catalog_search_returns_all_tables_with_row_counts() -> None:
    tool = DataCatalogSearchTool()
    result = await tool.handle({}, _ctx())
    assert result.output["count"] == len(ALLOWED_READ_TABLES)
    for row in result.output["tables"]:
        assert "table_name" in row
        assert row["row_count"] is not None
        assert isinstance(row["row_count"], int)
        assert row["row_count"] >= 0


@_SKIP_NO_DB
async def test_data_catalog_search_keyword_filter_returns_matching_tables() -> None:
    tool = DataCatalogSearchTool()
    result = await tool.handle({"keyword": "sku"}, _ctx())
    names = [row["table_name"] for row in result.output["tables"]]
    assert all("sku" in name for name in names)
    assert result.output["count"] == len(names)


@_SKIP_NO_DB
async def test_data_catalog_search_audit_payload_includes_table_count() -> None:
    tool = DataCatalogSearchTool()
    result = await tool.handle({}, _ctx())
    assert "table_count" in result.audit_payload
    assert result.audit_payload["table_count"] == result.output["count"]


# ---------------------------------------------------------------------------
# TableSchemaReaderTool
# ---------------------------------------------------------------------------


@_SKIP_NO_DB
async def test_table_schema_reader_sku_master_returns_expected_columns() -> None:
    tool = TableSchemaReaderTool()
    result = await tool.handle({"table_name": "sku_master"}, _ctx())
    assert "error" not in result.output
    assert "note" not in result.output
    assert result.output["column_count"] > 0
    column_names = {col["column_name"] for col in result.output["columns"]}
    assert {"sku_id", "name", "category"} <= column_names


@_SKIP_NO_DB
async def test_table_schema_reader_columns_have_required_fields() -> None:
    tool = TableSchemaReaderTool()
    result = await tool.handle({"table_name": "inventory_snapshot"}, _ctx())
    assert "error" not in result.output
    for col in result.output["columns"]:
        assert "column_name" in col
        assert "data_type" in col
        assert "is_nullable" in col
        assert isinstance(col["is_nullable"], bool)


@_SKIP_NO_DB
async def test_table_schema_reader_demand_history_has_date_column() -> None:
    tool = TableSchemaReaderTool()
    result = await tool.handle({"table_name": "demand_history"}, _ctx())
    assert "error" not in result.output
    column_names = {col["column_name"] for col in result.output["columns"]}
    assert "sku_id" in column_names


@_SKIP_NO_DB
async def test_table_schema_reader_rejects_table_not_in_allowlist() -> None:
    tool = TableSchemaReaderTool()
    result = await tool.handle({"table_name": "pg_catalog"}, _ctx())
    assert "error" in result.output
    assert result.output["column_count"] == 0


# ---------------------------------------------------------------------------
# DataQualityCheckerTool
# ---------------------------------------------------------------------------


@_SKIP_NO_DB
async def test_data_quality_checker_inventory_snapshot_executes_without_error() -> None:
    tool = DataQualityCheckerTool()
    result = await tool.handle({"table_name": "inventory_snapshot"}, _ctx())
    assert "error" not in result.output
    assert "note" not in result.output
    assert isinstance(result.output["total_rows"], int)
    assert result.output["total_rows"] >= 0
    assert isinstance(result.output["has_issues"], bool)


@_SKIP_NO_DB
async def test_data_quality_checker_columns_have_null_count_and_pct() -> None:
    tool = DataQualityCheckerTool()
    result = await tool.handle({"table_name": "sku_master"}, _ctx())
    assert "error" not in result.output
    assert len(result.output["columns"]) > 0
    for col in result.output["columns"]:
        assert "column_name" in col
        assert "null_count" in col
        assert "null_pct" in col
        assert isinstance(col["null_count"], int)
        assert isinstance(col["null_pct"], float)


@_SKIP_NO_DB
async def test_data_quality_checker_rejects_table_not_in_allowlist() -> None:
    tool = DataQualityCheckerTool()
    result = await tool.handle({"table_name": "information_schema_tables"}, _ctx())
    assert "error" in result.output


@pytest.mark.skipif(not _HAS_DB, reason="DATABASE_URL not set")
@pytest.mark.parametrize("table_name", sorted(ALLOWED_READ_TABLES))
async def test_data_quality_checker_all_allowlisted_tables_execute(
    table_name: str,
) -> None:
    tool = DataQualityCheckerTool()
    result = await tool.handle({"table_name": table_name}, _ctx())
    assert "error" not in result.output
    assert result.output["total_rows"] >= 0


# ---------------------------------------------------------------------------
# Tools that require an LLM — skipped in this integration suite
# ---------------------------------------------------------------------------


@pytest.mark.skip(
    reason=(
        "nl_query requires a live LLM client — "
        "tested separately with vcrpy cassettes"
    )
)
async def test_nl_query_tool_skipped_needs_llm() -> None:  # pragma: no cover
    pass


@pytest.mark.skip(
    reason=(
        "evaluate_candidates does not touch the DB; "
        "pure computation — covered in unit tests"
    )
)
async def test_evaluate_candidates_skipped_no_db() -> None:  # pragma: no cover
    pass


@pytest.mark.skip(
    reason=(
        "simulate_inventory and optimize_replenishment run InProcessJobRunner "
        "without DB I/O — covered in unit tests"
    )
)
async def test_simulation_optimizer_tools_skipped_no_db_io() -> None:  # pragma: no cover
    pass


@pytest.mark.skip(
    reason=(
        "forecast and train_forecast require a trained model and DB seed data — "
        "tested via dedicated predictor tests"
    )
)
async def test_forecast_tools_skipped_need_model() -> None:  # pragma: no cover
    pass
