from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Literal, Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel

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
from packages.schemas.recommendation import (
    Candidate,
    KpiScore,
    Recommendation,
    TradeoffExplanation,
)
from packages.tools.guardrail import classify_risk, needs_approval

logger = logging.getLogger(__name__)

_VALID_SPECIALIST_TYPES = {
    "domain_expert", "data_engineer", "simulation_optimizer", "evaluator", "anomaly_detector"
}

_CROSS_DOMAIN_AGENTS: dict[str, type] = {
    "data_engineer": DataEngineerAgent,
    "simulation_optimizer": SimulationOptimizerAgent,
    "evaluator": EvaluatorAgent,
    "anomaly_detector": AnomalyDetectorAgent,
}

_PLANNING_SYSTEM = """\
You are a planning agent for a supply chain decision system.
Return ONLY a JSON array of task nodes needed to fulfil the goal.

Each node must have:
- "id": unique string identifier (short, e.g. "domain", "data", "sim", "eval")
- "specialist_type": one of "domain_expert" | "data_engineer" | "simulation_optimizer"
  | "evaluator" | "anomaly_detector"
- "deps": list of node ids that must complete before this node starts ([] for no deps)
- "tools": list of tools this specialist may use

Available specialist types:
- "domain_expert": parallel domain analysis (forecast, inventory, procurement,
  production, cost). tools: []
- "data_engineer": queries operational DB via SQL.
  tools: ["sql_query", "forecast"]
- "simulation_optimizer": runs inventory simulation and replenishment optimisation.
  tools: ["simulate_inventory", "optimize_replenishment"]
- "evaluator": scores each candidate against all KPIs independently.
  tools: ["evaluate_candidates", "write_audit_log"]
- "anomaly_detector": detects anomalies across demand, inventory, procurement,
  production, and logistics. tools: ["sql_query", "nl_query"]

Rules:
1. Simple data lookup -> [data_engineer node, no deps]
2. Domain analysis without optimisation -> domain_expert and data_engineer
   with deps=[] (run in parallel)
3. Replenishment/optimisation -> domain_expert and data_engineer with deps=[]
   (parallel), then simulation_optimizer depending on data_engineer, then
   evaluator depending on simulation_optimizer
4. "evaluator" requires "simulation_optimizer" -- evaluator.deps must include
   simulation_optimizer's id
5. Anomaly detection -> anomaly_detector with deps=[] or after data_engineer
6. Greetings, chit-chat, or off-topic -> []

Return ONLY a valid JSON array of node objects. No explanation, no markdown.\
"""


class TaskNode(BaseModel):
    id: str
    specialist_type: str
    deps: list[str] = []
    tools: list[str] = []


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


class Orchestrator(Protocol):
    async def run(self, session_id: UUID, goal: SessionGoal) -> Recommendation: ...
    async def resume(self, session_id: UUID, approval_id: UUID) -> Recommendation: ...


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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

    async def _run_specialist_with_retry(
        self,
        specialist: Any,
        task: SpecialistTask,
        ctx: Any,
    ) -> SpecialistResult:
        delays = [1, 4]
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                result: SpecialistResult = await specialist.run(task, ctx)
                return result
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Specialist %s attempt %d failed: %s", specialist.role, attempt + 1, exc
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

    async def _plan_execution(self, goal: SessionGoal) -> list[TaskNode]:
        import json
        import re

        from packages.agent.llm import LLMMessage

        messages = [
            LLMMessage(role="system", content=_PLANNING_SYSTEM),
            LLMMessage(role="user", content=f"Goal: {goal.text}"),
        ]
        response = await self._llm_client.complete(
            messages=messages,
            tools=None,
            temperature=0.0,
            max_tokens=512,
            prompt_cache=False,
            specialist_role="orchestrator",
        )
        match = re.search(r"\[.*\]", response.text, re.DOTALL)
        if not match:
            raise ValueError("no JSON array in planning response")
        raw: list[dict[str, Any]] = json.loads(match.group())
        if not raw:
            return []
        nodes = [
            TaskNode(**item) for item in raw
            if item.get("specialist_type") in _VALID_SPECIALIST_TYPES
        ]
        if not nodes:
            raise ValueError("no valid nodes in planning response")

        # Enforce evaluator ↔ sim_opt co-occurrence
        types = {n.specialist_type for n in nodes}
        if "simulation_optimizer" in types and "evaluator" not in types:
            sim_ids = [n.id for n in nodes if n.specialist_type == "simulation_optimizer"]
            nodes.append(TaskNode(
                id="eval", specialist_type="evaluator", deps=sim_ids,
                tools=["evaluate_candidates", "write_audit_log"],
            ))
        if "evaluator" in types and "simulation_optimizer" not in types:
            data_ids = [n.id for n in nodes if n.specialist_type == "data_engineer"]
            nodes.append(TaskNode(
                id="sim", specialist_type="simulation_optimizer", deps=data_ids,
                tools=["simulate_inventory", "optimize_replenishment"],
            ))
            eval_node = next(n for n in nodes if n.specialist_type == "evaluator")
            eval_node.deps = [*eval_node.deps, "sim"]

        return nodes

    async def _run_node(
        self,
        session_id: UUID,
        goal: SessionGoal,
        node: TaskNode,
    ) -> SpecialistResult:
        from packages.tools.base import ToolContext

        if node.specialist_type == "domain_expert":
            domain_results = await self._run_domain_specialists_parallel(session_id, goal)
            merged: dict[str, Any] = {role: r.output for role, r in domain_results.items()}
            all_tool_calls = [tc for r in domain_results.values() for tc in r.tool_calls_made]
            any_failed = any(r.status == "failed" for r in domain_results.values())
            return SpecialistResult(
                task_id=uuid4(),
                output=merged,
                tool_calls_made=all_tool_calls,
                status="failed" if any_failed else "completed",
            )

        agent_cls = _CROSS_DOMAIN_AGENTS[node.specialist_type]
        specialist = agent_cls(self._llm_client, self._tool_registry, self._sse_queue)
        task_id = uuid4()
        ctx = ToolContext(
            session_id=session_id,
            agent_step_id=task_id,
            specialist_role=node.specialist_type,  # type: ignore[arg-type]
            actor="orchestrator",
            correlation_id=uuid4(),
        )
        task = SpecialistTask(
            task_id=task_id,
            instruction=f"Process decision goal: {goal.text}",
            context_payload={"goal": goal.text, "session_id": str(session_id)},
            allowed_tools=node.tools,
        )
        return await self._run_specialist_with_retry(specialist, task, ctx)

    async def _execute_dag(
        self,
        session_id: UUID,
        goal: SessionGoal,
        plan: list[TaskNode],
    ) -> dict[str, SpecialistResult]:
        remaining = {node.id: node for node in plan}
        completed: dict[str, SpecialistResult] = {}

        while remaining:
            ready = [
                node for node in remaining.values()
                if all(dep in completed for dep in node.deps)
            ]
            if not ready:
                logger.error(
                    "DAG execution stuck — possible cycle or unresolvable deps: %s",
                    list(remaining),
                )
                break

            step_t0 = time.monotonic()
            run_results = await asyncio.gather(
                *[self._run_node(session_id, goal, node) for node in ready]
            )
            pairs: list[tuple[TaskNode, SpecialistResult]] = list(zip(ready, run_results))

            for node, result in pairs:
                step_duration_ms = int((time.monotonic() - step_t0) * 1000)
                output_summary = (
                    str(result.output.get("text", ""))[:100] if result.output else None
                )
                await self._push({
                    "type": "step_completed",
                    "step_id": node.id,
                    "specialist_role": node.specialist_type,
                    "duration_ms": step_duration_ms,
                    "output_preview": str(result.output)[:200],
                    "output_summary": output_summary,
                    "tokens": 0,
                    "cost_usd": 0.0,
                    "ended_at": _iso_now(),
                })
                if result.status == "failed":
                    self._sessions[session_id]["status"] = "failed"
                    await self._push({
                        "type": "error",
                        "step_id": node.id,
                        "code": "specialist_failed",
                        "message": (
                            f"Specialist {node.id} ({node.specialist_type})"
                            f" failed: {result.error}"
                        ),
                        "recoverable": False,
                        "timestamp": _iso_now(),
                    })
                completed[node.id] = result
                del remaining[node.id]

        return completed

    async def _resolve_weights_with_memory(
        self, goal: SessionGoal
    ) -> tuple[dict[str, float], str]:
        import json

        from packages.agent.orchestrator.weights import resolve_weights
        from packages.memory import MemoryQuery

        try:
            results = await self._memory_store.search(
                MemoryQuery(type="user_policy", k=1, min_similarity=0.0, query_text=goal.text)
            )
            if results:
                mem, _score = results[0]
                data = json.loads(mem.content)
                if "weights" in data and isinstance(data["weights"], dict):
                    await self._push({
                        "type": "memory_retrieved",
                        "count": len(results),
                        "source": "user_policy",
                        "timestamp": _iso_now(),
                    })
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
        recommendation: "Recommendation",
    ) -> None:
        import json

        from packages.memory import Memory

        mem = Memory(
            id=uuid4(),
            scope="global",
            type="user_policy",
            content=json.dumps({
                "goal": goal.text, "weights": weights, "weight_source": weight_source
            }),
            metadata={"session_id": str(session_id), "risk_level": recommendation.risk_level},
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        await self._memory_store.write(mem)
        await self._push({"type": "memory_written", "timestamp": _iso_now()})

    async def _run_domain_specialists_parallel(
        self,
        session_id: UUID,
        goal: SessionGoal,
    ) -> dict[str, SpecialistResult]:
        from packages.agent.domain import create_domain_agents
        from packages.tools.base import ToolContext

        domain_agents = create_domain_agents(
            self._llm_client, self._tool_registry, sse_queue=self._sse_queue
        )

        async def _run_one(agent: Any) -> tuple[str, SpecialistResult]:
            _run_one_t0 = time.monotonic()
            task_id = uuid4()
            ctx = ToolContext(
                session_id=session_id,
                agent_step_id=task_id,
                specialist_role=agent.role,
                actor="orchestrator",
                correlation_id=uuid4(),
            )
            task = SpecialistTask(
                task_id=task_id,
                instruction=f"Process decision goal: {goal.text}",
                context_payload={"goal": goal.text, "session_id": str(session_id)},
                allowed_tools=[],
            )
            result = await self._run_specialist_with_retry(agent, task, ctx)
            if result.status == "failed":
                self._sessions[session_id]["status"] = "failed"
                await self._push({
                    "type": "error",
                    "code": "specialist_failed",
                    "message": f"Specialist {agent.name} failed: {result.error}",
                    "recoverable": False,
                    "timestamp": _iso_now(),
                })
            specialist_duration_ms = int((time.monotonic() - _run_one_t0) * 1000)
            await self._push({
                "type": "specialist_completed",
                "specialist_name": agent.name.replace("_", " ").title(),
                "specialist_role": agent.role,
                "task_id": str(task_id),
                "duration_ms": specialist_duration_ms,
                "output_summary": (
                    str(result.output.get("text", ""))[:100] if result.output else None
                ),
                "timestamp": _iso_now(),
            })
            return agent.role, result

        pairs = await asyncio.gather(*[_run_one(a) for a in domain_agents])
        return dict(pairs)

    async def run(self, session_id: UUID, goal: SessionGoal) -> Recommendation:
        self._sessions[session_id] = {"status": "active"}

        plan_step_id = str(uuid4())
        plan_started_at = _iso_now()
        plan_t0 = time.monotonic()
        await self._push({
            "type": "step_started",
            "step_id": plan_step_id,
            "specialist_role": "orchestrator",
            "step_type": "planning",
            "started_at": plan_started_at,
            "input_summary": goal.text[:200],
        })

        try:
            execution_plan = await self._plan_execution(goal)
        except Exception as exc:
            self._sessions[session_id]["status"] = "failed"
            await self._push({
                "type": "error",
                "code": "planning_failed",
                "message": f"Failed to generate an execution plan: {exc}",
                "recoverable": False,
                "timestamp": _iso_now(),
            })
            raise
        plan_duration_ms = int((time.monotonic() - plan_t0) * 1000)

        await self._push({
            "type": "execution_plan",
            "plan": [
                {"id": n.id, "specialist_type": n.specialist_type, "deps": n.deps}
                for n in execution_plan
            ],
            "timestamp": _iso_now(),
        })

        await self._push({
            "type": "step_completed",
            "step_id": plan_step_id,
            "specialist_role": "orchestrator",
            "step_type": "planning",
            "node_count": len(execution_plan),
            "duration_ms": plan_duration_ms,
            "ended_at": _iso_now(),
        })

        if not execution_plan:
            from packages.agent.llm import LLMMessage as _LLMMsg
            conv_response = await self._llm_client.complete(
                messages=[
                    _LLMMsg(
                        role="system",
                        content=(
                            "You are a helpful supply chain decision assistant. "
                            "The user sent a conversational message — not a decision request. "
                            "Reply naturally and briefly. You may mention that you can help with "
                            "supply chain decisions such as inventory optimisation, replenishment "
                            "planning, and demand forecasting. "
                            "Always respond in the same language the user writes in."
                        ),
                    ),
                    _LLMMsg(role="user", content=goal.text),
                ],
                tools=None,
                temperature=0.0,
                max_tokens=512,
                specialist_role="orchestrator",
            )
            return Recommendation(
                primary=None,
                alternatives=[],
                tradeoff=None,
                rationale=conv_response.text,
                risk_level="low",
                requires_approval=False,
                direct_reply=conv_response.text,
            )

        node_results = await self._execute_dag(session_id, goal, execution_plan)

        # Find sim_opt result by specialist_type for downstream KPI scoring
        _sim_opt_node = next(
            (n for n in execution_plan if n.specialist_type == "simulation_optimizer"), None
        )
        sim_opt_result = (
            node_results.get(_sim_opt_node.id) if _sim_opt_node is not None else None
        ) or SpecialistResult(task_id=uuid4(), output={}, tool_calls_made=[], status="completed")
        raw_candidates = sim_opt_result.output.get("candidates", [])

        moq = 100.0
        if not raw_candidates:
            candidates = [
                Candidate(
                    id="c1",
                    action={"order_qty": moq * 1},
                    kpi_scores=make_stub_kpi_scores(moq * 1, 0),
                    constraints_satisfied=["MOQ"],
                    constraints_violated=[],
                ),
                Candidate(
                    id="c2",
                    action={"order_qty": moq * 2},
                    kpi_scores=make_stub_kpi_scores(moq * 2, 1),
                    constraints_satisfied=["MOQ"],
                    constraints_violated=[],
                ),
                Candidate(
                    id="c3",
                    action={"order_qty": moq * 3},
                    kpi_scores=make_stub_kpi_scores(moq * 3, 2),
                    constraints_satisfied=["MOQ"],
                    constraints_violated=[],
                ),
            ]
        else:
            candidates = [
                Candidate(
                    id=str(c.get("id", uuid4())),
                    action=c.get("action", {}),
                    kpi_scores=[KpiScore(**s) for s in c.get("kpi_scores", [])],
                    constraints_satisfied=c.get("constraints_satisfied", []),
                    constraints_violated=c.get("constraints_violated", []),
                )
                for c in raw_candidates
            ]

        weights, weight_source = await self._resolve_weights_with_memory(goal)

        utilities = [(c, weighted_utility(c.kpi_scores, weights)) for c in candidates]
        utilities.sort(key=lambda x: x[1], reverse=True)

        primary = utilities[0][0]
        others = [c for c, _ in utilities[1:]]

        alt_service = max(
            others,
            key=lambda c: next(
                (s.value for s in c.kpi_scores if s.name == KPI_SERVICE_LEVEL), 0.0
            ),
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
        seen_ids: set[str] = set()
        for alt in [alt_service, alt_cost]:
            if alt is not None and alt.id not in seen_ids:
                alternatives.append(alt)
                seen_ids.add(alt.id)

        if not alternatives and others:
            alternatives = others[:2]
        elif len(alternatives) < 2 and others:
            for c in others:
                if c.id not in seen_ids:
                    alternatives.append(c)
                    seen_ids.add(c.id)
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
        _approval_pending = needs_approval(risk_level)

        recommendation = Recommendation(
            primary=primary,
            alternatives=alternatives,
            tradeoff=tradeoff,
            rationale=(
                f"Selected candidate {primary.id} based on weighted utility. Goal: {goal.text}"
            ),
            risk_level=risk_level,
            requires_approval=_approval_pending,
        )

        await self._write_decision_memory(session_id, goal, weights, weight_source, recommendation)

        recommendation_id = uuid4()
        self._sessions[session_id]["status"] = (
            "awaiting_approval" if _approval_pending else "completed"
        )

        auto_execute = not _approval_pending

        await self._push({
            "type": "recommendation_ready",
            "recommendation_id": str(recommendation_id),
            "risk_level": risk_level,
            "requires_approval": _approval_pending,
            "auto_execute": auto_execute,
            "timestamp": _iso_now(),
        })

        if auto_execute:
            await self._push({
                "type": "auto_executed",
                "recommendation_id": str(recommendation_id),
                "timestamp": _iso_now(),
            })
        else:
            from datetime import timedelta

            approval_id = str(uuid4())
            expires_at = (datetime.now(timezone.utc) + timedelta(seconds=86400)).isoformat()
            await self._push({
                "type": "awaiting_approval",
                "approval_id": approval_id,
                "recommendation_id": str(recommendation_id),
                "expires_at": expires_at,
                "timestamp": _iso_now(),
            })

        return recommendation

    async def resume(self, session_id: UUID, approval_id: UUID) -> Recommendation:
        goal = SessionGoal(text="resume after approval")
        return await self.run(session_id, goal)
