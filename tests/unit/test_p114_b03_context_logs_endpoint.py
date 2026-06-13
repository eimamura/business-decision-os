from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from httpx import ASGITransport

import apps.api.routers.admin as admin_router
from apps.api.main import app
from packages.schemas.context_packs import ContextLogRead


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def client() -> httpx.AsyncClient:
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


def _make_context_log_read(
    session_id: uuid.UUID | None = None,
    use_case_id: str = "Q1",
) -> ContextLogRead:
    return ContextLogRead(
        id=uuid.uuid4(),
        session_id=session_id or uuid.uuid4(),
        use_case_id=use_case_id,
        intent="supply_chain",
        required_tools=["list_stockout_risk"],
        prohibited_tools=["list_today_exceptions"],
        context_pack_json={"use_case_id": use_case_id, "routing_hint": "hint"},
        created_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )


def _make_fake_pool(repo_mock: Any) -> Any:
    """Return a fake pool whose acquire() context manager yields a fake conn."""
    fake_conn = object()

    class FakeAcquire:
        async def __aenter__(self) -> object:
            return fake_conn

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

    class FakePool:
        def acquire(self) -> FakeAcquire:
            return FakeAcquire()

    return FakePool()


# ---------------------------------------------------------------------------
# list_recent path (no filters)
# ---------------------------------------------------------------------------


async def test_context_logs_no_filter_calls_list_recent(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log = _make_context_log_read()
    repo_instance = MagicMock()
    repo_instance.list_recent = AsyncMock(return_value=[log])

    fake_pool = _make_fake_pool(repo_instance)

    monkeypatch.setattr(admin_router, "get_pool", AsyncMock(return_value=fake_pool))

    import packages.persistence.context_log as context_log_mod

    monkeypatch.setattr(
        context_log_mod, "ContextLogRepository", lambda: repo_instance
    )

    response = await client.get("/api/v1/admin/context-logs")

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 1
    assert body[0]["use_case_id"] == "Q1"


# ---------------------------------------------------------------------------
# list_by_session path
# ---------------------------------------------------------------------------


async def test_context_logs_with_session_id_calls_list_by_session(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sid = uuid.uuid4()
    log = _make_context_log_read(session_id=sid)
    repo_instance = MagicMock()
    repo_instance.list_by_session = AsyncMock(return_value=[log])

    fake_pool = _make_fake_pool(repo_instance)

    monkeypatch.setattr(admin_router, "get_pool", AsyncMock(return_value=fake_pool))

    import packages.persistence.context_log as context_log_mod

    monkeypatch.setattr(
        context_log_mod, "ContextLogRepository", lambda: repo_instance
    )

    response = await client.get(f"/api/v1/admin/context-logs?session_id={sid}")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["session_id"] == str(sid)


# ---------------------------------------------------------------------------
# list_by_use_case path
# ---------------------------------------------------------------------------


async def test_context_logs_with_use_case_id_calls_list_by_use_case(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log = _make_context_log_read(use_case_id="Q3")
    repo_instance = MagicMock()
    repo_instance.list_by_use_case = AsyncMock(return_value=[log])

    fake_pool = _make_fake_pool(repo_instance)

    monkeypatch.setattr(admin_router, "get_pool", AsyncMock(return_value=fake_pool))

    import packages.persistence.context_log as context_log_mod

    monkeypatch.setattr(
        context_log_mod, "ContextLogRepository", lambda: repo_instance
    )

    response = await client.get("/api/v1/admin/context-logs?use_case_id=Q3")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["use_case_id"] == "Q3"


# ---------------------------------------------------------------------------
# limit enforcement (le=200)
# ---------------------------------------------------------------------------


async def test_context_logs_limit_exceeding_max_returns_422(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/api/v1/admin/context-logs?limit=201")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Empty result when DATABASE_URL absent
# ---------------------------------------------------------------------------


async def test_context_logs_no_database_url_returns_empty_list(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get_pool() -> None:
        raise RuntimeError("DATABASE_URL not set")

    monkeypatch.setattr(admin_router, "get_pool", fake_get_pool)

    response = await client.get("/api/v1/admin/context-logs")

    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# Response shape — all required ContextLogRead fields present
# ---------------------------------------------------------------------------


async def test_context_logs_response_contains_all_required_fields(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log = _make_context_log_read()
    repo_instance = MagicMock()
    repo_instance.list_recent = AsyncMock(return_value=[log])

    fake_pool = _make_fake_pool(repo_instance)

    monkeypatch.setattr(admin_router, "get_pool", AsyncMock(return_value=fake_pool))

    import packages.persistence.context_log as context_log_mod

    monkeypatch.setattr(
        context_log_mod, "ContextLogRepository", lambda: repo_instance
    )

    response = await client.get("/api/v1/admin/context-logs")

    assert response.status_code == 200
    item = response.json()[0]
    for field in (
        "id",
        "session_id",
        "use_case_id",
        "intent",
        "required_tools",
        "prohibited_tools",
        "context_pack_json",
        "created_at",
    ):
        assert field in item, f"Missing field: {field}"
