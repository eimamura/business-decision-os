from __future__ import annotations

import os
from unittest.mock import patch

import pytest


def test_create_model_registry_anthropic_returns_chat_anthropic():
    env = {
        "LLM_PROVIDER": "anthropic",
        "ANTHROPIC_API_KEY": "sk-test-key",
        "ANTHROPIC_MODEL": "claude-sonnet-4-6",
    }
    with patch.dict(os.environ, env, clear=False):
        from langchain_anthropic import ChatAnthropic

        from packages.agent.model_registry import create_model_registry

        registry = create_model_registry()
        model = registry.get("orchestrator")
        assert isinstance(model, ChatAnthropic)


def test_create_model_registry_ollama_returns_chat_ollama():
    env = {
        "LLM_PROVIDER": "ollama",
        "OLLAMA_BASE_URL": "http://localhost:11434",
        "OLLAMA_MODEL": "qwen2.5:7b",
    }
    with patch.dict(os.environ, env, clear=False):
        from langchain_ollama import ChatOllama

        from packages.agent.model_registry import create_model_registry

        registry = create_model_registry()
        model = registry.get("orchestrator")
        assert isinstance(model, ChatOllama)


def test_create_model_registry_ollama_orchestrator_has_num_predict():
    env = {
        "LLM_PROVIDER": "ollama",
        "OLLAMA_BASE_URL": "http://localhost:11434",
        "OLLAMA_MODEL": "qwen2.5:7b",
    }
    with patch.dict(os.environ, env, clear=False):
        from packages.agent.model_registry import create_model_registry

        registry = create_model_registry()
        model = registry.get("orchestrator")
        assert model.num_predict == 512  # type: ignore[union-attr]


@pytest.mark.parametrize("role", ["orchestrator", "planner", "control"])
def test_create_model_registry_ollama_all_roles_have_num_ctx_16384(role: str):
    """T-567c: Both orchestrator/planner (structured) and control models must have
    num_ctx == 16384 (_OLLAMA_NUM_CTX). This is the P92 fix to prevent silent prompt
    truncation when the control prompt exceeds the default 4096-token context window."""
    env = {
        "LLM_PROVIDER": "ollama",
        "OLLAMA_BASE_URL": "http://localhost:11434",
        "OLLAMA_MODEL": "gemma4:12b",
    }
    with patch.dict(os.environ, env, clear=False):
        from packages.agent.model_registry import _OLLAMA_NUM_CTX, create_model_registry

        registry = create_model_registry()
        model = registry.get(role)
        # Verify the model carries the expected num_ctx value.
        # Zero-network: ChatOllama construction makes no HTTP calls.
        assert model.num_ctx == _OLLAMA_NUM_CTX, (  # type: ignore[union-attr]
            f"Role '{role}' model num_ctx={model.num_ctx!r} != {_OLLAMA_NUM_CTX!r} "  # type: ignore[union-attr]
            "(P92 fix: context window must be 16384 to avoid silent prompt truncation)"
        )
        assert _OLLAMA_NUM_CTX == 16384, (
            f"_OLLAMA_NUM_CTX must be 16384, got {_OLLAMA_NUM_CTX!r}"
        )


@pytest.mark.parametrize("role", ["orchestrator", "planner", "control"])
def test_create_model_registry_ollama_all_roles_have_think_false(role: str):
    env = {
        "LLM_PROVIDER": "ollama",
        "OLLAMA_BASE_URL": "http://localhost:11434",
        "OLLAMA_MODEL": "qwen2.5:7b",
    }
    with patch.dict(os.environ, env, clear=False):
        from packages.agent.model_registry import create_model_registry

        registry = create_model_registry()
        model = registry.get(role)
        assert model.reasoning is False  # type: ignore[union-attr]


def test_create_model_registry_openai_returns_chat_openai():
    env = {
        "LLM_PROVIDER": "openai",
        "OPENAI_API_KEY": "sk-test-key",
        "OPENAI_MODEL": "gpt-4o",
    }
    with patch.dict(os.environ, env, clear=False):
        from langchain_openai import ChatOpenAI

        from packages.agent.model_registry import create_model_registry

        registry = create_model_registry()
        model = registry.get("orchestrator")
        assert isinstance(model, ChatOpenAI)


def test_create_model_registry_openai_missing_key_raises():
    env = {"LLM_PROVIDER": "openai"}
    with patch.dict(os.environ, env, clear=False):
        import os as _os
        _os.environ.pop("OPENAI_API_KEY", None)

        from packages.agent.model_registry import create_model_registry

        with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
            create_model_registry()


def test_create_model_registry_openai_base_url_forwarded():
    env = {
        "LLM_PROVIDER": "openai",
        "OPENAI_API_KEY": "sk-test-key",
        "OPENAI_MODEL": "gpt-4o-mini",
        "OPENAI_BASE_URL": "https://my-proxy.example.com/v1",
    }
    with patch.dict(os.environ, env, clear=False):
        from packages.agent.model_registry import create_model_registry

        registry = create_model_registry()
        model = registry.get("control")
        assert str(model.openai_api_base) == "https://my-proxy.example.com/v1"  # type: ignore[union-attr]


def test_model_registry_get_unknown_role_raises_value_error():
    from langchain_core.language_models.chat_models import BaseChatModel
    from unittest.mock import MagicMock

    from packages.agent.model_registry import ModelRegistry

    stub: BaseChatModel = MagicMock(spec=BaseChatModel)
    registry = ModelRegistry({"orchestrator": stub, "planner": stub, "control": stub})
    with pytest.raises(ValueError, match="Unknown model role"):
        registry.get("nonexistent")
