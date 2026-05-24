from __future__ import annotations

from typing import Any

import httpx
import pytest
from httpx import ASGITransport

import apps.api.routers.admin as admin_router
from apps.api.main import app


@pytest.fixture
async def client():
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


class FakeAcquire:
    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None


class FakePool:
    def acquire(self) -> FakeAcquire:
        return FakeAcquire()


async def test_generate_sample_data_defaults_return_table_summaries(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    def fake_generate(config: object) -> None:
        captured["config"] = config

    async def fake_get_pool() -> FakePool:
        return FakePool()

    async def fake_replace_operational_tables(conn: object) -> list[dict[str, Any]]:
        return [
            {"table_name": name, "row_count": idx, "top_rows": [{"id": idx}]}
            for idx, name in enumerate(
                ["sku_master", "customers", "inventory", "demand_history", "supply", "cost"],
                start=1,
            )
        ]

    monkeypatch.setattr(admin_router, "generate", fake_generate)
    monkeypatch.setattr(admin_router, "get_pool", fake_get_pool)
    monkeypatch.setattr(admin_router, "replace_operational_tables", fake_replace_operational_tables)

    response = await client.post("/api/v1/admin/sample-data/generate", json={})

    assert response.status_code == 200
    body = response.json()
    assert len(body["tables"]) == 6
    assert body["tables"][0] == {
        "table_name": "sku_master",
        "row_count": 1,
        "top_rows": [{"id": 1}],
    }
    assert captured["config"].seed == 42
    assert captured["config"].sku_count == 30
    assert captured["config"].horizon_days == 365
    assert captured["config"].warehouse_count == 2
    assert captured["config"].missing_rate == 0.02


@pytest.mark.parametrize(
    "payload",
    [
        {"sku_count": 0},
        {"sku_count": 31},
        {"horizon_days": 0},
        {"horizon_days": 1096},
        {"warehouse_count": 0},
        {"warehouse_count": 11},
        {"missing_rate": -0.01},
        {"missing_rate": 0.26},
    ],
)
async def test_generate_sample_data_invalid_params_return_422(
    client: httpx.AsyncClient, payload: dict[str, object]
) -> None:
    response = await client.post("/api/v1/admin/sample-data/generate", json=payload)

    assert response.status_code == 422


async def test_generate_sample_data_without_database_url_returns_500(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_generate(config: object) -> None:
        return None

    async def fake_get_pool() -> FakePool:
        raise RuntimeError("DATABASE_URL not set")

    monkeypatch.setattr(admin_router, "generate", fake_generate)
    monkeypatch.setattr(admin_router, "get_pool", fake_get_pool)

    response = await client.post("/api/v1/admin/sample-data/generate", json={})

    assert response.status_code == 500
    assert response.json()["detail"] == "DATABASE_URL not set"
