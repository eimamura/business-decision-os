from __future__ import annotations

import os

import pytest

# The unit tier is an explicit test environment for APP_ENV purposes. This must
# run at conftest import time — before any test module imports apps.api.main —
# because operational routes (/api/v1/debug, /api/v1/admin/*) are registered
# only in explicit dev/test environments.
# ADR: docs/adr/2026-08-24-local-only-operational-routes.md
os.environ.setdefault("APP_ENV", "test")


@pytest.fixture(autouse=True)
def _block_network_in_unit_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Block real network calls in the unit test tier.

    Unit tests must use StubClaudeClient or mocks — never real API calls.
    Blocks:
      - anthropic.AsyncAnthropic message creation
      - httpx.AsyncHTTPTransport (real TCP connections; ASGI transport is unaffected)
      - LangGraph AsyncPostgresSaver (forces MemorySaver; prevents pool-exhaustion across tests)
    """
    # Default to Ollama so tests don't accidentally hit the Anthropic API.
    # Tests that explicitly exercise the anthropic code path must delenv LLM_PROVIDER.
    monkeypatch.setenv("LLM_PROVIDER", "ollama")

    # Force LangGraph to use MemorySaver in all unit tests by suppressing DATABASE_URL.
    # Without this, _get_graph() creates an AsyncConnectionPool per test; running hundreds
    # of tests exhausts the postgres connection limit and causes intermittent failures.
    monkeypatch.delenv("DATABASE_URL", raising=False)

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
