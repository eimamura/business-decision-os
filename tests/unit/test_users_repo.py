from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.persistence.users_repo import UserRepository


async def _mock_pool_with_row(row: dict | None) -> MagicMock:
    """Return a mock asyncpg pool whose ``acquire()`` context yields a connection
    that returns *row* from ``fetchrow``."""
    conn = AsyncMock()
    if row is not None:
        conn.fetchrow.return_value = MagicMock(**{"__getitem__": lambda self, k: row[k]})
    else:
        conn.fetchrow.return_value = None

    pool = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    return pool


@pytest.mark.asyncio
async def test_get_role_known_user_returns_correct_role() -> None:
    pool = await _mock_pool_with_row({"role": "manager"})
    with patch("packages.persistence.users_repo.get_pool", AsyncMock(return_value=pool)):
        repo = UserRepository()
        role = await repo.get_role("user-123")
    assert role == "manager"


@pytest.mark.asyncio
async def test_get_role_unknown_user_returns_analyst() -> None:
    pool = await _mock_pool_with_row(None)
    with patch("packages.persistence.users_repo.get_pool", AsyncMock(return_value=pool)):
        repo = UserRepository()
        role = await repo.get_role("nonexistent-user")
    assert role == "analyst"
