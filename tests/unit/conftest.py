from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _block_network_in_unit_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Block real network calls in the unit test tier.

    Unit tests must use StubClaudeClient or mocks — never real API calls.
    Blocks:
      - anthropic.AsyncAnthropic message creation
      - httpx.AsyncHTTPTransport (real TCP connections; ASGI transport is unaffected)
    """

    def _blocked(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError(
            "unit tests must not make real network calls — use StubClaudeClient or a mock"
        )

    try:
        import anthropic  # noqa: F401

        monkeypatch.setattr(
            "anthropic.resources.messages.messages.AsyncMessages.create",
            _blocked,
        )
    except (ImportError, AttributeError):
        pass

    try:
        import httpx

        monkeypatch.setattr(
            httpx.AsyncHTTPTransport,
            "handle_async_request",
            _blocked,
        )
    except (ImportError, AttributeError):
        pass
