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


def test_model_registry_get_unknown_role_raises_value_error():
    from langchain_core.language_models.chat_models import BaseChatModel
    from unittest.mock import MagicMock

    from packages.agent.model_registry import ModelRegistry

    stub: BaseChatModel = MagicMock(spec=BaseChatModel)
    registry = ModelRegistry({"orchestrator": stub, "planner": stub, "control": stub})
    with pytest.raises(ValueError, match="Unknown model role"):
        registry.get("nonexistent")
