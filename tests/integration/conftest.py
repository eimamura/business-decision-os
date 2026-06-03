from __future__ import annotations

from typing import AsyncGenerator

import pytest


@pytest.fixture(scope="session")
def vcr_config() -> dict:  # type: ignore[type-arg]
    return {
        "cassette_library_dir": "tests/cassettes",
        "record_mode": "none",
        "match_on": ["uri", "method", "body"],
        "filter_headers": ["Authorization", "x-api-key"],
    }


def _api_is_up() -> bool:
    import httpx
    try:
        return httpx.get("http://localhost:8000/health", timeout=1).status_code == 200
    except Exception:
        return False


@pytest.fixture(autouse=True)
async def cleanup_test_sessions() -> AsyncGenerator[list[str], None]:
    """Collect session IDs created during the test; delete them all on teardown."""
    created: list[str] = []
    yield created
    if not _api_is_up():
        return
    import httpx
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        for sid in created:
            try:
                await client.delete(f"/api/v1/sessions/{sid}", timeout=5)
            except Exception:
                pass
