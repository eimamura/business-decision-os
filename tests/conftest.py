"""Root conftest for Business Decision OS test suite."""
from __future__ import annotations

import socket
from collections.abc import AsyncGenerator

import pytest


def _api_is_up() -> bool:
    try:
        with socket.create_connection(("localhost", 8000), timeout=1):
            return True
    except OSError:
        return False


def pytest_collection_modifyitems(items: list) -> None:
    """Auto-skip @pytest.mark.e2e tests when localhost:8000 is not reachable."""
    if _api_is_up():
        return
    skip = pytest.mark.skip(reason="API server not running on localhost:8000")
    for item in items:
        if "e2e" in item.nodeid or item.get_closest_marker("e2e") is not None:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
async def reset_db_pool_global() -> AsyncGenerator[None, None]:
    """Reset the global asyncpg pool before and after each test.

    The ASGI app's lifespan (load_schema_context) creates a DB pool when
    DATABASE_URL is set. If the pool is bound to a previous test's event loop,
    any attempt to use it in the next test hangs indefinitely. Resetting _pool
    to None before each test forces recreation in the current loop.
    """
    import packages.persistence.db as db_module

    db_module._pool = None
    yield
    if db_module._pool is not None:
        try:
            await db_module._pool.close()
        except Exception:
            pass
        db_module._pool = None
