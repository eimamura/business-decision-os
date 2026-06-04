from __future__ import annotations

import pytest

from packages.persistence.session_events_repo import SessionEventRepository


async def test_create_raises_without_db(monkeypatch: pytest.MonkeyPatch) -> None:
    import packages.persistence.db as _db
    monkeypatch.delenv("DATABASE_URL", raising=False)
    _db._pool = None
    repo = SessionEventRepository()
    with pytest.raises(RuntimeError, match="DATABASE_URL not set"):
        await repo.create(
            session_id="00000000-0000-0000-0000-000000000001",
            event_type="query_received",
            payload={"type": "query_received"},
        )


async def test_list_for_session_raises_without_db(monkeypatch: pytest.MonkeyPatch) -> None:
    import packages.persistence.db as _db
    monkeypatch.delenv("DATABASE_URL", raising=False)
    _db._pool = None
    repo = SessionEventRepository()
    with pytest.raises(RuntimeError, match="DATABASE_URL not set"):
        await repo.list_for_session("00000000-0000-0000-0000-000000000001")
