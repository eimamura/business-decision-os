"""Shared LLM test helpers for unit tests.

Centralises make_llm_usage(), make_stop_response(), make_tool_call_response(),
RecordingLLMClient, FakeLCModel, and make_model_registry() so they are not
copy-pasted across multiple test files.
"""
from __future__ import annotations

import types
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

from packages.agent.llm import LLMMessage, LLMResponse, LLMUsage


def make_llm_usage(
    input_tokens: int = 10,
    output_tokens: int = 5,
) -> LLMUsage:
    return LLMUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_cost_usd=Decimal("0"),
    )


def make_tool_call_response(
    tool_name: str,
    tool_input: dict[str, Any],
    call_id: str = "call_001",
) -> LLMResponse:
    return LLMResponse(
        text="",
        tool_calls=[{"id": call_id, "name": tool_name, "input": tool_input}],
        finish_reason="tool_use",
        usage=make_llm_usage(),
        model="claude-sonnet-4-6-test",
        request_id=str(uuid4()),
        latency_ms=1,
    )


def make_stop_response(text: str = "Done.") -> LLMResponse:
    return LLMResponse(
        text=text,
        tool_calls=[],
        finish_reason="stop",
        usage=make_llm_usage(),
        model="claude-sonnet-4-6-test",
        request_id=str(uuid4()),
        latency_ms=1,
    )


class RecordingLLMClient:
    """Records every complete() call and returns pre-configured responses in order."""

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self._calls: list[list[LLMMessage]] = []
        self._model = "claude-sonnet-4-6-mock"

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: Any = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        prompt_cache: bool = True,
        agent_step_id: Any = None,
        specialist_role: Any = None,
    ) -> LLMResponse:
        self._calls.append(list(messages))
        if not self._responses:
            return make_stop_response("fallback")
        return self._responses.pop(0)


# ---------------------------------------------------------------------------
# LangChain-compatible fake model — wraps LLMResponse objects so that
# AgentRuntime._call_model_node (LangChain path) can be tested without
# a real LLM backend.
# ---------------------------------------------------------------------------


def _llm_response_to_ai_message(resp: LLMResponse) -> Any:
    """Convert an LLMResponse into a LangChain AIMessage."""
    from langchain_core.messages import AIMessage

    # Map {name, id, input} tool calls to LangChain {name, id, args} format
    lc_tool_calls = [
        {"name": tc["name"], "id": tc["id"], "args": tc.get("input", {})}
        for tc in (resp.tool_calls or [])
    ]
    usage_metadata = {
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
        "total_tokens": resp.usage.input_tokens + resp.usage.output_tokens,
    }
    return AIMessage(
        content=resp.text,
        tool_calls=lc_tool_calls,
        usage_metadata=usage_metadata,
    )


class FakeLCModel:
    """LangChain-style chat model that returns pre-configured LLMResponse objects.

    Implements .ainvoke() and .bind_tools() so that AgentRuntime._call_model_node
    and session_orchestrator / planning functions can run without a real LLM.
    """

    model = "fake-lc-model"

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self._calls: list[Any] = []

    def bind_tools(self, tools: Any) -> "FakeLCModel":
        """Return self — tool binding is a no-op in the fake."""
        return self

    def with_structured_output(self, schema: Any) -> "_FakeStructured":
        return _FakeStructured(self._responses)

    async def ainvoke(self, messages: Any, **kwargs: Any) -> Any:
        self._calls.append(messages)
        if self._responses:
            resp = self._responses.pop(0)
        else:
            resp = make_stop_response("fallback")
        return _llm_response_to_ai_message(resp)


class _FakeStructured:
    """Returned by FakeLCModel.with_structured_output(); returns objects from the responses
    list directly (caller must populate the list with the expected Pydantic model instances)."""

    def __init__(self, responses: list[Any]) -> None:
        self._responses = responses  # shared reference

    async def ainvoke(self, messages: Any, **kwargs: Any) -> Any:
        if self._responses:
            return self._responses.pop(0)
        return None


class StructuredOutputFakeModel:
    """Fake LC model for orchestrator roles where with_structured_output is called.

    `structured_responses` is a list of Pydantic model instances that will be
    returned in order when .with_structured_output(...).ainvoke(...) is called.
    """

    model = "fake-structured-model"

    def __init__(self, structured_responses: list[Any]) -> None:
        self._structured_responses = list(structured_responses)

    def with_structured_output(self, schema: Any) -> "_FakeStructured":
        return _FakeStructured(self._structured_responses)

    def bind_tools(self, tools: Any) -> "StructuredOutputFakeModel":
        return self

    async def ainvoke(self, messages: Any, **kwargs: Any) -> Any:
        # Fallback for direct ainvoke (e.g., verify_findings)
        if self._structured_responses:
            item = self._structured_responses.pop(0)
            if isinstance(item, LLMResponse):
                return _llm_response_to_ai_message(item)
            return item
        return _llm_response_to_ai_message(make_stop_response("fallback"))


def make_model_registry(lc_model: Any) -> Any:
    """Create a minimal ModelRegistry mock that returns lc_model for any role."""
    registry = MagicMock()
    registry.get.return_value = lc_model
    return registry


class MultiRoleModelRegistry:
    """ModelRegistry where each role has its own FakeLCModel.

    Pass `role_models` as a dict mapping role name → FakeLCModel.
    A `default` key is used as fallback when the requested role is not found.
    """

    def __init__(self, role_models: dict[str, Any]) -> None:
        self._role_models = role_models

    def get(self, role: str) -> Any:
        return self._role_models.get(role) or self._role_models.get("default")
