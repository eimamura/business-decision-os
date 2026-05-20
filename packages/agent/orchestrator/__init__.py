from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Literal, Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel

from packages.schemas.recommendation import (
    Candidate,
    KpiScore,
    Recommendation,
    TradeoffExplanation,
)

logger = logging.getLogger(__name__)

_VALID_ROLES = {"domain_expert", "data_engineer", "sim_opt", "evaluator"}
_ALL_ROLES = ["domain_expert", "data_engineer", "sim_opt", "evaluator"]

# Domain specialist roles dispatched in parallel by the Orchestrator
_DOMAIN_SPECIALIST_ROLES = ["forecast", "inventory", "procurement", "production", "cost"]

_ROUTING_SYSTEM = """\
You are a routing agent for a supply chain decision system.
Return ONLY a JSON array of pipeline stages needed to fulfil the goal.

Stages:
- "domain_expert": parallel domain analysis (forecast, inventory, procurement, production, cost)
- "data_engineer": queries operational DB tables via SQL to gather facts
- "sim_opt": runs inventory simulation and replenishment optimisation
- "evaluator": scores each optimiser candidate against all KPIs independently
- "none": conversational input, greetings, or completely off-topic -- no specialists needed

Rules:
1. Simple data lookup (e.g. current inventory, demand history) -> ["data_engineer"]
2. Domain analysis without optimisation -> ["domain_expert", "data_engineer"]
3. Replenishment / optimisation decision -> ["domain_expert", "data_engineer", "sim_opt",
   "evaluator"]
4. "evaluator" requires "sim_opt" -- never include one without the other.
5. Greetings, chit-chat, or off-topic input -> ["none"]

Return ONLY a valid JSON array. No explanation, no markdown, no wrapping text.\
"""


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


def _make_stub_kpi_scores(order_qty: float, idx: int) -> list[KpiScore]:
    service_level = max(0.0, 0.95 - idx * 0.05)
    fill_rate = max(0.0, 0.90 - idx * 0.03)
    stockout_rate = min(1.0, 0.05 + idx * 0.03)
    total_cost = order_qty * 1.2

    return [
        KpiScore(name="service_level", value=service_level, unit="%", direction="higher_better"),
        KpiScore(name="fill_rate", value=fill_rate, unit="%", direction="higher_better"),
        KpiScore(
            name="stockout_rate", value=stockout_rate, unit="%", direction="lower_better"
        ),
        KpiScore(
            name="inventory_turnover",
            value=4.0,
            unit="turns/year",
            direction="higher_better",
        ),
        KpiScore(
            name="days_on_hand",
            value=30.0 + idx * 15,
            unit="days",
            direction="lower_better",
        ),
        KpiScore(
            name="excess_inventory",
            value=max(0.0, order_qty * 0.1 * idx),
            unit="units",
            direction="lower_better",
        ),
        KpiScore(
            name="working_capital",
            value=total_cost * 0.5,
            unit="USD",
            direction="lower_better",
        ),
        KpiScore(
            name="total_supply_chain_cost",
            value=total_cost,
            unit="USD",
            direction="lower_better",
        ),
    ]


def _weighted_utility(kpi_scores: list[KpiScore], weights: dict[str, float]) -> float:
    total = 0.0
    for score in kpi_scores:
        weight = weights.get(score.name, 0.0)
        if score.direction == "higher_better":
            total += weight * score.value
        else:
            max_val = 100.0 if score.unit == "%" else 10000.0
            total += weight * max(0.0, 1.0 - score.value / max_val)
    return total


def _classify_risk(primary: Candidate) -> Literal["low", "medium", "high"]:
    for score in primary.kpi_scores:
        if score.name == "service_level":
            if score.value < 0.85:
                return "high"
            if score.value < 0.95:
                return "medium"
    return "low"


class PhaseOrchestrator:
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

    async def _route_specialists(self, goal: SessionGoal) -> list[str]:
        import json
        import re

        from packages.agent.llm import LLMMessage

        messages = [
            LLMMessage(role="system", content=_ROUTING_SYSTEM),
            LLMMessage(role="user", content=f"Goal: {goal.text}"),
        ]
        try:
            response = await self._llm_client.complete(
                messages=messages,
                tools=None,
                temperature=0.0,
                max_tokens=256,
                prompt_cache=False,
                specialist_role="orchestrator",
            )
            match = re.search(r"\[.*?\]", response.text, re.DOTALL)
            if not match:
                raise ValueError("no JSON array in routing response")
            raw_roles: list[str] = json.loads(match.group())
            if raw_roles == ["none"] or raw_roles == []:
                return []
            roles: list[str] = [r for r in raw_roles if r in _VALID_ROLES]
            if not roles:
                raise ValueError("no valid roles extracted from routing response")
        except Exception as exc:
            logger.warning("Routing failed (%s), falling back to full sequence", exc)
            return list(_ALL_ROLES)

        if "sim_opt" in roles and "evaluator" not in roles:
            roles.append("evaluator")
        if "evaluator" in roles and "sim_opt" not in roles:
            roles.append("sim_opt")

        return [r for r in _ALL_ROLES if r in roles]

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
        await self._push({"type": "memory_retrieved", "count": 0, "timestamp": _iso_now()})

    async def _run_domain_specialists_parallel(
        self,
        session_id: UUID,
        goal: SessionGoal,
    ) -> dict[str, SpecialistResult]:
        from packages.agent.specialists import create_domain_specialists
        from packages.tools.base import ToolContext

        domain_agents = create_domain_specialists(
            self._llm_client, self._tool_registry, sse_queue=self._sse_queue
        )

        async def _run_one(agent: Any) -> tuple[str, SpecialistResult]:
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
            await self._push({
                "type": "specialist_completed",
                "specialist_name": agent.name.replace("_", " ").title(),
                "specialist_role": agent.role,
                "task_id": str(task_id),
                "duration_ms": 0,
                "timestamp": _iso_now(),
            })
            return agent.role, result

        pairs = await asyncio.gather(*[_run_one(a) for a in domain_agents])
        return dict(pairs)

    async def run(self, session_id: UUID, goal: SessionGoal) -> Recommendation:
        from packages.agent.specialists import create_specialists
        from packages.tools.base import ToolContext

        self._sessions[session_id] = {"status": "active"}

        plan_step_id = str(uuid4())
        await self._push({
            "type": "step_started",
            "step_id": plan_step_id,
            "specialist_role": "orchestrator",
            "step_type": "plan",
            "started_at": _iso_now(),
        })

        route_step_id = str(uuid4())
        await self._push({
            "type": "step_started",
            "step_id": route_step_id,
            "specialist_role": "orchestrator",
            "step_type": "routing",
            "started_at": _iso_now(),
        })

        role_sequence = await self._route_specialists(goal)

        await self._push({
            "type": "step_completed",
            "step_id": route_step_id,
            "specialist_role": "orchestrator",
            "step_type": "routing",
            "selected_roles": role_sequence,
            "duration_ms": 0,
        })

        if not role_sequence:
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
                            "planning, and demand forecasting."
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

        # Sequential pipeline specialists (PromptBasedSpecialist — data, sim, eval)
        pipeline_specialists = create_specialists(self._llm_client, self._tool_registry)
        pipeline_tools: dict[str, list[str]] = {
            "data_engineer": ["sql_query", "forecast"],
            "sim_opt": ["simulate_inventory", "optimize_replenishment"],
            "evaluator": ["evaluate_candidates", "write_audit_log"],
        }

        results: dict[str, SpecialistResult] = {}

        # Phase 1 — parallel domain specialist dispatch via AgentBasedSpecialist
        if "domain_expert" in role_sequence:
            domain_results = await self._run_domain_specialists_parallel(session_id, goal)
            results.update(domain_results)

        # Phase 2 — sequential pipeline: data_engineer → sim_opt → evaluator
        for role in [r for r in role_sequence if r != "domain_expert"]:
            specialist = pipeline_specialists[role]
            step_id = str(uuid4())
            task_id = uuid4()

            await self._push({
                "type": "step_started",
                "step_id": step_id,
                "specialist_role": role,
                "step_type": "specialist",
                "started_at": _iso_now(),
            })

            ctx = ToolContext(
                session_id=session_id,
                agent_step_id=task_id,
                specialist_role=role,  # type: ignore[arg-type]
                actor="orchestrator",
                correlation_id=uuid4(),
            )

            task = SpecialistTask(
                task_id=task_id,
                instruction=f"Process decision goal: {goal.text}",
                context_payload={"goal": goal.text, "session_id": str(session_id)},
                allowed_tools=pipeline_tools.get(role, []),
            )

            result = await self._run_specialist_with_retry(specialist, task, ctx)

            if result.status == "failed":
                self._sessions[session_id]["status"] = "failed"
                await self._push({
                    "type": "error",
                    "step_id": step_id,
                    "code": "specialist_failed",
                    "message": f"Specialist {role} failed: {result.error}",
                    "recoverable": False,
                    "timestamp": _iso_now(),
                })

            results[role] = result

            await self._push({
                "type": "step_completed",
                "step_id": step_id,
                "specialist_role": role,
                "duration_ms": 0,
                "output_preview": str(result.output)[:200],
                "tokens": 0,
                "cost_usd": 0.0,
            })

        sim_opt_result = results.get(
            "sim_opt",
            SpecialistResult(task_id=uuid4(), output={}, tool_calls_made=[], status="completed"),
        )
        raw_candidates = sim_opt_result.output.get("candidates", [])

        moq = 100.0
        if not raw_candidates:
            candidates = [
                Candidate(
                    id="c1",
                    action={"order_qty": moq * 1},
                    kpi_scores=_make_stub_kpi_scores(moq * 1, 0),
                    constraints_satisfied=["MOQ"],
                    constraints_violated=[],
                ),
                Candidate(
                    id="c2",
                    action={"order_qty": moq * 2},
                    kpi_scores=_make_stub_kpi_scores(moq * 2, 1),
                    constraints_satisfied=["MOQ"],
                    constraints_violated=[],
                ),
                Candidate(
                    id="c3",
                    action={"order_qty": moq * 3},
                    kpi_scores=_make_stub_kpi_scores(moq * 3, 2),
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

        utilities = [(c, _weighted_utility(c.kpi_scores, weights)) for c in candidates]
        utilities.sort(key=lambda x: x[1], reverse=True)

        primary = utilities[0][0]
        others = [c for c, _ in utilities[1:]]

        alt_service = max(
            others,
            key=lambda c: next(
                (s.value for s in c.kpi_scores if s.name == "service_level"), 0.0
            ),
            default=None,
        )
        alt_cost = min(
            others,
            key=lambda c: next(
                (s.value for s in c.kpi_scores if s.name == "total_supply_chain_cost"),
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

        risk_level = _classify_risk(primary)
        requires_approval = risk_level in ("high", "medium")

        recommendation = Recommendation(
            primary=primary,
            alternatives=alternatives,
            tradeoff=tradeoff,
            rationale=(
                f"Selected candidate {primary.id} based on weighted utility. Goal: {goal.text}"
            ),
            risk_level=risk_level,
            requires_approval=requires_approval,
        )

        await self._write_decision_memory(session_id, goal, weights, weight_source, recommendation)

        recommendation_id = uuid4()
        self._sessions[session_id]["status"] = (
            "awaiting_approval" if requires_approval else "completed"
        )

        auto_execute = not requires_approval

        await self._push({
            "type": "recommendation_ready",
            "recommendation_id": str(recommendation_id),
            "risk_level": risk_level,
            "requires_approval": requires_approval,
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
