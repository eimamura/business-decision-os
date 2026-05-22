from __future__ import annotations

import pytest

from packages.persistence.session_events_repo import SessionEventRepository


@pytest.mark.asyncio
async def test_create_raises_without_db() -> None:
    repo = SessionEventRepository()
    with pytest.raises((RuntimeError, Exception)):
        await repo.create(
            session_id="00000000-0000-0000-0000-000000000001",
            event_type="query_received",
            payload={"type": "query_received"},
        )


@pytest.mark.asyncio
async def test_list_for_session_raises_without_db() -> None:
    repo = SessionEventRepository()
    with pytest.raises((RuntimeError, Exception)):
        await repo.list_for_session("00000000-0000-0000-0000-000000000001")
