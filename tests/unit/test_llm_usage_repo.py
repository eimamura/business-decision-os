"""Unit tests for LlmUsageRepository.get_session_totals cache-hit aggregates (T-042)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_pool(fetchrow_return: Any = None) -> MagicMock:
    """Return a mock asyncpg pool whose acquire() yields a connection with mocked fetchrow."""
    mock_conn = MagicMock()
    mock_conn.fetchrow = AsyncMock(return_value=fetchrow_return)

    @asynccontextmanager
    async def _fake_acquire():  # type: ignore[return]
        yield mock_conn

    mock_pool = MagicMock()
    mock_pool.acquire = _fake_acquire
    return mock_pool


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_get_session_totals_cache_hit_rate() -> None:
    """cache_hit_rate = cache_read / (input + cache_read)."""
    from packages.persistence.llm_usage_repo import LlmUsageRepository

    mock_row = {
        "input_tokens": 100,
        "output_tokens": 50,
        "total_cost_usd": 0.001,
        "cache_read_tokens": 100,
        "cache_write_tokens": 20,
    }
    mock_pool = _make_fake_pool(fetchrow_return=mock_row)

    with patch("packages.persistence.llm_usage_repo.get_pool", AsyncMock(return_value=mock_pool)):
        repo = LlmUsageRepository()
        result = await repo.get_session_totals("00000000-0000-0000-0000-000000000001")

    assert result["cache_hit_rate"] == pytest.approx(0.5)
    assert result["cache_read_tokens"] == 100
    assert result["cache_write_tokens"] == 20


async def test_get_session_totals_zero_inputs_no_division_by_zero() -> None:
    """When all token counts are zero, cache_hit_rate must be 0.0 (no ZeroDivisionError)."""
    from packages.persistence.llm_usage_repo import LlmUsageRepository

    mock_row = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_cost_usd": 0.0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
    }
    mock_pool = _make_fake_pool(fetchrow_return=mock_row)

    with patch("packages.persistence.llm_usage_repo.get_pool", AsyncMock(return_value=mock_pool)):
        repo = LlmUsageRepository()
        result = await repo.get_session_totals("00000000-0000-0000-0000-000000000002")

    assert result["cache_hit_rate"] == pytest.approx(0.0)
    assert result["cache_read_tokens"] == 0
    assert result["cache_write_tokens"] == 0


async def test_get_session_totals_returns_zero_row_when_none() -> None:
    """When fetchrow returns None, get_session_totals must return safe zero defaults."""
    from packages.persistence.llm_usage_repo import LlmUsageRepository

    mock_pool = _make_fake_pool(fetchrow_return=None)

    with patch("packages.persistence.llm_usage_repo.get_pool", AsyncMock(return_value=mock_pool)):
        repo = LlmUsageRepository()
        result = await repo.get_session_totals("00000000-0000-0000-0000-000000000003")

    assert result["input_tokens"] == 0
    assert result["output_tokens"] == 0
    assert result["total_cost_usd"] == pytest.approx(0.0)
    assert result["cache_read_tokens"] == 0
    assert result["cache_write_tokens"] == 0
    assert result["cache_hit_rate"] == pytest.approx(0.0)


async def test_get_session_totals_includes_cache_fields_in_response() -> None:
    """get_session_totals must always include cache_read_tokens and cache_write_tokens keys."""
    from packages.persistence.llm_usage_repo import LlmUsageRepository

    mock_row = {
        "input_tokens": 200,
        "output_tokens": 80,
        "total_cost_usd": 0.002,
        "cache_read_tokens": 50,
        "cache_write_tokens": 10,
    }
    mock_pool = _make_fake_pool(fetchrow_return=mock_row)

    with patch("packages.persistence.llm_usage_repo.get_pool", AsyncMock(return_value=mock_pool)):
        repo = LlmUsageRepository()
        result = await repo.get_session_totals("00000000-0000-0000-0000-000000000004")

    assert "cache_read_tokens" in result
    assert "cache_write_tokens" in result
    assert "cache_hit_rate" in result
    # cache_hit_rate = 50 / (200 + 50) = 0.2
    assert result["cache_hit_rate"] == pytest.approx(0.2)
