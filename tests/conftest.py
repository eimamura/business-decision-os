"""Root conftest for Business Decision OS test suite."""
from __future__ import annotations

import os
import socket
from collections.abc import AsyncGenerator

import pytest

# Mirrors the Makefile default (`API_PORT ?= 8002`); override via env when the
# API is served elsewhere (D-024: the e2e probe must never hardcode a literal).
DEFAULT_API_PORT = 8002


def configured_api_port() -> int:
    """API port the e2e tier should talk to.

    Reads API_PORT (the Make-owned configuration variable). An invalid value is
    a configuration error and fails loudly instead of probing a wrong port.
    """
    raw = os.environ.get("API_PORT", "").strip()
    if not raw:
        return DEFAULT_API_PORT
    try:
        return int(raw)
    except ValueError as exc:
        raise pytest.UsageError(
            f"API_PORT={raw!r} is not a valid integer port "
            "(set it to the port the API is served on, e.g. 8002)"
        ) from exc


def api_base_url() -> str:
    """Base URL of the API server under test."""
    return f"http://localhost:{configured_api_port()}"


API_BASE_URL = api_base_url()


def _api_is_up() -> bool:
    try:
        with socket.create_connection(("localhost", configured_api_port()), timeout=1):
            return True
    except OSError:
        return False


def pytest_collection_modifyitems(items: list) -> None:
    """Auto-skip @pytest.mark.e2e tests when no API is reachable at api_base_url().

    tests/e2e/conftest.py tightens this for dedicated e2e sessions: a run whose
    entire scope is the e2e tier fails loudly instead of silently skipping.
    """
    if _api_is_up():
        return
    skip = pytest.mark.skip(
        reason=f"API server not running on {api_base_url()} "
        f"(configure with API_PORT; default {DEFAULT_API_PORT})"
    )
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
