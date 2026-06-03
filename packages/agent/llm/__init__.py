from __future__ import annotations

import os
import time
import warnings
from decimal import Decimal
from typing import Any, AsyncIterator, Awaitable, Callable, Coroutine, Literal, Protocol, TypedDict
from uuid import UUID, uuid4

from pydantic import BaseModel


class BudgetSoftLimitWarning(Warning):
    pass


class BudgetHardLimitError(RuntimeError):
    pass


class BudgetGuard:
    def __init__(
        self,
        soft_limit_usd: Decimal | None,
        hard_limit_usd: Decimal | None,
    ) -> None:
        self.soft_limit_usd = soft_limit_usd
        self.hard_limit_usd = hard_limit_usd
        self.accumulated_cost: Decimal = Decimal("0")

    def check_and_accumulate(self, cost: Decimal) -> None:
        self.accumulated_cost += cost
        if self.hard_limit_usd is not None and self.accumulated_cost >= self.hard_limit_usd:
            raise BudgetHardLimitError(
                f"LLM budget hard limit ${self.hard_limit_usd} exceeded:"
                f" accumulated ${self.accumulated_cost}"
            )
        if self.soft_limit_usd is not None and self.accumulated_cost >= self.soft_limit_usd:
            warnings.warn(
                BudgetSoftLimitWarning(
                    f"LLM budget soft limit ${self.soft_limit_usd} exceeded:"
                    f" accumulated ${self.accumulated_cost}"
                ),
                stacklevel=2,
            )


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
        max_tokens: int = 4096,
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
        max_tokens: int = 4096,
        prompt_cache: bool = True,
        agent_step_id: UUID | None = None,
        specialist_role: str | None = None,
    ) -> AsyncIterator[LLMStreamEvent]:
        async def _gen() -> AsyncIterator[LLMStreamEvent]:
            yield LLMStreamEvent(event="text_delta", data="stub response")

        return _gen()

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
        max_tokens: int = 4096,
        prompt_cache: bool = True,
        agent_step_id: UUID | None = None,
        specialist_role: str | None = None,
    ) -> LLMResponse:
        import json

        system_text = self._collect_system_text(messages)

        if "category" in system_text or "intent" in system_text:
            response_text = json.dumps({
                "category": "lookup",
                "confidence": 0.95,
                "rationale": "Mock mode",
                "goal_text": "mock goal",
            })
        elif "route" in system_text or "primary_role" in system_text:
            response_text = json.dumps({
                "mode": "single_agent",
                "primary_role": "data_engineer",
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
        max_tokens: int = 4096,
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

    async def embed(
        self,
        texts: list[str],
        model: str = "text-embedding-3-small",
        agent_step_id: UUID | None = None,
    ) -> list[list[float]]:
        return [[0.0] * 1536 for _ in texts]


class ClaudeClient:
    DEFAULT_MODEL = "claude-sonnet-4-6"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        usage_writer: UsageWriter | None = None,
    ) -> None:
        resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._model = model
        self._usage_writer: UsageWriter = usage_writer or _noop_usage_writer
        self._client = self._build_client(resolved_key)

    def _build_client(self, api_key: str) -> Any:
        import logging

        import anthropic
        client = anthropic.AsyncAnthropic(api_key=api_key)
        logging.getLogger(__name__).info(
            "Anthropic client initialized: anthropic==%s", anthropic.__version__
        )
        return client

    def _to_anthropic_messages(self, messages: list[LLMMessage]) -> list[dict[str, Any]]:
        result = []
        for msg in messages:
            if msg.role == "system":
                continue
            if msg.role == "tool":
                result.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.tool_call_id or "",
                        "content": msg.content,
                    }],
                })
            elif msg.content_blocks:
                result.append({"role": msg.role, "content": msg.content_blocks})
            else:
                result.append({"role": msg.role, "content": msg.content})
        return result

    def _extract_system(self, messages: list[LLMMessage], prompt_cache: bool) -> Any:
        system_msgs = [msg for msg in messages if msg.role == "system"]
        if not system_msgs:
            return None

        # If any system message carries explicit content_blocks, forward them directly.
        # This supports the 3-block prompt-caching pattern (T-008) where cache_control
        # is already embedded in each block.
        all_blocks: list[dict[str, Any]] = []
        for msg in system_msgs:
            if msg.content_blocks:
                # Filter out empty text blocks to avoid empty-string API errors
                all_blocks.extend(
                    b for b in msg.content_blocks
                    if not (b.get("type") == "text" and not b.get("text", "").strip())
                )
            elif msg.content:
                block: dict[str, Any] = {"type": "text", "text": msg.content}
                if prompt_cache:
                    block["cache_control"] = {"type": "ephemeral"}
                all_blocks.append(block)

        if not all_blocks:
            return None

        # If there is only a single plain-text block with no cache_control and
        # prompt_cache is False, return a simple string for backwards compatibility.
        if (
            len(all_blocks) == 1
            and all_blocks[0].get("type") == "text"
            and "cache_control" not in all_blocks[0]
            and not prompt_cache
        ):
            return all_blocks[0]["text"]

        return all_blocks

    def _to_anthropic_tools(self, tools: list[LLMToolSpec]) -> list[dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            }
            for t in tools
        ]

    def _compute_cost(self, usage: Any) -> Decimal:
        input_cost = Decimal(str(usage.input_tokens)) * Decimal("0.000003")
        output_cost = Decimal(str(usage.output_tokens)) * Decimal("0.000015")
        cache_read_raw = getattr(usage, "cache_read_input_tokens", 0) or 0
        cache_write_raw = getattr(usage, "cache_creation_input_tokens", 0) or 0
        cache_read_cost = Decimal(str(cache_read_raw)) * Decimal("0.0000003")
        cache_write_cost = Decimal(str(cache_write_raw)) * Decimal("0.00000375")
        return input_cost + output_cost + cache_read_cost + cache_write_cost

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
        import anthropic

        system = self._extract_system(messages, prompt_cache)
        ant_messages = self._to_anthropic_messages(messages)
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": ant_messages,
        }
        if system is not None:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = self._to_anthropic_tools(tools)

        start = time.monotonic()
        try:
            response = await self._client.messages.create(**kwargs)
        except anthropic.APIError as exc:
            usage_zero = LLMUsage(
                input_tokens=0,
                output_tokens=0,
                total_cost_usd=Decimal("0"),
            )
            await self._usage_writer(
                None, agent_step_id, specialist_role, "anthropic", self._model, usage_zero
            )
            raise exc

        latency_ms = int((time.monotonic() - start) * 1000)

        raw_usage = response.usage
        cache_read = getattr(raw_usage, "cache_read_input_tokens", 0) or 0
        cache_write = getattr(raw_usage, "cache_creation_input_tokens", 0) or 0

        llm_usage = LLMUsage(
            input_tokens=raw_usage.input_tokens,
            output_tokens=raw_usage.output_tokens,
            cache_read_tokens=cache_read,
            cache_write_tokens=cache_write,
            total_cost_usd=self._compute_cost(raw_usage),
        )
        await self._usage_writer(
            None, agent_step_id, specialist_role, "anthropic", self._model, llm_usage
        )

        text_parts = []
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })

        finish_map = {
            "end_turn": "stop",
            "tool_use": "tool_use",
            "max_tokens": "length",
        }
        finish_reason: Literal["stop", "tool_use", "length", "error"] = finish_map.get(
            str(response.stop_reason), "stop"
        )  # type: ignore[assignment]

        return LLMResponse(
            text=" ".join(text_parts),
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=llm_usage,
            model=response.model,
            request_id=response.id,
            latency_ms=latency_ms,
        )

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
        system = self._extract_system(messages, prompt_cache)
        ant_messages = self._to_anthropic_messages(messages)
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": ant_messages,
        }
        if system is not None:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = self._to_anthropic_tools(tools)

        client = self._client

        async def _gen() -> AsyncIterator[LLMStreamEvent]:
            async with client.messages.stream(**kwargs) as stream:
                async for event in stream:
                    yield LLMStreamEvent(event="text_delta", data=str(event))

        return _gen()

    async def embed(
        self,
        texts: list[str],
        model: str = "text-embedding-3-small",
        agent_step_id: UUID | None = None,
    ) -> list[list[float]]:
        return [[0.0] * 1536 for _ in texts]


def create_llm_client(
    usage_writer: UsageWriter | None = None,
) -> ClaudeClient | ScenarioStubClaudeClient:
    if os.environ.get("MOCK_LLM", "").lower() == "true":
        return ScenarioStubClaudeClient()
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set — add it to .env")
    model = os.environ.get("TEST_MODEL") or ClaudeClient.DEFAULT_MODEL
    return ClaudeClient(api_key=api_key, model=model, usage_writer=usage_writer)


class BudgetedClaudeClient:
    def __init__(self, inner: ClaudeClient | ScenarioStubClaudeClient, guard: BudgetGuard) -> None:
        self._inner = inner
        self._guard = guard

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
        response = await self._inner.complete(
            messages=messages,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
            prompt_cache=prompt_cache,
            agent_step_id=agent_step_id,
            specialist_role=specialist_role,
        )
        self._guard.check_and_accumulate(response.usage.total_cost_usd)
        return response

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
        return await self._inner.stream(
            messages=messages,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
            prompt_cache=prompt_cache,
            agent_step_id=agent_step_id,
            specialist_role=specialist_role,
        )

    async def embed(
        self,
        texts: list[str],
        model: str = "text-embedding-3-small",
        agent_step_id: UUID | None = None,
    ) -> list[list[float]]:
        return await self._inner.embed(texts=texts, model=model, agent_step_id=agent_step_id)


PolicyLoader = Callable[[], Awaitable[tuple[Decimal, Decimal]]]


async def create_budgeted_llm_client(
    policy_loader: PolicyLoader,
    usage_writer: UsageWriter | None = None,
) -> BudgetedClaudeClient:
    soft_limit, hard_limit = await policy_loader()
    guard = BudgetGuard(soft_limit_usd=soft_limit, hard_limit_usd=hard_limit)
    inner = create_llm_client(usage_writer=usage_writer)
    return BudgetedClaudeClient(inner=inner, guard=guard)
