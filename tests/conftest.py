"""Root conftest for Business Decision OS test suite."""
from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest


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
