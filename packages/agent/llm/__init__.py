from __future__ import annotations

from decimal import Decimal
from typing import Any, AsyncIterator, Literal, Protocol, TypedDict
from uuid import UUID

from pydantic import BaseModel


class LLMMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: str | None = None
    tool_call_id: str | None = None


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


class LLMClient(Protocol):
    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolSpec] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        prompt_cache: bool = True,
        agent_step_id: UUID | None = None,
        specialist_role: str | None = None,
    ) -> LLMResponse: ...

    async def stream(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolSpec] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        prompt_cache: bool = True,
        agent_step_id: UUID | None = None,
        specialist_role: str | None = None,
    ) -> AsyncIterator[LLMStreamEvent]: ...

    async def embed(
        self,
        texts: list[str],
        model: str = "text-embedding-3-small",
        agent_step_id: UUID | None = None,
    ) -> list[list[float]]: ...


class ClaudeClient:
    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolSpec] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        prompt_cache: bool = True,
        agent_step_id: UUID | None = None,
        specialist_role: str | None = None,
    ) -> LLMResponse:
        raise NotImplementedError("Phase 1")

    async def stream(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolSpec] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        prompt_cache: bool = True,
        agent_step_id: UUID | None = None,
        specialist_role: str | None = None,
    ) -> AsyncIterator[LLMStreamEvent]:
        raise NotImplementedError("Phase 1")

    async def embed(
        self,
        texts: list[str],
        model: str = "text-embedding-3-small",
        agent_step_id: UUID | None = None,
    ) -> list[list[float]]:
        raise NotImplementedError("Phase 1")
