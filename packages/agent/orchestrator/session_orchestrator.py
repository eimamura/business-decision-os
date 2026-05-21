from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Protocol, cast
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from packages.agent.cross_domain import (
    AnomalyDetectorAgent,
    DataEngineerAgent,
    EvaluatorAgent,
    SimulationOptimizerAgent,
)
from packages.knowledge.kpi import (
    KPI_SERVICE_LEVEL,
    KPI_TOTAL_SUPPLY_CHAIN_COST,
    make_stub_kpi_scores,
    weighted_utility,
)
from packages.schemas.recommendation import Candidate, KpiScore, TradeoffExplanation
from packages.tools.guardrail import classify_risk, needs_approval

logger = logging.getLogger(__name__)

ExecutionMode = Literal[
    "direct_chat",
    "single_agent",
    "sequential_agents",
    "planned_execution",
    "dag_execution",
]

_DOMAIN_AGENT_ROLES = {
    "demand",
    "inventory",
    "replenishment",
    "procurement",
    "supplier",
    "production",
    "logistics",
}
_CROSS_DOMAIN_AGENTS: dict[str, type] = {
    "data_engineer": DataEngineerAgent,
    "simulation_optimizer": SimulationOptimizerAgent,
    "evaluator": EvaluatorAgent,
    "anomaly_detector": AnomalyDetectorAgent,
}
_VALID_AGENT_ROLES = _DOMAIN_AGENT_ROLES | set(_CROSS_DOMAIN_AGENTS)

_INTENT_SYSTEM = """\
You are the intent classifier inside SessionOrchestrator for a supply chain
decision system. Return ONLY a JSON object:
{"category": "...", "confidence": 0.0-1.0, "rationale": "...", "goal_text": string|null}

Categories:
- chat: greeting, chitchat, or off-topic
- lookup: factual supply-chain question or data lookup
- domain_analysis: one domain needs analysis
- cross_domain_analysis: several domains or anomaly/root-cause analysis
- decision_support: explicit recommendation, optimization, scenario comparison,
  or approval-oriented decision

Use goal_text only when there is a clear decision or analytical goal.
"""

_ROUTER_SYSTEM = """\
You are the router inside SessionOrchestrator. Return ONLY a JSON object:
{"mode":"...", "agents":["..."], "requires_planning":false, "requires_dag":false, "rationale":"..."}

Modes:
- direct_chat: no agents
- single_agent: exactly one agent
- sequential_agents: two or more agents run in the listed order
- planned_execution: create a serial plan before execution
- dag_execution: create dependency nodes before execution

Allowed agents:
demand, inventory, replenishment, procurement, supplier, production, logistics,
data_engineer, simulation_optimizer, evaluator, anomaly_detector

Default to sequential_agents instead of dag_execution unless the user asks for a
complex dependency-aware workflow or the task clearly needs branching dependencies.
"""

_PLAN_SYSTEM = """\
Create a serial execution plan for SessionOrchestrator. Return ONLY JSON:
{"steps":[{"id":"step-1", "agent_role":"...", "instruction":"...", "tools":[]}]}
Allowed agent_role values are:
demand, inventory, replenishment, procurement, supplier, production, logistics,
data_engineer, simulation_optimizer, evaluator, anomaly_detector.
"""

_DAG_SYSTEM = """\
Create dependency nodes for SessionOrchestrator. Return ONLY a JSON array:
[{"id":"data", "agent_role":"data_engineer", "deps":[], "instruction":"...", "tools":["sql_query"]}]
Allowed agent_role values are:
demand, inventory, replenishment, procurement, supplier, production, logistics,
data_engineer, simulation_optimizer, evaluator, anomaly_detector.
Do not include parallel execution instructions; the initial runtime executes in
topological order.
"""


class SessionUserQuery(BaseModel):
    text: str
    conversation_context: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    weight_override_json: dict[str, Any] | None = None


class SessionIntent(BaseModel):
    category: str
    confidence: float
    rationale: str
    goal_text: str | None = None


class AgentRoute(BaseModel):
    mode: ExecutionMode
    agents: list[str] = Field(default_factory=list)
    requires_planning: bool = False
    requires_dag: bool = False
    rationale: str


class PlanStep(BaseModel):
    id: str
    agent_role: str
    instruction: str
    tools: list[str] = Field(default_factory=list)


class ExecutionPlan(BaseModel):
    steps: list[PlanStep]


class TaskNode(BaseModel):
    id: str
    agent_role: str
    deps: list[str] = Field(default_factory=list)
    instruction: str = ""
    tools: list[str] = Field(default_factory=list)

    @property
    def specialist_type(self) -> str:
        return self.agent_role


class SessionGoal(BaseModel):
    text: str
    weight_override_json: dict[str, Any] | None = None


class SpecialistTask(BaseModel):
    task_id: UUID
    instruction: str
    context_payload: dict[str, Any]
    allowed_tools: list[str]


class SpecialistResult(BaseModel):
    task_id: UUID
    output: dict[str, Any]
    tool_calls_made: list[UUID]
    status: Literal["completed", "failed", "needs_input"]
    error: str | None = None


class SessionResponse(BaseModel):
    mode: ExecutionMode
    reply: str
    intent: SessionIntent
    route: AgentRoute
    agent_results: dict[str, SpecialistResult] = Field(default_factory=dict)
    primary: Candidate | None = None
    alternatives: list[Candidate] = Field(default_factory=list)
    tradeoff: TradeoffExplanation | None = None
    risk_level: Literal["low", "medium", "high"] = "low"
    requires_approval: bool = False


class Orchestrator(Protocol):
    async def run(self, session_id: UUID, query: SessionUserQuery) -> SessionResponse: ...
    async def resume(self, session_id: UUID, approval_id: UUID) -> SessionResponse: ...


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_obj(text: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("no JSON object in LLM response")
    return cast(dict[str, Any], json.loads(match.group()))


def _json_array(text: str) -> list[dict[str, Any]]:
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        raise ValueError("no JSON array in LLM response")
    return cast(list[dict[str, Any]], json.loads(match.group()))


class SessionOrchestrator:
    def __init__(
        self,
        llm_client: Any,
        tool_registry: Any,
        memory_store: Any,
        sse_queue: asyncio.Queue[dict[str, Any]] | None = None,
    ) -> None:
        self._llm_client = llm_client
        self._tool_registry = tool_registry
        self._memory_store = memory_store
        self._sse_queue = sse_queue
        self._sessions: dict[UUID, dict[str, Any]] = {}

    async def _push(self, event: dict[str, Any]) -> None:
        if self._sse_queue is not None:
            await self._sse_queue.put(event)

    def _query_text(self, query: SessionUserQuery) -> str:
        if query.conversation_context:
            return f"[Conversation context: {query.conversation_context}]\n\n{query.text}"
        return query.text

    async def classify_intent(self, query: SessionUserQuery) -> SessionIntent:
        from packages.agent.llm import LLMMessage

        response = await self._llm_client.complete(
            messages=[
                LLMMessage(role="system", content=_INTENT_SYSTEM),
                LLMMessage(role="user", content=self._query_text(query)),
            ],
            tools=None,
            temperature=0.0,
            max_tokens=512,
            prompt_cache=False,
            specialist_role="orchestrator",
        )
        intent = SessionIntent(**_json_obj(response.text))
        await self._push({
            "type": "intent_classified",
            "category": intent.category,
            "confidence": intent.confidence,
            "rationale": intent.rationale,
            "goal_text": intent.goal_text,
            "timestamp": _iso_now(),
        })
        return intent

    async def select_execution_mode(
        self, query: SessionUserQuery, intent: SessionIntent
    ) -> AgentRoute:
        from packages.agent.llm import LLMMessage

        response = await self._llm_client.complete(
            messages=[
                LLMMessage(role="system", content=_ROUTER_SYSTEM),
                LLMMessage(
                    role="user",
                    content=json.dumps(
                        {"query": self._query_text(query), "intent": intent.model_dump()}
                    ),
                ),
            ],
            tools=None,
            temperature=0.0,
            max_tokens=512,
            prompt_cache=False,
            specialist_role="orchestrator",
        )
        route = AgentRoute(**_json_obj(response.text))
        self._validate_route(route)
        await self._push({
            "type": "execution_mode_selected",
            "mode": route.mode,
            "agents": route.agents,
            "requires_planning": route.requires_planning,
            "requires_dag": route.requires_dag,
            "rationale": route.rationale,
            "timestamp": _iso_now(),
        })
        return route

    def _validate_route(self, route: AgentRoute) -> None:
        if route.mode == "direct_chat" and route.agents:
            raise ValueError("direct_chat route must not include agents")
        if route.mode == "single_agent" and len(route.agents) != 1:
            raise ValueError("single_agent route requires exactly one agent")
        if route.mode == "sequential_agents" and len(route.agents) < 1:
            raise ValueError("sequential_agents route requires at least one agent")
        unknown = [agent for agent in route.agents if agent not in _VALID_AGENT_ROLES]
        if unknown:
            raise ValueError(f"unknown agent role(s): {', '.join(unknown)}")

    async def run_direct_chat(
        self, session_id: UUID, query: SessionUserQuery, intent: SessionIntent, route: AgentRoute
    ) -> SessionResponse:
        from packages.agent.llm import LLMMessage

        response = await self._llm_client.complete(
            messages=[
                LLMMessage(
                    role="system",
                    content=(
                        "You are a helpful supply chain decision assistant. Reply briefly "
                        "and naturally in the same language the user writes in. Do not make "
                        "a decision recommendation unless the user asks for one."
                    ),
                ),
                LLMMessage(role="user", content=self._query_text(query)),
            ],
            tools=None,
            temperature=0.0,
            max_tokens=512,
            specialist_role="orchestrator",
        )
        await self._push({"type": "response_ready", "mode": route.mode, "timestamp": _iso_now()})
        self._sessions[session_id]["status"] = "completed"
        return SessionResponse(mode=route.mode, reply=response.text, intent=intent, route=route)

    async def _run_specialist_with_retry(
        self, specialist: Any, task: SpecialistTask, ctx: Any
    ) -> SpecialistResult:
        delays = [1, 4]
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                return cast(SpecialistResult, await specialist.run(task, ctx))
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Agent %s attempt %d failed: %s",
                    getattr(specialist, "role", "?"),
                    attempt + 1,
                    exc,
                )
                if attempt < len(delays):
                    await asyncio.sleep(delays[attempt])
        return SpecialistResult(
            task_id=task.task_id,
            output={},
            tool_calls_made=[],
            status="failed",
            error=str(last_exc),
        )

    def _make_agent(self, agent_role: str) -> Any:
        if agent_role in _CROSS_DOMAIN_AGENTS:
            return _CROSS_DOMAIN_AGENTS[agent_role](
                self._llm_client, self._tool_registry, self._sse_queue
            )
        if agent_role in _DOMAIN_AGENT_ROLES:
            from packages.agent.domain import create_domain_agents

            for agent in create_domain_agents(
                self._llm_client, self._tool_registry, sse_queue=self._sse_queue
            ):
                if agent.role == agent_role:
                    return agent
        raise ValueError(f"unknown agent role: {agent_role}")

    async def _run_agent(
        self,
        session_id: UUID,
        agent_role: str,
        instruction: str,
        context_payload: dict[str, Any],
        allowed_tools: list[str],
    ) -> SpecialistResult:
        from packages.tools.base import ToolContext

        agent = self._make_agent(agent_role)
        task_id = uuid4()
        started_at = _iso_now()
        await self._push({
            "type": "agent_started",
            "agent_name": getattr(agent, "name", agent_role).replace("_", " ").title(),
            "agent_role": agent_role,
            "task_id": str(task_id),
            "started_at": started_at,
            "input_summary": instruction[:200],
        })
        ctx = ToolContext(
            session_id=session_id,
            agent_step_id=task_id,
            specialist_role=agent_role,  # type: ignore[arg-type]
            actor="orchestrator",
            correlation_id=uuid4(),
        )
        task = SpecialistTask(
            task_id=task_id,
            instruction=instruction,
            context_payload=context_payload,
            allowed_tools=allowed_tools,
        )
        t0 = time.monotonic()
        result = await self._run_specialist_with_retry(agent, task, ctx)
        await self._push({
            "type": "agent_completed",
            "agent_name": getattr(agent, "name", agent_role).replace("_", " ").title(),
            "agent_role": agent_role,
            "task_id": str(task_id),
            "duration_ms": int((time.monotonic() - t0) * 1000),
            "output_summary": str(result.output.get("text", ""))[:200] if result.output else None,
            "timestamp": _iso_now(),
        })
        if result.status == "failed":
            await self._push({
                "type": "error",
                "code": "agent_failed",
                "message": f"Agent {agent_role} failed: {result.error}",
                "recoverable": False,
                "timestamp": _iso_now(),
            })
        return result

    async def run_single_agent(
        self, session_id: UUID, query: SessionUserQuery, intent: SessionIntent, route: AgentRoute
    ) -> SessionResponse:
        results = await self._run_agents_in_order(session_id, query, route.agents, intent)
        return await self._synthesize_response(session_id, query, intent, route, results)

    async def run_sequential_agents(
        self, session_id: UUID, query: SessionUserQuery, intent: SessionIntent, route: AgentRoute
    ) -> SessionResponse:
        results = await self._run_agents_in_order(session_id, query, route.agents, intent)
        return await self._synthesize_response(session_id, query, intent, route, results)

    async def _run_agents_in_order(
        self,
        session_id: UUID,
        query: SessionUserQuery,
        agent_roles: list[str],
        intent: SessionIntent,
    ) -> dict[str, SpecialistResult]:
        results: dict[str, SpecialistResult] = {}
        for agent_role in agent_roles:
            context_payload = {
                "query": query.text,
                "conversation_context": query.conversation_context,
                "intent": intent.model_dump(),
                "previous_results": {role: result.output for role, result in results.items()},
            }
            result = await self._run_agent(
                session_id=session_id,
                agent_role=agent_role,
                instruction=intent.goal_text or query.text,
                context_payload=context_payload,
                allowed_tools=self._default_tools(agent_role),
            )
            results[agent_role] = result
        return results

    async def create_execution_plan(
        self, query: SessionUserQuery, intent: SessionIntent, route: AgentRoute
    ) -> ExecutionPlan:
        from packages.agent.llm import LLMMessage

        response = await self._llm_client.complete(
            messages=[
                LLMMessage(role="system", content=_PLAN_SYSTEM),
                LLMMessage(
                    role="user",
                    content=json.dumps(
                        {
                            "query": self._query_text(query),
                            "intent": intent.model_dump(),
                            "route": route.model_dump(),
                        }
                    ),
                ),
            ],
            tools=None,
            temperature=0.0,
            max_tokens=1024,
            prompt_cache=False,
            specialist_role="orchestrator",
        )
        plan = ExecutionPlan(**_json_obj(response.text))
        for step in plan.steps:
            if step.agent_role not in _VALID_AGENT_ROLES:
                raise ValueError(f"unknown agent role in plan: {step.agent_role}")
        await self._push({
            "type": "plan_created",
            "mode": "planned_execution",
            "steps": [s.model_dump() for s in plan.steps],
            "timestamp": _iso_now(),
        })
        return plan

    async def run_planned_execution(
        self, session_id: UUID, query: SessionUserQuery, intent: SessionIntent, route: AgentRoute
    ) -> SessionResponse:
        plan = await self.create_execution_plan(query, intent, route)
        results: dict[str, SpecialistResult] = {}
        for step in plan.steps:
            context_payload = {
                "query": query.text,
                "intent": intent.model_dump(),
                "previous_results": {k: v.output for k, v in results.items()},
            }
            results[step.id] = await self._run_agent(
                session_id, step.agent_role, step.instruction, context_payload, step.tools
            )
        return await self._synthesize_response(session_id, query, intent, route, results)

    async def create_task_nodes(
        self, query: SessionUserQuery, intent: SessionIntent, route: AgentRoute
    ) -> list[TaskNode]:
        from packages.agent.llm import LLMMessage

        response = await self._llm_client.complete(
            messages=[
                LLMMessage(role="system", content=_DAG_SYSTEM),
                LLMMessage(
                    role="user",
                    content=json.dumps(
                        {
                            "query": self._query_text(query),
                            "intent": intent.model_dump(),
                            "route": route.model_dump(),
                        }
                    ),
                ),
            ],
            tools=None,
            temperature=0.0,
            max_tokens=1024,
            prompt_cache=False,
            specialist_role="orchestrator",
        )
        nodes = [TaskNode(**item) for item in _json_array(response.text)]
        for node in nodes:
            if node.agent_role not in _VALID_AGENT_ROLES:
                raise ValueError(f"unknown agent role in DAG: {node.agent_role}")
        await self._push({
            "type": "plan_created",
            "mode": "dag_execution",
            "nodes": [n.model_dump() for n in nodes],
            "timestamp": _iso_now(),
        })
        return nodes

    async def run_dag_execution(
        self, session_id: UUID, query: SessionUserQuery, intent: SessionIntent, route: AgentRoute
    ) -> SessionResponse:
        nodes = await self.create_task_nodes(query, intent, route)
        remaining = {node.id: node for node in nodes}
        completed: dict[str, SpecialistResult] = {}
        while remaining:
            ready = [
                node for node in remaining.values()
                if all(dep in completed for dep in node.deps)
            ]
            if not ready:
                raise ValueError(f"DAG has unresolvable dependencies: {list(remaining)}")
            for node in ready:
                context_payload = {
                    "query": query.text,
                    "intent": intent.model_dump(),
                    "dependency_results": {dep: completed[dep].output for dep in node.deps},
                }
                completed[node.id] = await self._run_agent(
                    session_id,
                    node.agent_role,
                    node.instruction or (intent.goal_text or query.text),
                    context_payload,
                    node.tools,
                )
                del remaining[node.id]
        return await self._synthesize_response(session_id, query, intent, route, completed)

    def _default_tools(self, agent_role: str) -> list[str]:
        if agent_role == "data_engineer":
            return ["sql_query", "nl_query", "forecast"]
        if agent_role == "simulation_optimizer":
            return ["simulate_inventory", "optimize_replenishment"]
        if agent_role == "evaluator":
            return ["evaluate_candidates", "write_audit_log"]
        if agent_role == "anomaly_detector":
            return ["sql_query", "nl_query"]
        return []

    async def _resolve_weights_with_memory(self, goal: SessionGoal) -> tuple[dict[str, float], str]:
        from packages.agent.orchestrator.weights import resolve_weights
        from packages.memory import MemoryQuery

        try:
            results = await self._memory_store.search(
                MemoryQuery(type="user_policy", k=1, min_similarity=0.0, query_text=goal.text)
            )
            if results:
                mem, _score = results[0]
                data = json.loads(mem.content)
                if isinstance(data.get("weights"), dict):
                    return data["weights"], "user_policy"
        except Exception:
            pass
        return resolve_weights(goal)

    async def _write_decision_memory(
        self,
        session_id: UUID,
        goal: SessionGoal,
        weights: dict[str, float],
        weight_source: str,
        risk_level: str,
    ) -> None:
        from packages.memory import Memory

        mem = Memory(
            id=uuid4(),
            scope="global",
            type="user_policy",
            content=json.dumps({
                "goal": goal.text,
                "weights": weights,
                "weight_source": weight_source,
            }),
            metadata={"session_id": str(session_id), "risk_level": risk_level},
            created_at=_iso_now(),
        )
        await self._memory_store.write(mem)

    async def _synthesize_response(
        self,
        session_id: UUID,
        query: SessionUserQuery,
        intent: SessionIntent,
        route: AgentRoute,
        agent_results: dict[str, SpecialistResult],
    ) -> SessionResponse:
        decision_mode = (
            intent.category == "decision_support"
            or route.mode in ("planned_execution", "dag_execution")
            or "simulation_optimizer" in route.agents
            or any("simulation_optimizer" in key for key in agent_results)
        )
        if decision_mode:
            return await self._build_decision_response(
                session_id, query, intent, route, agent_results
            )

        from packages.agent.llm import LLMMessage

        response = await self._llm_client.complete(
            messages=[
                LLMMessage(
                    role="system",
                    content=(
                        "Synthesize the agent results into a concise assistant reply. "
                        "Use the same language as the user. Do not invent raw inventory rows."
                    ),
                ),
                LLMMessage(
                    role="user",
                    content=json.dumps(
                        {
                            "query": query.text,
                            "intent": intent.model_dump(),
                            "agent_results": {k: v.output for k, v in agent_results.items()},
                        }
                    ),
                ),
            ],
            tools=None,
            temperature=0.0,
            max_tokens=1024,
            specialist_role="orchestrator",
        )
        await self._push({"type": "response_ready", "mode": route.mode, "timestamp": _iso_now()})
        self._sessions[session_id]["status"] = "completed"
        return SessionResponse(
            mode=route.mode,
            reply=response.text,
            intent=intent,
            route=route,
            agent_results=agent_results,
        )

    async def _build_decision_response(
        self,
        session_id: UUID,
        query: SessionUserQuery,
        intent: SessionIntent,
        route: AgentRoute,
        agent_results: dict[str, SpecialistResult],
    ) -> SessionResponse:
        raw_candidates: list[dict[str, Any]] = []
        for result in agent_results.values():
            if isinstance(result.output.get("candidates"), list):
                raw_candidates = result.output["candidates"]
                break
            tool_results = result.output.get("tool_results")
            if isinstance(tool_results, dict):
                optimizer_output = tool_results.get("optimize_replenishment")
                if (
                    isinstance(optimizer_output, dict)
                    and isinstance(optimizer_output.get("candidates"), list)
                ):
                    raw_candidates = optimizer_output["candidates"]
                    break

        if raw_candidates:
            candidates = [
                Candidate(
                    id=str(c.get("id", uuid4())),
                    action=c.get("action", {"order_qty": c.get("order_qty")}),
                    kpi_scores=[KpiScore(**s) for s in c.get("kpi_scores", [])]
                    or make_stub_kpi_scores(float(c.get("order_qty", 100.0)), idx),
                    constraints_satisfied=c.get("constraints_satisfied", []),
                    constraints_violated=c.get("constraints_violated", []),
                )
                for idx, c in enumerate(raw_candidates)
            ]
        else:
            moq = 100.0
            candidates = [
                Candidate(
                    id=f"c{idx + 1}",
                    action={"order_qty": moq * (idx + 1)},
                    kpi_scores=make_stub_kpi_scores(moq * (idx + 1), idx),
                    constraints_satisfied=["MOQ"],
                    constraints_violated=[],
                )
                for idx in range(3)
            ]

        goal = SessionGoal(
            text=intent.goal_text or query.text,
            weight_override_json=query.weight_override_json,
        )
        weights, weight_source = await self._resolve_weights_with_memory(goal)
        utilities = [
            (candidate, weighted_utility(candidate.kpi_scores, weights))
            for candidate in candidates
        ]
        utilities.sort(key=lambda item: item[1], reverse=True)
        primary = utilities[0][0]
        others = [candidate for candidate, _ in utilities[1:]]

        alt_service = max(
            others,
            key=lambda c: next((s.value for s in c.kpi_scores if s.name == KPI_SERVICE_LEVEL), 0.0),
            default=None,
        )
        alt_cost = min(
            others,
            key=lambda c: next(
                (s.value for s in c.kpi_scores if s.name == KPI_TOTAL_SUPPLY_CHAIN_COST),
                float("inf"),
            ),
            default=None,
        )
        alternatives: list[Candidate] = []
        seen: set[str] = set()
        for alt in [alt_service, alt_cost, *others]:
            if alt is not None and alt.id not in seen:
                alternatives.append(alt)
                seen.add(alt.id)
            if len(alternatives) >= 2:
                break

        tradeoff = TradeoffExplanation(
            weight_vector=weights,
            weight_source=weight_source,  # type: ignore[arg-type]
            primary_vs_alternative=[
                {
                    "alternative_id": alt.id,
                    "primary_advantage": "higher weighted utility",
                    "alternative_advantage": f"order_qty={alt.action.get('order_qty')}",
                }
                for alt in alternatives
            ],
        )
        risk_level = classify_risk(primary)
        requires_approval = needs_approval(risk_level)
        await self._write_decision_memory(session_id, goal, weights, weight_source, risk_level)

        reply = (
            f"Selected candidate {primary.id} for: {goal.text}\n\n"
            f"Primary action: {primary.action}\n"
            f"Risk level: {risk_level}"
        )
        await self._push({
            "type": "response_ready",
            "mode": route.mode,
            "risk_level": risk_level,
            "requires_approval": requires_approval,
            "timestamp": _iso_now(),
        })
        if requires_approval:
            await self._push({
                "type": "approval_requested",
                "approval_id": str(uuid4()),
                "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
                "risk_level": risk_level,
                "timestamp": _iso_now(),
            })
        else:
            await self._push({
                "type": "auto_executed",
                "recommendation_id": str(uuid4()),
                "timestamp": _iso_now(),
            })

        self._sessions[session_id]["status"] = (
            "awaiting_approval" if requires_approval else "completed"
        )
        return SessionResponse(
            mode=route.mode,
            reply=reply,
            intent=intent,
            route=route,
            agent_results=agent_results,
            primary=primary,
            alternatives=alternatives,
            tradeoff=tradeoff,
            risk_level=risk_level,
            requires_approval=requires_approval,
        )

    async def run(self, session_id: UUID, query: SessionUserQuery) -> SessionResponse:
        if isinstance(query, SessionGoal):
            query = SessionUserQuery(
                text=query.text,
                weight_override_json=query.weight_override_json,
            )

        self._sessions[session_id] = {"status": "active"}
        await self._push({
            "type": "query_received",
            "session_id": str(session_id),
            "timestamp": _iso_now(),
        })

        try:
            intent = await self.classify_intent(query)
            route = await self.select_execution_mode(query, intent)
            if route.mode == "direct_chat":
                return await self.run_direct_chat(session_id, query, intent, route)
            if route.mode == "single_agent":
                return await self.run_single_agent(session_id, query, intent, route)
            if route.mode == "sequential_agents":
                return await self.run_sequential_agents(session_id, query, intent, route)
            if route.mode == "planned_execution":
                return await self.run_planned_execution(session_id, query, intent, route)
            if route.mode == "dag_execution":
                return await self.run_dag_execution(session_id, query, intent, route)
            raise ValueError(f"unknown execution mode: {route.mode}")
        except Exception as exc:
            self._sessions[session_id]["status"] = "failed"
            await self._push({
                "type": "error",
                "code": "orchestration_failed",
                "message": str(exc),
                "recoverable": False,
                "timestamp": _iso_now(),
            })
            raise

    async def resume(self, session_id: UUID, approval_id: UUID) -> SessionResponse:
        query = SessionUserQuery(
            text="Resume the approved decision.",
            metadata={"approval_id": str(approval_id)},
        )
        return await self.run(session_id, query)
