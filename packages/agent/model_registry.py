from __future__ import annotations

import os

from langchain_core.language_models.chat_models import BaseChatModel


class ModelRegistry:
    """Role-based LangChain ChatModel selector.

    Maps role names to configured BaseChatModel instances.
    Provider-specific settings (num_predict) are encapsulated here.
    """

    def __init__(self, models: dict[str, BaseChatModel]) -> None:
        self._models = models

    def get(self, role: str) -> BaseChatModel:
        """Return the ChatModel for the given role.

        Args:
            role: One of 'orchestrator', 'planner', 'control'

        Raises:
            ValueError: If role is unknown
        """
        if role not in self._models:
            raise ValueError(
                f"Unknown model role: {role!r}. Valid roles: {sorted(self._models)}"
            )
        return self._models[role]


def create_model_registry() -> ModelRegistry:
    """Build a ModelRegistry from environment variables.

    Required env vars:
        LLM_PROVIDER: 'anthropic', 'ollama', or 'openai'

    For anthropic:
        ANTHROPIC_API_KEY: API key
        ANTHROPIC_MODEL: model name (default: 'claude-sonnet-4-6')

    For ollama:
        OLLAMA_BASE_URL: base URL (default: 'http://localhost:11434')
        OLLAMA_MODEL: model name (default: 'qwen2.5:7b')

    For openai:
        OPENAI_API_KEY: API key
        OPENAI_MODEL: model name (default: 'gpt-4o')
        OPENAI_BASE_URL: optional base URL for OpenAI-compatible endpoints
    """
    provider = os.environ.get("LLM_PROVIDER", "anthropic").lower()

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")
        model_name = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
        from pydantic import SecretStr
        base_model = ChatAnthropic(model=model_name, api_key=SecretStr(api_key), temperature=0.0)  # type: ignore[call-arg]
        return ModelRegistry(
            {
                "orchestrator": base_model,
                "planner": base_model,
                "control": base_model,
            }
        )

    elif provider == "ollama":
        from langchain_ollama import ChatOllama

        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        model_name = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
        # ChatOllama field: reasoning=False → sent to Ollama API as think=false
        # Prevents thinking models (qwen3, deepseek-r1) from exhausting num_predict
        # before emitting JSON content. Note: ChatOllama(think=False) is silently ignored.
        structured_model = ChatOllama(
            model=model_name,
            base_url=base_url,
            temperature=0.0,
            num_predict=512,
            reasoning=False,
        )
        # reasoning=False (→ Ollama API: think=false) required for tool calling accuracy
        control_model = ChatOllama(
            model=model_name,
            base_url=base_url,
            temperature=0.0,
            reasoning=False,
        )
        return ModelRegistry(
            {
                "orchestrator": structured_model,
                "planner": structured_model,
                "control": control_model,
            }
        )

    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        from pydantic import SecretStr

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        model_name = os.environ.get("OPENAI_MODEL", "gpt-4o")
        openai_base_url: str | None = os.environ.get("OPENAI_BASE_URL")
        if openai_base_url:
            openai_model = ChatOpenAI(
                model=model_name,
                api_key=SecretStr(api_key),
                temperature=0.0,
                base_url=openai_base_url,
            )
        else:
            openai_model = ChatOpenAI(
                model=model_name,
                api_key=SecretStr(api_key),
                temperature=0.0,
            )
        return ModelRegistry(
            {
                "orchestrator": openai_model,
                "planner": openai_model,
                "control": openai_model,
            }
        )

    else:
        raise RuntimeError(
            f"Unsupported LLM_PROVIDER: {provider!r}. Use 'anthropic', 'ollama', or 'openai'."
        )
