"""Orchestrator integration tests for the SessionUserQuery entrypoint."""
from __future__ import annotations

import asyncio
from decimal import Decimal
from uuid import uuid4

import pytest

from typing import AsyncIterator

from packages.agent.llm import LLMMessage, LLMResponse, LLMStreamEvent, LLMToolSpec, LLMUsage, StubClaudeClient
from packages.agent.orchestrator import SessionResponse, SessionUserQuery, SessionOrchestrator
from packages.memory import StubMemoryStore
from packages.tools import create_tool_registry


def _response(text: str) -> LLMResponse:
    return LLMResponse(
        text=text,
        tool_calls=[],
        finish_reason="stop",
        usage=LLMUsage(input_tokens=0, output_tokens=0, total_cost_usd=Decimal("0")),
        model="stub",
        request_id=str(uuid4()),
        latency_ms=0,
    )


def _extract_system(messages: list) -> str:
    """Read system text from either plain content or content_blocks (after T-008)."""
    if not messages:
        return ""
    msg = messages[0]
    if not msg.content and msg.content_blocks:
        return msg.content_blocks[0].get("text", "") if msg.content_blocks else ""
    return msg.content or ""


class QueryFlowStubClaudeClient(StubClaudeClient):
    async def complete(self, messages, **kwargs) -> LLMResponse:
        system = _extract_system(messages)
        payload = messages[-1].content if messages else ""
        if "intent classifier" in system:
            if "Good morning" in payload:
                return _response(
                    '{"category":"chat","confidence":0.99,"rationale":"Greeting",'
                    '"goal_text":"general greeting"}'
                )
            return _response(
                '{"category":"decision_support","confidence":0.9,'
                '"rationale":"Needs supply-chain work","goal_text":"Optimize replenishment"}'
            )
        if "router inside SessionOrchestrator" in system:
            if "Good morning" in payload:
                return _response(
                    '{"mode":"direct_chat","agents":[],"requires_planning":false,'
                    '"requires_dag":false,"rationale":"Conversational"}'
                )
            if "single" in payload:
                return _response(
                    '{"mode":"single_agent","agents":["inventory"],"requires_planning":false,'
                    '"requires_dag":false,"rationale":"Inventory only"}'
                )
            if "planned" in payload:
                return _response(
                    '{"mode":"planned_execution","agents":["data_engineer","simulation_optimizer"],'
                    '"requires_planning":true,"requires_dag":false,"rationale":"Needs serial plan"}'
                )
            if "dag" in payload:
                return _response(
                    '{"mode":"dag_execution","agents":["data_engineer","simulation_optimizer"],'
                    '"requires_planning":true,"requires_dag":true,"rationale":"Needs dependencies"}'
                )
            return _response(
                '{"mode":"sequential_agents","agents":["data_engineer","simulation_optimizer"],'
                '"requires_planning":false,"requires_dag":false,"rationale":"Default serial route"}'
            )
        if "Create a serial execution plan" in system:
            return _response(
                '{"steps":['
                '{"id":"data","agent_role":"data_engineer","instruction":"Gather facts","tools":["sql_query"]},'
                '{"id":"sim","agent_role":"simulation_optimizer","instruction":"Create candidates",'
                '"tools":["optimize_replenishment"]}]}'
            )
        if "Create dependency nodes" in system:
            return _response(
                '[{"id":"data","agent_role":"data_engineer","deps":[],"instruction":"Gather facts",'
                '"tools":["sql_query"]},'
                '{"id":"sim","agent_role":"simulation_optimizer","deps":["data"],'
                '"instruction":"Create candidates","tools":["optimize_replenishment"]}]'
            )
        # Specialist agents use content_blocks (T-008); detect by block 0 text
        if "simulation and optimization specialist" in system:
            # Second call: tool result already present — return final text
            if any(getattr(m, "role", "") == "tool" for m in messages):
                return _response("Optimization complete.")
            # First call: invoke optimize_replenishment tool
            return LLMResponse(
                text="",
                tool_calls=[{
                    "id": "call_opt_1",
                    "name": "optimize_replenishment",
                    "input": {"sku_id": "SKU001", "moq": 100.0, "horizon_days": 90},
                }],
                finish_reason="tool_use",
                usage=LLMUsage(
                    input_tokens=0, output_tokens=0, total_cost_usd=Decimal("0")
                ),
                model="stub",
                request_id=str(uuid4()),
                latency_ms=0,
            )
        if "helpful supply chain decision assistant" in system:
            return _response("Good morning! How can I help?")
        if "Synthesize the agent results" in system:
            return _response("Here is the agent summary.")
        return await super().complete(messages, **kwargs)

    async def stream(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolSpec] | None = None,
        **kwargs: object,
    ) -> AsyncIterator[LLMStreamEvent]:
        llm_response = await self.complete(messages, tools=tools, **kwargs)

        async def _gen() -> AsyncIterator[LLMStreamEvent]:
            yield LLMStreamEvent(event="text_delta", data=llm_response.text)

        return _gen()


@pytest.fixture
def stub_orchestrator():
    queue: asyncio.Queue[dict] = asyncio.Queue()
    orchestrator = SessionOrchestrator(
        QueryFlowStubClaudeClient(),
        create_tool_registry(),
        StubMemoryStore(),
        sse_queue=queue,
    )
    return orchestrator, queue


async def _events(queue: asyncio.Queue[dict]) -> list[dict]:
    events: list[dict] = []
    while not queue.empty():
        events.append(await queue.get())
    return events


@pytest.mark.asyncio
async def test_direct_chat_does_not_create_decision(stub_orchestrator):
    orchestrator, queue = stub_orchestrator
    response = await orchestrator.run(uuid4(), SessionUserQuery(text="Good morning!"))

    assert isinstance(response, SessionResponse)
    assert response.mode == "direct_chat"
    assert response.primary is None
    assert response.agent_results == {}
    assert response.reply == "Good morning! How can I help?"
    emitted_types = [event["type"] for event in await _events(queue)]
    # P20: legacy progress events replaced by graph_node events; graph_node end fires after response_ready
    assert "graph_node" in emitted_types
    assert "text_delta" in emitted_types
    assert "response_ready" in emitted_types


@pytest.mark.asyncio
async def test_single_agent_runs_only_selected_agent(stub_orchestrator):
    orchestrator, queue = stub_orchestrator
    response = await orchestrator.run(uuid4(), SessionUserQuery(text="single inventory check"))

    assert response.mode == "single_agent"
    assert list(response.agent_results) == ["inventory"]
    event_types = [event["type"] for event in await _events(queue)]
    # P20: agent_started replaced by graph_node (kind="agent") events
    agent_nodes = [e for e in event_types if e == "graph_node"]
    assert len(agent_nodes) >= 1
    assert "response_ready" in event_types


@pytest.mark.asyncio
async def test_sequential_agents_pass_previous_results(stub_orchestrator):
    orchestrator, _ = stub_orchestrator
    response = await orchestrator.run(uuid4(), SessionUserQuery(text="optimize replenishment"))

    assert response.mode == "sequential_agents"
    assert list(response.agent_results) == ["data_engineer", "simulation_optimizer"]
    assert response.primary is not None
    assert response.tradeoff is not None


@pytest.mark.asyncio
async def test_planned_execution_uses_serial_plan(stub_orchestrator):
    orchestrator, queue = stub_orchestrator
    response = await orchestrator.run(uuid4(), SessionUserQuery(text="planned replenishment"))

    assert response.mode == "planned_execution"
    assert list(response.agent_results) == ["data", "sim"]
    events = await _events(queue)
    # P20: plan_created event removed; plan structure visible via graph_node agent events
    event_types = [e["type"] for e in events]
    assert "graph_node" in event_types
    assert "response_ready" in event_types


@pytest.mark.asyncio
async def test_dag_execution_respects_dependencies(stub_orchestrator):
    orchestrator, _ = stub_orchestrator
    response = await orchestrator.run(uuid4(), SessionUserQuery(text="dag replenishment"))

    assert response.mode == "dag_execution"
    assert list(response.agent_results) == ["data", "sim"]


@pytest.mark.asyncio
async def test_router_bad_json_fails_explicitly(stub_orchestrator):
    orchestrator, queue = stub_orchestrator

    async def _bad_complete(messages, **kwargs):
        system = messages[0].content if messages else ""
        if "intent classifier" in system:
            return _response(
                '{"category":"lookup","confidence":0.9,"rationale":"x","goal_text":null}'
            )
        return _response("not json")

    orchestrator._llm_client.complete = _bad_complete

    with pytest.raises(ValueError, match="no JSON object"):
        await orchestrator.run(uuid4(), SessionUserQuery(text="inventory?"))
    assert any(event["type"] == "error" for event in await _events(queue))
