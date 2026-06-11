"""Unit tests for LLM usage recording wiring (T-526).

Tests:
1. create_model_registry(usage_writer=...) attaches UsageRecordingCallbackHandler
   to each model's callbacks (using LLM_PROVIDER=ollama, monkeypatched env; no network).
2. Default create_model_registry() call (no usage_writer) attaches no handler.
3. _real_usage_writer step-fallback:
   - agent_step_id=None + session_id present → make_step called and returned id
     passed to LlmUsageRepository.create.
   - Both None → no write at all.

Zero-network rule: construction of ChatOllama does NOT make real HTTP calls.
asyncio_mode=auto — no @pytest.mark.asyncio.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

from packages.agent.llm import LLMUsage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_usage() -> LLMUsage:
    return LLMUsage(
        input_tokens=10,
        output_tokens=5,
        total_cost_usd=Decimal("0"),
    )


# ---------------------------------------------------------------------------
# 1. create_model_registry with usage_writer attaches the handler
# ---------------------------------------------------------------------------


def test_create_model_registry_with_writer_attaches_handler(monkeypatch: Any) -> None:
    """Each model in the registry has a UsageRecordingCallbackHandler in its callbacks."""
    from packages.agent.llm.usage_recording import UsageRecordingCallbackHandler
    from packages.agent.model_registry import create_model_registry

    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:7b")

    writer = AsyncMock()
    registry = create_model_registry(usage_writer=writer)

    for role in ("orchestrator", "planner", "control"):
        model = registry.get(role)
        callbacks = getattr(model, "callbacks", None) or []
        handler_types = [type(cb).__name__ for cb in callbacks]
        assert "UsageRecordingCallbackHandler" in handler_types, (
            f"Role '{role}' missing UsageRecordingCallbackHandler in callbacks: {handler_types}"
        )


def test_create_model_registry_with_writer_handler_has_correct_provider(
    monkeypatch: Any,
) -> None:
    """The attached handler is initialised with provider='ollama'."""
    from packages.agent.llm.usage_recording import UsageRecordingCallbackHandler
    from packages.agent.model_registry import create_model_registry

    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:7b")

    writer = AsyncMock()
    registry = create_model_registry(usage_writer=writer)

    model = registry.get("orchestrator")
    callbacks = getattr(model, "callbacks", None) or []
    handlers = [cb for cb in callbacks if isinstance(cb, UsageRecordingCallbackHandler)]
    assert handlers, "No UsageRecordingCallbackHandler found"
    assert handlers[0]._provider == "ollama"


# ---------------------------------------------------------------------------
# 2. Default create_model_registry (no usage_writer) attaches nothing
# ---------------------------------------------------------------------------


def test_create_model_registry_without_writer_no_handler(monkeypatch: Any) -> None:
    """When no usage_writer is provided, callbacks list is empty for all models."""
    from packages.agent.llm.usage_recording import UsageRecordingCallbackHandler
    from packages.agent.model_registry import create_model_registry

    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:7b")

    registry = create_model_registry()  # no usage_writer

    for role in ("orchestrator", "planner", "control"):
        model = registry.get(role)
        callbacks = getattr(model, "callbacks", None) or []
        handlers = [cb for cb in callbacks if isinstance(cb, UsageRecordingCallbackHandler)]
        assert not handlers, (
            f"Role '{role}' should have no handler when usage_writer is None, "
            f"but found: {handlers}"
        )


# ---------------------------------------------------------------------------
# 3. _real_usage_writer step-fallback
# ---------------------------------------------------------------------------


async def test_real_usage_writer_creates_step_when_agent_step_id_is_none() -> None:
    """When agent_step_id=None and session_id present, make_step is called and its
    returned id is forwarded to LlmUsageRepository.create."""
    from apps.api.state import _real_usage_writer

    session_id = uuid4()
    fallback_step_id = uuid4()

    mock_repo = MagicMock()
    mock_repo.create = AsyncMock()

    # make_step is imported inside _real_usage_writer body:
    #   from packages.persistence.agent_steps_repo import make_step
    # So we patch it at its source module, not at apps.api.state.
    with (
        patch(
            "packages.persistence.agent_steps_repo.make_step",
            new=AsyncMock(return_value=fallback_step_id),
        ) as mock_make_step,
        patch("apps.api.state.LlmUsageRepository", return_value=mock_repo),
        patch("apps.api.state.asyncio.create_task") as mock_create_task,
    ):
        await _real_usage_writer(
            session_id=session_id,
            agent_step_id=None,
            specialist_role="control",
            provider="ollama",
            model="qwen2.5:7b",
            usage=_make_usage(),
        )

        # make_step must be called with the session_id
        mock_make_step.assert_awaited_once()
        call_args = mock_make_step.call_args
        assert str(session_id) in str(call_args)

        # asyncio.create_task must be called (the write coroutine is scheduled)
        mock_create_task.assert_called_once()

        # Extract the coroutine that was passed to create_task and await it
        # to verify LlmUsageRepository.create is called with the fallback step id
        coro = mock_create_task.call_args[0][0]
        await coro

        mock_repo.create.assert_awaited_once()
        create_kwargs = mock_repo.create.call_args[1]
        assert create_kwargs["agent_step_id"] == str(fallback_step_id)


async def test_real_usage_writer_skips_write_when_both_ids_none() -> None:
    """When both session_id and agent_step_id are None, no write occurs at all."""
    from apps.api.state import _real_usage_writer

    with (
        patch(
            "packages.persistence.agent_steps_repo.make_step",
            new=AsyncMock(),
        ) as mock_make_step,
        patch("apps.api.state.LlmUsageRepository") as mock_repo_cls,
        patch("apps.api.state.asyncio.create_task") as mock_create_task,
    ):
        await _real_usage_writer(
            session_id=None,
            agent_step_id=None,
            specialist_role=None,
            provider="ollama",
            model="qwen2.5:7b",
            usage=_make_usage(),
        )

        # Both None: returns immediately before calling make_step or creating the task
        mock_make_step.assert_not_awaited()
        mock_repo_cls.assert_not_called()
        mock_create_task.assert_not_called()


async def test_real_usage_writer_uses_supplied_step_id_directly() -> None:
    """When agent_step_id is already set, make_step is NOT called."""
    from apps.api.state import _real_usage_writer

    session_id = uuid4()
    step_id = uuid4()

    mock_repo = MagicMock()
    mock_repo.create = AsyncMock()

    with (
        patch(
            "packages.persistence.agent_steps_repo.make_step",
            new=AsyncMock(),
        ) as mock_make_step,
        patch("apps.api.state.LlmUsageRepository", return_value=mock_repo),
        patch("apps.api.state.asyncio.create_task") as mock_create_task,
    ):
        await _real_usage_writer(
            session_id=session_id,
            agent_step_id=step_id,
            specialist_role="orchestrator",
            provider="anthropic",
            model="claude-sonnet-4-6",
            usage=_make_usage(),
        )

        # make_step must NOT be called — step_id was supplied
        mock_make_step.assert_not_awaited()

        # But the write task IS created
        mock_create_task.assert_called_once()

        # Await the write coroutine and verify it uses the supplied step_id
        coro = mock_create_task.call_args[0][0]
        await coro

        mock_repo.create.assert_awaited_once()
        create_kwargs = mock_repo.create.call_args[1]
        assert create_kwargs["agent_step_id"] == str(step_id)


async def test_real_usage_writer_make_step_failure_skips_write() -> None:
    """When make_step returns None (DB failure), no write is performed."""
    from apps.api.state import _real_usage_writer

    session_id = uuid4()

    mock_repo = MagicMock()
    mock_repo.create = AsyncMock()

    with (
        patch(
            "packages.persistence.agent_steps_repo.make_step",
            new=AsyncMock(return_value=None),
        ),
        patch("apps.api.state.LlmUsageRepository", return_value=mock_repo),
        patch("apps.api.state.asyncio.create_task") as mock_create_task,
    ):
        await _real_usage_writer(
            session_id=session_id,
            agent_step_id=None,
            specialist_role=None,
            provider="ollama",
            model="qwen2.5:7b",
            usage=_make_usage(),
        )

        # make_step returned None → effective_step_id is None → skip write
        mock_create_task.assert_not_called()
        mock_repo.create.assert_not_awaited()


# ---------------------------------------------------------------------------
# 4. classify_intent passes step-id in invoke metadata
# ---------------------------------------------------------------------------


async def test_classify_intent_passes_agent_step_id_in_metadata() -> None:
    """classify_intent must forward the make_step id in the ainvoke config metadata."""
    from packages.agent.orchestrator.models import SessionIntent, SessionUserQuery

    expected_step_id = uuid4()

    # Capture the config passed to ainvoke
    captured_config: list[Any] = []

    structured_mock = MagicMock()

    async def _fake_ainvoke(messages: Any, config: Any = None, **kwargs: Any) -> SessionIntent:
        captured_config.append(config)
        return SessionIntent(
            category="analysis", confidence=0.9, rationale="test", goal_text="goal"
        )

    structured_mock.ainvoke = _fake_ainvoke
    model_mock = MagicMock()
    model_mock.with_structured_output.return_value = structured_mock

    from packages.agent.model_registry import ModelRegistry
    registry = MagicMock(spec=ModelRegistry)
    registry.get.return_value = model_mock

    from packages.agent.orchestrator.session_orchestrator import SessionOrchestrator
    from packages.memory import StubMemoryStore

    orch = SessionOrchestrator(
        llm_client=MagicMock(),
        tool_registry=MagicMock(),
        memory_store=StubMemoryStore(),
        model_registry=registry,
    )

    session_id = uuid4()

    # make_step is imported inside classify_intent body:
    #   from packages.persistence.agent_steps_repo import make_step
    # Patch at its definition module so the local binding in the function is replaced.
    with patch(
        "packages.persistence.agent_steps_repo.make_step",
        new=AsyncMock(return_value=expected_step_id),
    ):
        await orch.classify_intent(
            SessionUserQuery(text="What is stock level?"),
            session_id,
        )

    assert captured_config, "ainvoke was not called — classify_intent did not invoke the model"
    metadata = captured_config[0].get("metadata", {})
    assert metadata.get("agent_step_id") == str(expected_step_id), (
        f"Expected agent_step_id={expected_step_id!s} in metadata, got: {metadata!r}"
    )
    assert metadata.get("session_id") == str(session_id)
    assert metadata.get("specialist_role") == "orchestrator"


async def test_classify_intent_agent_step_id_none_when_make_step_fails() -> None:
    """When make_step returns None, agent_step_id in metadata is None (not raises)."""
    from packages.agent.orchestrator.models import SessionIntent, SessionUserQuery

    captured_config: list[Any] = []

    structured_mock = MagicMock()

    async def _fake_ainvoke(messages: Any, config: Any = None, **kwargs: Any) -> SessionIntent:
        captured_config.append(config)
        return SessionIntent(
            category="chat", confidence=0.95, rationale="test"
        )

    structured_mock.ainvoke = _fake_ainvoke
    model_mock = MagicMock()
    model_mock.with_structured_output.return_value = structured_mock

    from packages.agent.model_registry import ModelRegistry
    registry = MagicMock(spec=ModelRegistry)
    registry.get.return_value = model_mock

    from packages.agent.orchestrator.session_orchestrator import SessionOrchestrator
    from packages.memory import StubMemoryStore

    orch = SessionOrchestrator(
        llm_client=MagicMock(),
        tool_registry=MagicMock(),
        memory_store=StubMemoryStore(),
        model_registry=registry,
    )

    with patch(
        "packages.persistence.agent_steps_repo.make_step",
        new=AsyncMock(return_value=None),
    ):
        result = await orch.classify_intent(
            SessionUserQuery(text="Hello!"),
            uuid4(),
        )

    assert result is not None  # function succeeds even when step creation fails
    assert captured_config, "ainvoke not called"
    metadata = captured_config[0].get("metadata", {})
    assert metadata.get("agent_step_id") is None
