"""Integration tests for Data Access Tools — require a live PostgreSQL database (Docker).

Run with: docker compose up -d db && uv run pytest tests/unit/test_data_access_tools_integration.py -v
Without Docker these tests will fail with ConnectionRefusedError, which is expected.
"""
from __future__ import annotations

import os
from uuid import uuid4

import pytest

_needs_db = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"), reason="requires DATABASE_URL"
)

from packages.tools.base import ToolContext
from packages.tools.data_catalog_search_tool import DataCatalogSearchTool
from packages.tools.data_quality_checker_tool import DataQualityCheckerTool
from packages.tools.sql_allowlist import ALLOWED_READ_TABLES
from packages.tools.table_schema_reader_tool import TableSchemaReaderTool


def _ctx() -> ToolContext:
    return ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="data_engineer",
        actor="test",
        correlation_id=uuid4(),
    )


@pytest.fixture(autouse=True)
async def reset_db_pool():
    """Reset the global asyncpg pool before and after each test.

    pytest-asyncio creates a new event loop per test function. The global pool
    singleton in packages/persistence/db.py is bound to the event loop in which
    it was created, so it becomes invalid across tests. Resetting it forces
    recreation in the current loop.
    """
    import packages.persistence.db as db_module
    db_module._pool = None
    yield
    if db_module._pool is not None:
        await db_module._pool.close()
        db_module._pool = None


# ===== DataCatalogSearchTool =====

@_needs_db
async def test_data_catalog_search_returns_row_counts():
    tool = DataCatalogSearchTool()
    result = await tool.handle({}, _ctx())
    assert result.output["count"] == len(ALLOWED_READ_TABLES)
    for row in result.output["tables"]:
        assert row["row_count"] is not None
        assert row["row_count"] >= 0


# ===== TableSchemaReaderTool =====

@_needs_db
async def test_table_schema_reader_sku_master_schema():
    tool = TableSchemaReaderTool()
    result = await tool.handle({"table_name": "sku_master"}, _ctx())
    assert "error" not in result.output
    assert result.output["column_count"] > 0
    column_names = {c["column_name"] for c in result.output["columns"]}
    assert {"sku_id", "name", "category"} <= column_names
    for col in result.output["columns"]:
        assert "data_type" in col
        assert isinstance(col["is_nullable"], bool)


# ===== DataQualityCheckerTool =====

@_needs_db
async def test_data_quality_checker_dynamic_sql_executes():
    tool = DataQualityCheckerTool()
    result = await tool.handle({"table_name": "inventory_snapshot"}, _ctx())
    assert "error" not in result.output
    assert "note" not in result.output  # real DB path, not the no-DB fallback
    assert isinstance(result.output["total_rows"], int)
    assert len(result.output["columns"]) > 0  # columns fetched from information_schema
    for col in result.output["columns"]:
        assert "null_count" in col
        assert "null_pct" in col
    assert isinstance(result.output["has_issues"], bool)


@pytest.mark.parametrize("table_name", sorted(ALLOWED_READ_TABLES))
async def test_data_quality_checker_all_tables_execute(table_name: str):
    tool = DataQualityCheckerTool()
    result = await tool.handle({"table_name": table_name}, _ctx())
    assert "error" not in result.output
    assert result.output["total_rows"] >= 0
