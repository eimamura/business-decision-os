"""Tests that the zero-network autouse fixture is active in the unit tier (T-043)."""
from __future__ import annotations

import pytest


async def test_anthropic_messages_blocked() -> None:
    """Calling anthropic messages.create raises AssertionError in unit tier."""
    try:
        import anthropic
    except ImportError:
        pytest.skip("anthropic not installed")

    client = anthropic.AsyncAnthropic(api_key="sk-test")
    with pytest.raises(
        AssertionError,
        match="unit tests must not make real network calls",
    ):
        await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=10,
            messages=[{"role": "user", "content": "hi"}],
        )


async def test_httpx_real_transport_blocked() -> None:
    """Direct httpx.AsyncHTTPTransport requests raise AssertionError in unit tier."""
    try:
        import httpx
    except ImportError:
        pytest.skip("httpx not installed")

    transport = httpx.AsyncHTTPTransport()
    request = httpx.Request("GET", "https://example.com")
    with pytest.raises(AssertionError, match="unit tests must not make real network calls"):
        await transport.handle_async_request(request)
