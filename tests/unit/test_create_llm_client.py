"""Unit tests for the TEST_MODEL env var override in create_llm_client (T-041)."""
from __future__ import annotations

import pytest


def test_create_llm_client_respects_test_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
    monkeypatch.setenv("TEST_MODEL", "claude-haiku-4-5-20251001")
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("MOCK_LLM", raising=False)
    # Re-import to pick up the monkeypatched env vars.
    from packages.agent.llm import create_llm_client

    client = create_llm_client()
    assert client._model == "claude-haiku-4-5-20251001"


def test_create_llm_client_uses_default_model_when_test_model_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
    monkeypatch.delenv("TEST_MODEL", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("MOCK_LLM", raising=False)
    from packages.agent.llm import ClaudeClient, create_llm_client

    client = create_llm_client()
    assert client._model == ClaudeClient.DEFAULT_MODEL
