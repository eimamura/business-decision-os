from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.main import app


async def test_status_mock_mode_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOCK_LLM", "true")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/status")
    assert resp.status_code == 200
    assert resp.json()["mock_mode"] is True


async def test_status_mock_mode_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MOCK_LLM", raising=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/status")
    assert resp.status_code == 200
    assert resp.json()["mock_mode"] is False
