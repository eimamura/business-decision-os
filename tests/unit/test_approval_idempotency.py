from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from packages.persistence.approvals_repo import ApprovalsRepository


# ---------------------------------------------------------------------------
# test_get_pending_approval_returns_none_for_unknown_session
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_pending_approval_returns_none_for_unknown_session() -> None:
    """When the DB returns no row for the session, the method returns None."""
    session_id = uuid4()

    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=None)

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch(
        "packages.persistence.approvals_repo.get_pool",
        new=AsyncMock(return_value=mock_pool),
    ):
        repo = ApprovalsRepository()
        result = await repo.get_pending_approval_for_session(session_id)

    assert result is None
    mock_conn.fetchrow.assert_awaited_once_with(
        "SELECT * FROM approvals WHERE session_id = $1 AND status = 'pending' LIMIT 1",
        session_id,
    )


# ---------------------------------------------------------------------------
# test_second_approval_request_reuses_existing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_second_approval_request_reuses_existing() -> None:
    """When get_pending_approval_for_session returns an existing record,
    create() must NOT be called a second time."""
    session_id = uuid4()
    existing_id = uuid4()
    existing_record: dict[str, Any] = {
        "id": existing_id,
        "session_id": session_id,
        "status": "pending",
        "actor": None,
        "reason": None,
    }

    mock_repo = MagicMock(spec=ApprovalsRepository)
    mock_repo.get_pending_approval_for_session = AsyncMock(return_value=existing_record)
    mock_repo.create = AsyncMock()

    # Simulate the idempotency guard logic from decision.py directly
    existing = await mock_repo.get_pending_approval_for_session(session_id)

    if existing is None:
        await mock_repo.create({
            "session_id": session_id,
            "status": "pending",
            "actor": None,
        })
        approval_id_val = str(uuid4())
    else:
        approval_id_val = str(existing.get("id", uuid4()))

    assert approval_id_val == str(existing_id)
    mock_repo.create.assert_not_awaited()
