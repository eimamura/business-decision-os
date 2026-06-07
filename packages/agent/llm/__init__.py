from __future__ import annotations

import os
from decimal import Decimal
from typing import Any, AsyncIterator, Callable, Coroutine, Literal, TypedDict
from uuid import UUID, uuid4

from pydantic import BaseModel


class LLMMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    content_blocks: list[dict[str, Any]] | None = None


class LLMToolSpec(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]


class LLMUsage(BaseModel):
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    total_cost_usd: Decimal
    prompt_messages_json: str | None = None
    response_text: str | None = None
    tool_calls_json: str | None = None


class LLMResponse(BaseModel):
    text: str
    tool_calls: list[dict[str, Any]]
    finish_reason: Literal["stop", "tool_use", "length", "error"]
    usage: LLMUsage
    model: str
    request_id: str
    latency_ms: int


class LLMStreamEvent(TypedDict, total=False):
    event: Literal[
        "text_delta",
        "tool_call_start",
        "tool_call_delta",
        "tool_call_end",
        "usage_update",
        "error",
    ]
    data: str
    tool_call_id: str
    tool_name: str
    input_delta: str
    usage: dict[str, Any]
    error: str


UsageWriter = Callable[
    [UUID | None, UUID | None, str | None, str, str, LLMUsage],
    Coroutine[Any, Any, None],
]


async def _noop_usage_writer(
    session_id: UUID | None,
    agent_step_id: UUID | None,
    specialist_role: str | None,
    provider: str,
    model: str,
    usage: LLMUsage,
) -> None:
    pass


class StubClaudeClient:
    def __init__(self, usage_writer: UsageWriter | None = None) -> None:
        self._usage_writer: UsageWriter = usage_writer or _noop_usage_writer
        self._model = "claude-sonnet-4-6-stub"

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolSpec] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 8192,
        prompt_cache: bool = True,
        agent_step_id: UUID | None = None,
        specialist_role: str | None = None,
    ) -> LLMResponse:
        usage = LLMUsage(
            input_tokens=0,
            output_tokens=0,
            cache_read_tokens=0,
            cache_write_tokens=0,
            total_cost_usd=Decimal("0"),
        )
        await self._usage_writer(
            None, agent_step_id, specialist_role, "anthropic", self._model, usage
        )
        return LLMResponse(
            text="stub response",
            tool_calls=[],
            finish_reason="stop",
            usage=usage,
            model=self._model,
            request_id=str(uuid4()),
            latency_ms=0,
        )

    async def stream(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolSpec] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 8192,
        prompt_cache: bool = True,
        agent_step_id: UUID | None = None,
        specialist_role: str | None = None,
    ) -> AsyncIterator[LLMStreamEvent]:
        async def _gen() -> AsyncIterator[LLMStreamEvent]:
            yield LLMStreamEvent(event="text_delta", data="stub response")

        return _gen()

    async def astream(self, input: Any, config: Any = None, **kwargs: Any) -> AsyncIterator[Any]:
        from types import SimpleNamespace
        lc_msgs = input if isinstance(input, list) else []
        msgs = [
            LLMMessage(
                role="system" if getattr(m, "type", "") == "system" else (
                    "assistant" if getattr(m, "type", "") == "ai" else "user"
                ),
                content=getattr(m, "content", ""),
            )
            for m in lc_msgs
        ]
        response = await self.complete(msgs)
        yield SimpleNamespace(content=response.text)

    async def embed(
        self,
        texts: list[str],
        model: str = "text-embedding-3-small",
        agent_step_id: UUID | None = None,
    ) -> list[list[float]]:
        return [[0.0] * 1536 for _ in texts]


class ScenarioStubClaudeClient:
    """Schema-conforming stub for cost-free UI and integration testing.

    Inspects system message content to detect the orchestrator call type and
    returns schema-conforming JSON responses.  Use this client when MOCK_LLM=true.
    """

    _model = "scenario-stub-v1"

    def _collect_system_text(self, messages: list[LLMMessage]) -> str:
        parts: list[str] = []
        for msg in messages:
            if msg.role != "system":
                continue
            if msg.content_blocks:
                for block in msg.content_blocks:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "")
                        if text:
                            parts.append(text)
            elif msg.content:
                parts.append(msg.content)
        return " ".join(parts).lower()

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolSpec] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 8192,
        prompt_cache: bool = True,
        agent_step_id: UUID | None = None,
        specialist_role: str | None = None,
    ) -> LLMResponse:
        import json

        system_text = self._collect_system_text(messages)

        if "information-gathering" in system_text:
            if os.environ.get("MOCK_ASK_USER", "").lower() == "true":
                response_text = json.dumps({
                    "needs_input": True,
                    "question": "What date range should I analyze?",
                    "suggestions": ["Last 30 days", "Q1 2025", "Last 12 months"],
                })
            else:
                response_text = json.dumps(
                    {"needs_input": False, "question": None, "suggestions": None}
                )
        elif "intent classifier" in system_text or "category" in system_text:
            category = (
                "domain_analysis"
                if os.environ.get("MOCK_ASK_USER", "").lower() == "true"
                else "lookup"
            )
            response_text = json.dumps({
                "category": category,
                "confidence": 0.95,
                "rationale": "Mock mode",
                "goal_text": "mock goal",
            })
        elif "route" in system_text or "primary_role" in system_text:
            response_text = json.dumps({
                "mode": "single_agent",
                "agents": ["data_engineer"],
                "rationale": "Mock stub",
            })
        elif "verify" in system_text or "findings" in system_text:
            response_text = json.dumps({
                "status": "pass",
                "rationale": "Mock mode — no verification performed",
            })
        else:
            response_text = "Mock mode response — no LLM cost incurred."

        usage = LLMUsage(
            input_tokens=0,
            output_tokens=0,
            cache_read_tokens=0,
            cache_write_tokens=0,
            total_cost_usd=Decimal("0"),
        )
        return LLMResponse(
            text=response_text,
            tool_calls=[],
            finish_reason="stop",
            usage=usage,
            model=self._model,
            request_id=str(uuid4()),
            latency_ms=0,
        )

    async def stream(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolSpec] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 8192,
        prompt_cache: bool = True,
        agent_step_id: UUID | None = None,
        specialist_role: str | None = None,
    ) -> AsyncIterator[LLMStreamEvent]:
        async def _gen() -> AsyncIterator[LLMStreamEvent]:
            yield LLMStreamEvent(
                event="text_delta",
                data="Mock mode response — no LLM cost incurred.",
            )

        return _gen()

    async def astream(self, input: Any, config: Any = None, **kwargs: Any) -> AsyncIterator[Any]:
        from types import SimpleNamespace
        lc_msgs = input if isinstance(input, list) else []
        msgs = [
            LLMMessage(
                role="system" if getattr(m, "type", "") == "system" else (
                    "assistant" if getattr(m, "type", "") == "ai" else "user"
                ),
                content=getattr(m, "content", ""),
            )
            for m in lc_msgs
        ]
        response = await self.complete(msgs)
        yield SimpleNamespace(content=response.text)

    async def embed(
        self,
        texts: list[str],
        model: str = "text-embedding-3-small",
        agent_step_id: UUID | None = None,
    ) -> list[list[float]]:
        return [[0.0] * 1536 for _ in texts]
