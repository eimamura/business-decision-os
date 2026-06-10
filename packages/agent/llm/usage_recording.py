from __future__ import annotations

import json
import logging
import time
from decimal import Decimal
from typing import Any
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult

from packages.agent.llm import LLMUsage, UsageWriter

_log = logging.getLogger(__name__)


class UsageRecordingCallbackHandler(AsyncCallbackHandler):
    """LangChain callback handler that records LLM usage to the persistence layer.

    Attach one instance per ChatModel via the ``callbacks`` constructor field.
    The handler is exception-safe: writer failures are logged as warnings and
    never propagate into the caller's execution path.

    Metadata propagation:
        LangChain propagates ``config={"metadata": {...}}`` to callbacks via
        the ``metadata`` kwarg of ``on_chat_model_start``.  LangGraph propagates
        the graph-level ``config["metadata"]`` to all child model calls through
        the same mechanism.  Keys consumed here:

        - ``session_id`` (str | None): UUID of the decision session.
        - ``agent_step_id`` (str | None): UUID of the agent_steps row for this call.
        - ``specialist_role`` (str | None): role label (e.g. "orchestrator", "control").
    """

    def __init__(
        self,
        writer: UsageWriter,
        provider: str,
        fallback_model_name: str = "unknown",
    ) -> None:
        """Initialise the handler.

        Args:
            writer: Async callable matching the ``UsageWriter`` type alias.
            provider: Provider string — "anthropic", "ollama", or "openai".
            fallback_model_name: Model name used when it cannot be extracted from the
                LLMResult.  Defaults to "unknown".
        """
        super().__init__()
        self._writer = writer
        self._provider = provider
        self._fallback_model_name = fallback_model_name

        # Per-run state keyed by run_id UUID.
        # Value: {"start_time": float, "prompt_messages_json": str | None,
        #         "session_id": UUID | None, "agent_step_id": UUID | None,
        #         "specialist_role": str | None}
        self._run_state: dict[UUID, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # on_chat_model_start
    # ------------------------------------------------------------------

    async def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[BaseMessage]],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Record start time, prompt messages, and session context for *run_id*."""
        start_time = time.monotonic()

        meta = metadata or {}
        raw_session_id: str | None = meta.get("session_id")
        raw_step_id: str | None = meta.get("agent_step_id")
        specialist_role: str | None = meta.get("specialist_role")

        session_id: UUID | None = None
        if raw_session_id:
            try:
                session_id = UUID(raw_session_id)
            except (ValueError, AttributeError):
                _log.warning(
                    "UsageRecording: invalid session_id in metadata: %r", raw_session_id
                )

        agent_step_id: UUID | None = None
        if raw_step_id:
            try:
                agent_step_id = UUID(raw_step_id)
            except (ValueError, AttributeError):
                _log.warning(
                    "UsageRecording: invalid agent_step_id in metadata: %r", raw_step_id
                )

        # Serialize prompt messages to JSON (role + content only).
        try:
            flat: list[dict[str, Any]] = []
            for batch in messages:
                for msg in batch:
                    flat.append({
                        "role": getattr(msg, "type", type(msg).__name__),
                        "content": (
                            msg.content
                            if isinstance(msg.content, str)
                            else json.dumps(msg.content)
                        ),
                    })
            prompt_messages_json: str | None = json.dumps(flat)
        except Exception:  # Any: serialisation is best-effort; broad catch is intentional
            prompt_messages_json = None

        self._run_state[run_id] = {
            "start_time": start_time,
            "prompt_messages_json": prompt_messages_json,
            "session_id": session_id,
            "agent_step_id": agent_step_id,
            "specialist_role": specialist_role,
        }

    # ------------------------------------------------------------------
    # on_llm_end
    # ------------------------------------------------------------------

    async def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """Extract usage from *response* and invoke the writer."""
        state = self._run_state.pop(run_id, None)

        if state is None:
            # on_llm_end fired without a preceding on_chat_model_start — benign.
            # (Can happen when a run is replayed from a checkpoint.)
            _log.debug(
                "UsageRecording: on_llm_end received for unknown run_id %s — skipping", run_id
            )
            return

        end_time = time.monotonic()
        latency_ms = int((end_time - state["start_time"]) * 1000)

        # Extract the first generation (there is always exactly one for chat models).
        generation: Any = None
        if response.generations and response.generations[0]:
            generation = response.generations[0][0]

        ai_message: Any = None
        if generation is not None:
            ai_message = getattr(generation, "message", None)

        # --- Model name ---
        model_name: str = self._fallback_model_name
        # Try llm_output["model_name"] first (Anthropic / OpenAI pattern).
        if response.llm_output and isinstance(response.llm_output, dict):
            candidate = response.llm_output.get("model_name") or response.llm_output.get("model")
            if candidate:
                model_name = str(candidate)
        # Try response_metadata on the AIMessage (Anthropic / Ollama pattern).
        if model_name == self._fallback_model_name and ai_message is not None:
            resp_meta: dict[str, Any] = getattr(ai_message, "response_metadata", {}) or {}
            candidate = resp_meta.get("model") or resp_meta.get("model_name")
            if candidate:
                model_name = str(candidate)

        # --- Token counts from usage_metadata ---
        input_tokens = 0
        output_tokens = 0
        cache_read_tokens = 0
        cache_write_tokens = 0

        if ai_message is not None:
            usage_meta: Any = getattr(ai_message, "usage_metadata", None)
            if isinstance(usage_meta, dict):
                input_tokens = int(usage_meta.get("input_tokens", 0))
                output_tokens = int(usage_meta.get("output_tokens", 0))
                # input_token_details holds cache breakdown (present for Anthropic).
                input_details: dict[str, Any] = usage_meta.get("input_token_details") or {}
                cache_read_tokens = int(input_details.get("cache_read", 0))
                cache_write_tokens = int(input_details.get("cache_creation", 0))

        # --- Response text ---
        response_text: str | None = None
        if ai_message is not None:
            raw_content = getattr(ai_message, "content", None)
            if isinstance(raw_content, str):
                response_text = raw_content
            elif raw_content is not None:
                try:
                    response_text = json.dumps(raw_content)
                except Exception:  # Any: broad; serialisation is best-effort
                    response_text = None

        # --- Tool calls ---
        tool_calls_json: str | None = None
        if ai_message is not None:
            raw_tool_calls: Any = getattr(ai_message, "tool_calls", None)
            if raw_tool_calls:
                try:
                    tool_calls_json = json.dumps(raw_tool_calls)
                except Exception:  # Any: broad; serialisation is best-effort
                    tool_calls_json = None

        usage = LLMUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
            total_cost_usd=Decimal("0"),
            prompt_messages_json=state["prompt_messages_json"],
            response_text=response_text,
            tool_calls_json=tool_calls_json,
        )

        session_id: UUID | None = state["session_id"]
        agent_step_id: UUID | None = state["agent_step_id"]
        specialist_role: str | None = state["specialist_role"]

        _log.debug(
            "UsageRecording: run_id=%s provider=%s model=%s latency_ms=%d "
            "input_tokens=%d output_tokens=%d",
            run_id,
            self._provider,
            model_name,
            latency_ms,
            input_tokens,
            output_tokens,
        )

        try:
            await self._writer(
                session_id,
                agent_step_id,
                specialist_role,
                self._provider,
                model_name,
                usage,
            )
        except Exception as exc:  # Any: writer failures must never crash the agent run
            _log.warning(
                "UsageRecording: writer raised an exception (non-fatal): %s", exc
            )

    # ------------------------------------------------------------------
    # on_llm_error
    # ------------------------------------------------------------------

    async def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """Pop per-run state on error to prevent memory leaks."""
        self._run_state.pop(run_id, None)
