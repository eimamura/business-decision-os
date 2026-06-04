"""Shared LLM test helpers for unit tests.

Centralises make_llm_usage(), make_stop_response(), make_tool_call_response(),
and RecordingLLMClient so they are not copy-pasted across multiple test files.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any
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
