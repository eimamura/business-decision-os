from __future__ import annotations

import logging
import os
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel

from packages.agent.llm import UsageWriter

_log = logging.getLogger(__name__)

# Ollama default num_ctx=4096 silently truncated the control prompt after P86-P91 growth
# (tools 31→37, schema tables 8→12 pushed the prompt past 4096 — judge-FAIL 2026-06-12).
# 16384 ≈ 4× headroom over the current ~4.1K control prompt; gemma4:12b supports 128K.
# Accepted floor 8192 if VRAM-constrained — document the change in a code comment if lowered.
_OLLAMA_NUM_CTX = 16384

# Warn when reported input tokens reach 90% of the configured context window.
_CTX_SATURATION_RATIO = 0.9


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


def _make_callbacks(usage_writer: UsageWriter | None, provider: str) -> list[Any]:
    """Build the callbacks list for a ChatModel.

    Returns a list containing one ``UsageRecordingCallbackHandler`` when
    *usage_writer* is provided, or an empty list otherwise.
    """
    if usage_writer is None:
        return []
    from packages.agent.llm.usage_recording import UsageRecordingCallbackHandler

    return [UsageRecordingCallbackHandler(writer=usage_writer, provider=provider)]


def create_model_registry(usage_writer: UsageWriter | None = None) -> ModelRegistry:
    """Build a ModelRegistry from environment variables.

    Test-only override (takes precedence over LLM_PROVIDER):
        LLM_DRIVER: 'scripted' builds a registry of ScriptedDriverModel
            instances that emit a deterministic job_dispatch tool-call
            sequence, so job-flow e2e scenarios never depend on live model
            NL routing (D-026). Any other non-empty value raises RuntimeError.

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

    Args:
        usage_writer: Optional ``UsageWriter`` callable.  When provided, a
            ``UsageRecordingCallbackHandler`` is attached to every ChatModel via
            ``callbacks``.  Defaults to ``None`` (no recording — existing tests
            and tool-only call sites are unaffected).
    """
    driver = os.environ.get("LLM_DRIVER", "").strip().lower()
    if driver:
        if driver != "scripted":
            raise RuntimeError(
                f"Unsupported LLM_DRIVER: {driver!r}. Only 'scripted' is supported."
            )
        from packages.agent.scripted_model import ScriptedDriverModel

        callbacks = _make_callbacks(usage_writer, "scripted")
        # One shared instance; bind_tools() returns copies, so the shared
        # instance is never mutated.
        scripted = ScriptedDriverModel(callbacks=callbacks or None)
        return ModelRegistry(
            {
                "orchestrator": scripted,
                "planner": scripted,
                "control": scripted,
            }
        )

    provider = os.environ.get("LLM_PROVIDER", "anthropic").lower()
    callbacks = _make_callbacks(usage_writer, provider)

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")
        model_name = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
        from pydantic import SecretStr
        base_model = ChatAnthropic(  # type: ignore[call-arg]
            model=model_name,
            api_key=SecretStr(api_key),
            temperature=0.0,
            callbacks=callbacks or None,
        )
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
        # Prevents thinking models (qwen3, deepseek-r1, gemma4) from exhausting num_predict
        # before emitting JSON content. Note: ChatOllama(think=False) is silently ignored.
        # temperature=0.1: gemma4 is tuned for temperature=1.0; 0.0 causes greedy-decoding loops.
        # num_ctx=_OLLAMA_NUM_CTX: sets the KV-cache / context window; see constant docstring.
        structured_model = ChatOllama(
            model=model_name,
            base_url=base_url,
            temperature=0.1,
            num_predict=512,
            num_ctx=_OLLAMA_NUM_CTX,
            reasoning=False,
            callbacks=callbacks or None,
        )
        # reasoning=False (→ Ollama API: think=false) required for tool calling accuracy.
        # num_predict=2048: surfaces truncation via output_tokens warning log if thinking leaks.
        # num_ctx=_OLLAMA_NUM_CTX: sets the KV-cache / context window; see constant docstring.
        control_model = ChatOllama(
            model=model_name,
            base_url=base_url,
            temperature=0.1,
            num_predict=2048,
            num_ctx=_OLLAMA_NUM_CTX,
            reasoning=False,
            callbacks=callbacks or None,
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
                callbacks=callbacks or None,
            )
        else:
            openai_model = ChatOpenAI(
                model=model_name,
                api_key=SecretStr(api_key),
                temperature=0.0,
                callbacks=callbacks or None,
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
