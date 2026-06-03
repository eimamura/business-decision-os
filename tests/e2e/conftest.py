"""E2E test conftest — auto-skip when the API server is not running."""

from __future__ import annotations

import socket
from typing import Generator

import pytest


def _api_is_up() -> bool:
    try:
        with socket.create_connection(("localhost", 8000), timeout=1):
            return True
    except OSError:
        return False


def pytest_collection_modifyitems(items: list) -> None:
    if _api_is_up():
        return
    skip = pytest.mark.skip(reason="API server not running on localhost:8000")
    for item in items:
        if "e2e" in item.nodeid:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def cleanup_test_sessions() -> Generator[list[str], None, None]:
    """Collect session IDs created during the test; delete them all on teardown."""
    created: list[str] = []
    yield created
    if not _api_is_up():
        return
    import httpx
    for sid in created:
        try:
            httpx.delete(f"http://localhost:8000/api/v1/sessions/{sid}", timeout=5)
        except Exception:
            pass
