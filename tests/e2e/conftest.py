"""E2E test conftest — auto-skip when the API server is not running."""

from __future__ import annotations

import socket

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
