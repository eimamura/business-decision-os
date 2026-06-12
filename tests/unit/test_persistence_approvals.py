"""Unit tests for B03: repository stubs, audit hash chain, sql allowlist."""

from __future__ import annotations

import hashlib
import json

import pytest

from packages.persistence import (
    ApprovalsRepository,
    AuditLogRepository,
    DecisionSessionRepository,
    LlmUsageRepository,
    RecommendationsRepository,
    ToolCallsRepository,
)
from packages.persistence.audit_log_repo import compute_hash
from packages.tools.sql_allowlist import ALLOWED_READ_TABLES, check_allowed

# ---------------------------------------------------------------------------
# compute_hash
# ---------------------------------------------------------------------------

def test_compute_hash_deterministic():
    payload = {"event": "tool_called", "tool": "sql"}
    h1 = compute_hash(payload, None)
    h2 = compute_hash(payload, None)
    assert h1 == h2


def test_compute_hash_is_sha256_hex():
    payload = {"x": 1}
    result = compute_hash(payload, None)
    assert len(result) == 64
    int(result, 16)


def test_compute_hash_prev_none_uses_empty_string():
    payload = {"a": "b"}
    expected_input = json.dumps({"payload": payload, "prev_hash": ""}, sort_keys=True)
    expected = hashlib.sha256(expected_input.encode()).hexdigest()
    assert compute_hash(payload, None) == expected


def test_compute_hash_changes_with_prev_hash():
    payload = {"x": 1}
    h_none = compute_hash(payload, None)
    h_prev = compute_hash(payload, "abc123")
    assert h_none != h_prev


def test_compute_hash_changes_with_payload():
    h1 = compute_hash({"a": 1}, None)
    h2 = compute_hash({"a": 2}, None)
    assert h1 != h2


# ---------------------------------------------------------------------------
# Repository stubs — all methods raise NotImplementedError
# ---------------------------------------------------------------------------

async def test_sessions_repo_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    import packages.persistence.db as _db
    monkeypatch.delenv("DATABASE_URL", raising=False)
    _db._pool = None  # reset stale pool so get_pool re-checks env
    repo = DecisionSessionRepository()
    with pytest.raises(RuntimeError, match="DATABASE_URL not set"):
        await repo.get(str(__import__("uuid").uuid4()))


async def test_audit_log_repo_raises():
    repo = AuditLogRepository()
    with pytest.raises(NotImplementedError):
        await repo.get(__import__("uuid").uuid4())


async def test_audit_log_hash_chain_write_raises():
    repo = AuditLogRepository()
    with pytest.raises(NotImplementedError):
        await repo.hash_chain_write(
            session_id=None,
            agent_step_id=None,
            tool_call_id=None,
            event_type="test",
            payload={"x": 1},
            actor="dev",
        )


async def test_approvals_repo_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    import packages.persistence.db as _db
    monkeypatch.delenv("DATABASE_URL", raising=False)
    _db._pool = None
    repo = ApprovalsRepository()
    with pytest.raises(RuntimeError, match="DATABASE_URL not set"):
        await repo.get(__import__("uuid").uuid4())


async def test_recommendations_repo_raises():
    repo = RecommendationsRepository()
    with pytest.raises(NotImplementedError):
        await repo.get(__import__("uuid").uuid4())


async def test_llm_usage_repo_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    import packages.persistence.db as _db
    monkeypatch.delenv("DATABASE_URL", raising=False)
    _db._pool = None
    repo = LlmUsageRepository()
    with pytest.raises(RuntimeError, match="DATABASE_URL not set"):
        await repo.get_session_totals(str(__import__("uuid").uuid4()))


async def test_tool_calls_repo_raises():
    repo = ToolCallsRepository()
    with pytest.raises(NotImplementedError):
        await repo.get(__import__("uuid").uuid4())


# ---------------------------------------------------------------------------
# SQL allowlist
# ---------------------------------------------------------------------------

def test_allowed_tables_are_exactly_ten():
    # P87 added customer_orders and shipments; total is now 10.
    assert len(ALLOWED_READ_TABLES) == 10


@pytest.mark.parametrize("table", [
    "sku_master", "location_master", "customer_master",
    "inventory_snapshot", "demand_history", "supply_orders", "cost_master", "forecast_history",
    "customer_orders", "shipments",
])
def test_allowed_tables_pass(table: str):
    assert check_allowed(table) is True


@pytest.mark.parametrize("table", [
    "users", "audit_log", "memories", "llm_usage", "approvals", "recommendations",
    "decision_sessions", "agent_steps", "tool_calls",
])
def test_non_allowed_tables_fail(table: str):
    assert check_allowed(table) is False


def test_check_allowed_is_case_insensitive():
    assert check_allowed("SKU_MASTER") is True
    assert check_allowed("Inventory_Snapshot") is True
