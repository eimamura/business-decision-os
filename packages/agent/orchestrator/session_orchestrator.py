from __future__ import annotations

import asyncio
import json as _json
import time
from typing import Any, cast
from uuid import UUID, uuid4

import structlog
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from packages.agent.model_registry import ModelRegistry
from packages.agent.orchestrator.ask_user import (
    build_ask_user_event,
    is_analytical_intent,
)
from packages.agent.orchestrator.models import (
    AgentRoute,
    AskUserDecision,
    GoalEvaluation,
    GoalSpec,
    SessionGoal,
    SessionIntent,
    SessionResponse,
    SessionUserQuery,
)
from packages.agent.orchestrator.parsing import (
    LLMResponseParseError,
    _iso_now,
    json_safe,
)
from packages.agent.orchestrator.prompts import (
    ASK_USER_SYSTEM,
    EVALUATE_GOAL_SYSTEM,
    INTENT_SYSTEM,
    SET_GOAL_SYSTEM,
)
from packages.agent.orchestrator.routing import route_after_intent, validate_route
from packages.agent.orchestrator.runtime import (
    _run_agents_in_order,
    _synthesize_response,
    run_direct_chat,
)
from packages.persistence.sessions_repo import DecisionSessionRepository

_log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Typed exception for missing / non-pending checkpoint
# ---------------------------------------------------------------------------


class NoPendingInterruptError(RuntimeError):
    """Raised when a resume call targets a thread that has no LangGraph checkpoint
    or whose most-recent checkpoint has no pending interrupt.

    Callers (routers) should map this to an HTTP 409 response rather than
    treating it as an internal server error.
    """

    def __init__(self, session_id: UUID) -> None:
        super().__init__(
            f"No pending interrupt found for session {session_id} — "
            "the graph checkpoint may have been lost on a server restart. "
            "Re-send your message to start a new run."
        )
        self.session_id = session_id


# ---------------------------------------------------------------------------
# OrchestratorState
# ---------------------------------------------------------------------------


class OrchestratorState(TypedDict):
    session_id: str
    # SessionUserQuery.model_dump() — primitives only for safe checkpoint serialization
    query: dict[str, Any]
    intent: SessionIntent | None
    route: AgentRoute | None
    result: SessionResponse | None
    error: str | None
    ask_user_id: str | None           # UUID set by prepare_ask_user
    ask_user_question: str | None     # question emitted by prepare_ask_user
    ask_user_answer: str | None       # answer injected by wait_for_answer on resume
    # Goal evaluation loop fields
    goal: dict[str, Any] | None       # GoalSpec.model_dump() or None for chat
    goal_eval: dict[str, Any] | None  # GoalEvaluation.model_dump() or None
    refine_count: int                 # number of refinement passes executed (max 1)
    refinement_feedback: str | None   # missing text appended to instruction on refinement


# ---------------------------------------------------------------------------
# Module-level helpers for astream_events
# ---------------------------------------------------------------------------

_ORCHESTRATOR_NODES = frozenset({
    "classify_intent", "set_goal", "prepare_ask_user", "wait_for_answer",
    "select_mode", "run_direct_chat", "run_sequential",
    "evaluate_goal", "refine",
})


def _get_orchestrator_model_name(llm_client: Any) -> str | None:
    """Return the orchestrator-role model name, falling back to the default model."""
    return (
        getattr(llm_client, "_orchestrator_model", None)
        or getattr(llm_client, "_model", None)
    )


def _extract_orch_meta(node_name: str, output: Any) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    if not isinstance(output, dict):
        return meta
    if node_name == "classify_intent":
        intent = output.get("intent")
        if intent is not None:
            d = intent.model_dump() if hasattr(intent, "model_dump") else {}
            meta.update({"category": d.get("category", ""), "confidence": d.get("confidence", 0.0)})
    elif node_name == "select_mode":
        route = output.get("route")
        if route is not None:
            d = route.model_dump() if hasattr(route, "model_dump") else {}
            meta.update({"mode": d.get("mode", ""), "agents": d.get("agents", [])})
    elif node_name == "set_goal":
        goal = output.get("goal")
        if goal is not None:
            meta.update({"goal_text": goal.get("goal_text", "")})
    elif node_name == "evaluate_goal":
        goal_eval = output.get("goal_eval")
        if goal_eval is not None:
            meta.update({
                "satisfied": goal_eval.get("satisfied", True),
                "missing": goal_eval.get("missing"),
            })
    return meta


# ---------------------------------------------------------------------------
# SessionOrchestrator
# ---------------------------------------------------------------------------


class SessionOrchestrator:
    def __init__(
        self,
        llm_client: Any,
        tool_registry: Any,
        memory_store: Any,
        sse_queue: Any | None = None,
        event_persister: Any | None = None,
        checkpoint_pool: Any | None = None,
        model_registry: ModelRegistry | None = None,
    ) -> None:
        self._llm_client = llm_client
        self._tool_registry = tool_registry
        self._memory_store = memory_store
        self._sse_queue = sse_queue
        self._event_persister = event_persister
        self._checkpoint_pool = checkpoint_pool
        self._model_registry = model_registry
        self._graph: Any = None  # lazily initialised by _get_graph()

    async def _push(self, event: dict[str, Any], sse_queue: Any = None) -> None:
        q = sse_queue if sse_queue is not None else self._sse_queue
        safe = json_safe(event)
        if q is not None:
            await q.put(safe)
        if sse_queue is None and self._event_persister is not None:
            await self._event_persister(safe)

    def _query_text(self, query: SessionUserQuery) -> str:
        if query.conversation_context:
            return f"[Conversation context: {query.conversation_context}]\n\n{query.text}"
        return query.text

    def _schedule_status_update(self, session_id: UUID | str, status: str) -> None:
        """Fire-and-forget DB status update; logs a warning on failure."""
        sid = str(session_id)

        async def _persist() -> None:
            try:
                await DecisionSessionRepository().update_status(sid, status)
            except Exception as exc:
                _log.warning(
                    "session status update failed",
                    target_status=status,
                    session_id=sid,
                    error=str(exc),
                )

        asyncio.create_task(_persist())

    async def classify_intent(self, query: SessionUserQuery, session_id: UUID) -> SessionIntent:
        from langchain_core.messages import HumanMessage, SystemMessage

        from packages.persistence.agent_steps_repo import make_step

        step_id = await make_step(str(session_id), "intent_classification")
        model = self._model_registry.get("orchestrator")  # type: ignore[union-attr]
        result = await model.with_structured_output(SessionIntent).ainvoke(
            [SystemMessage(INTENT_SYSTEM), HumanMessage(self._query_text(query))],
            config={
                "metadata": {
                    "session_id": str(session_id),
                    "agent_step_id": str(step_id) if step_id else None,
                    "specialist_role": "orchestrator",
                }
            },
        )
        return result  # type: ignore[return-value]

    async def select_execution_mode(
        self, query: SessionUserQuery, intent: SessionIntent, session_id: UUID
    ) -> AgentRoute:
        from packages.persistence.agent_steps_repo import make_step

        _ = await make_step(str(session_id), "routing")
        mode = route_after_intent(intent)
        agents: list[str] = ["control"] if mode == "single_agent" else []
        route = AgentRoute(
            mode=mode,  # type: ignore[arg-type]
            agents=agents,
            requires_planning=False,
            requires_dag=False,
            rationale=f"Deterministic route for intent '{intent.category}'",
        )
        self._validate_route(route)
        return route

    def _validate_route(self, route: AgentRoute) -> None:
        validate_route(route)

    # ------------------------------------------------------------------
    # Graph nodes
    # ------------------------------------------------------------------

    async def _node_classify_intent(
        self, state: OrchestratorState, config: RunnableConfig
    ) -> dict[str, Any]:
        raw_session_id = state.get("session_id")
        if not raw_session_id:
            raise RuntimeError(
                "graph state missing session_id — resumed without checkpoint? "
                "Use has_pending_interrupt() before calling answer_ask_user() or resume()."
            )
        session_id = UUID(raw_session_id)
        query = SessionUserQuery.model_validate(state["query"])
        intent = await self.classify_intent(query, session_id)
        return {"intent": intent}

    async def _node_set_goal(
        self, state: OrchestratorState, config: RunnableConfig
    ) -> dict[str, Any]:
        """Derive GoalSpec for non-chat intents via one structured-output call.

        Fail-open: on any exception, use GoalSpec(goal_text=query_text,
        success_criteria=[]) so the rest of the graph always gets a valid goal dict.
        Chat intent: return goal=None and pass through without an LLM call.
        """
        from langchain_core.messages import HumanMessage, SystemMessage

        intent = state.get("intent")
        if intent is None or intent.category == "chat":
            return {"goal": None}

        raw_session_id = state.get("session_id")
        query = SessionUserQuery.model_validate(state["query"])
        user_content = self._query_text(query)
        try:
            model = self._model_registry.get("orchestrator")  # type: ignore[union-attr]
            result = await model.with_structured_output(GoalSpec).ainvoke(
                [SystemMessage(SET_GOAL_SYSTEM), HumanMessage(user_content)],
                config={
                    "metadata": {
                        "session_id": raw_session_id,
                        "agent_step_id": None,
                        "specialist_role": "orchestrator",
                    }
                },
            )
            goal_spec = cast(GoalSpec, result)
        except Exception as exc:
            _log.warning(
                "set_goal structured-output failed — using fail-open GoalSpec",
                error=str(exc),
            )
            goal_spec = GoalSpec(goal_text=query.text, success_criteria=[])

        return {"goal": goal_spec.model_dump()}

    async def _node_prepare_ask_user(
        self, state: OrchestratorState, config: RunnableConfig
    ) -> dict[str, Any]:
        """LLM call + SSE emission. Side effects allowed here (before interrupt())."""
        intent = state.get("intent")
        if intent is None or not is_analytical_intent(intent.category):
            return {}

        session_id = UUID(state["session_id"])
        query = SessionUserQuery.model_validate(state["query"])

        user_content = _json.dumps({
            "query": query.text,
            "conversation_context": query.conversation_context,
            "intent": intent.model_dump(),
        })

        from langchain_core.messages import HumanMessage, SystemMessage

        model = self._model_registry.get("orchestrator")  # type: ignore[union-attr]
        decision = await model.with_structured_output(AskUserDecision).ainvoke(
            [SystemMessage(ASK_USER_SYSTEM), HumanMessage(user_content)],
            config={
                "metadata": {
                    "session_id": str(session_id),
                    "agent_step_id": None,
                    "specialist_role": "orchestrator",
                }
            },
        )
        needs_input: bool = decision.needs_input  # type: ignore[union-attr]
        question: str | None = decision.question  # type: ignore[union-attr]
        raw_suggestions: list[str] = decision.suggestions or []  # type: ignore[union-attr]

        if not needs_input or not question:
            return {}

        suggestions: list[str] = raw_suggestions[:3]
        ask_user_id = str(uuid4())
        event = build_ask_user_event(session_id, question, ask_user_id, suggestions)
        await self._push(event)

        self._schedule_status_update(session_id, "awaiting_input")

        return {"ask_user_id": ask_user_id, "ask_user_question": question}

    async def _node_wait_for_answer(
        self, state: OrchestratorState, config: RunnableConfig
    ) -> dict[str, Any]:
        """Zero DB side effects — calls interrupt() only."""
        if not state.get("ask_user_id"):
            return {}  # non-analytical intent — pass through

        from langgraph.types import interrupt

        answer = interrupt({
            "ask_user_id": state["ask_user_id"],
            "question": state["ask_user_question"],
        })
        answer_text: str = ""
        if isinstance(answer, dict):
            answer_text = answer.get("answer", "")
        elif isinstance(answer, str):
            answer_text = answer
        return {"ask_user_answer": answer_text}

    async def _node_select_mode(
        self, state: OrchestratorState, config: RunnableConfig
    ) -> dict[str, Any]:
        session_id = UUID(state["session_id"])
        intent = state["intent"]
        assert intent is not None

        query = SessionUserQuery.model_validate(state["query"])
        if state.get("ask_user_answer"):
            query = SessionUserQuery(
                text=query.text,
                conversation_context=f"User answered: {state['ask_user_answer']}",
                weight_override_json=query.weight_override_json,
            )

        route = await self.select_execution_mode(query, intent, session_id)
        return {"route": route}

    async def _node_run_direct_chat(
        self, state: OrchestratorState, config: RunnableConfig
    ) -> dict[str, Any]:
        session_id = UUID(state["session_id"])
        intent = state["intent"]
        route = state["route"]
        assert intent is not None
        assert route is not None

        _query = SessionUserQuery.model_validate(state["query"])
        result = await run_direct_chat(self, session_id, _query, intent, route)
        self._schedule_status_update(session_id, "completed")
        return {"result": result}

    async def _node_run_sequential(
        self, state: OrchestratorState, config: RunnableConfig
    ) -> dict[str, Any]:
        session_id = UUID(state["session_id"])
        intent = state["intent"]
        route = state["route"]
        assert intent is not None
        assert route is not None

        _query = SessionUserQuery.model_validate(state["query"])

        # Inject refinement feedback into intent.goal_text so _run_agents_in_order
        # picks it up as the instruction (planning.py uses `intent.goal_text or query.text`).
        refinement_feedback = state.get("refinement_feedback")
        if refinement_feedback:
            base = intent.goal_text or _query.text
            augmented_intent = SessionIntent(
                category=intent.category,
                confidence=intent.confidence,
                rationale=intent.rationale,
                goal_text=f"{base}\n\nAdditional guidance: {refinement_feedback}",
            )
        else:
            augmented_intent = intent

        results = await _run_agents_in_order(
            self, session_id, _query, route.agents, augmented_intent
        )
        result = await _synthesize_response(
            self, session_id, _query, augmented_intent, route, results
        )
        await self._push({"type": "response_ready", "mode": route.mode, "timestamp": _iso_now()})
        self._schedule_status_update(session_id, "completed")
        return {"result": result}

    async def _node_evaluate_goal(
        self, state: OrchestratorState, config: RunnableConfig
    ) -> dict[str, Any]:
        """Evaluate whether run_sequential's result satisfies the goal.

        Gated to: non-chat intent AND goal present AND non-empty reply.
        Fail-open: on any exception, treat as satisfied=True to avoid blocking the answer.
        """
        from langchain_core.messages import HumanMessage, SystemMessage

        intent = state.get("intent")
        goal = state.get("goal")
        result = state.get("result")

        # Skip evaluation for chat, or if no goal was derived, or if reply is empty.
        if intent is None or intent.category == "chat" or not goal or not result:
            return {"goal_eval": None}
        if not result.reply.strip():
            return {"goal_eval": None}

        user_content = _json.dumps({
            "goal_text": goal.get("goal_text", ""),
            "success_criteria": goal.get("success_criteria", []),
            "reply": result.reply,
        })

        raw_session_id = state.get("session_id")
        try:
            model = self._model_registry.get("orchestrator")  # type: ignore[union-attr]
            verdict = await model.with_structured_output(GoalEvaluation).ainvoke(
                [SystemMessage(EVALUATE_GOAL_SYSTEM), HumanMessage(user_content)],
                config={
                    "metadata": {
                        "session_id": raw_session_id,
                        "agent_step_id": None,
                        "specialist_role": "orchestrator",
                    }
                },
            )
            goal_eval_obj = cast(GoalEvaluation, verdict)
        except Exception as exc:
            _log.warning(
                "evaluate_goal structured-output failed — failing open as satisfied",
                error=str(exc),
            )
            goal_eval_obj = GoalEvaluation(satisfied=True)

        return {"goal_eval": goal_eval_obj.model_dump()}

    async def _node_refine(
        self, state: OrchestratorState, config: RunnableConfig
    ) -> dict[str, Any]:
        """Prepare for a single refinement pass back through run_sequential.

        - Increments refine_count.
        - Stores the evaluator's missing text as refinement_feedback (picked up by
          _node_run_sequential to augment the instruction).
        - If reroute_category names a valid, different non-chat INTENT_REGISTRY category,
          replaces state["intent"].category (keeps confidence/rationale, notes re-route).
        """
        from packages.agent.orchestrator.intent_registry import INTENT_REGISTRY
        from packages.agent.orchestrator.routing import _INTENT_MODE_MAP

        intent = state.get("intent")
        goal_eval = state.get("goal_eval") or {}
        refine_count = state.get("refine_count") or 0

        missing = goal_eval.get("missing") or ""
        reroute_category = goal_eval.get("reroute_category")

        updates: dict[str, Any] = {
            "refine_count": refine_count + 1,
            "refinement_feedback": missing if missing else None,
        }

        # Apply reroute if the category is valid, different, and non-chat.
        if (
            reroute_category
            and reroute_category != "chat"
            and reroute_category in INTENT_REGISTRY
            and intent is not None
            and reroute_category != intent.category
        ):
            new_mode = _INTENT_MODE_MAP.get(reroute_category, "single_agent")
            reroute_note = (
                f" [re-routed from {intent.category} to {reroute_category} by goal evaluator]"
            )
            updates["intent"] = SessionIntent(
                category=reroute_category,
                confidence=intent.confidence,
                rationale=intent.rationale + reroute_note,
                goal_text=intent.goal_text,
            )
            # Also update the route to match the new mode.
            existing_route = state.get("route")
            agents = existing_route.agents if existing_route is not None else ["control"]
            updates["route"] = AgentRoute(
                mode=new_mode,  # type: ignore[arg-type]
                agents=agents,
                requires_planning=False,
                requires_dag=False,
                rationale=f"Re-routed to {reroute_category} by goal evaluator",
            )

        return updates

    # ------------------------------------------------------------------
    # Conditional edges
    # ------------------------------------------------------------------

    def _edge_after_evaluate_goal(self, state: OrchestratorState) -> str:
        """Route after evaluate_goal:
        - satisfied=True OR refine_count >= 1  → END
        - otherwise                             → refine
        """
        goal_eval = state.get("goal_eval") or {}
        refine_count = state.get("refine_count") or 0

        satisfied = goal_eval.get("satisfied", True)
        if satisfied or refine_count >= 1:
            return END
        return "refine"

    def _edge_after_select_mode(self, state: OrchestratorState) -> str:
        route = state.get("route")
        if route is None:
            return END
        mode = route.mode
        if mode == "direct_chat":
            return "run_direct_chat"
        if mode == "single_agent":
            return "run_sequential"
        return END

    # ------------------------------------------------------------------
    # Graph builder
    # ------------------------------------------------------------------

    def _build_graph(self, checkpointer: Any = None) -> Any:
        sg: StateGraph = StateGraph(OrchestratorState)  # type: ignore[type-arg]

        sg.add_node("classify_intent", self._node_classify_intent)
        sg.add_node("set_goal", self._node_set_goal)
        sg.add_node("prepare_ask_user", self._node_prepare_ask_user)
        sg.add_node("wait_for_answer", self._node_wait_for_answer)
        sg.add_node("select_mode", self._node_select_mode)
        sg.add_node("run_direct_chat", self._node_run_direct_chat)
        sg.add_node("run_sequential", self._node_run_sequential)
        sg.add_node("evaluate_goal", self._node_evaluate_goal)
        sg.add_node("refine", self._node_refine)

        sg.add_edge(START, "classify_intent")
        # set_goal runs after classify_intent, before prepare_ask_user.
        # This placement is safe for HITL resume: answer_ask_user uses Command(resume=...)
        # which re-enters at wait_for_answer (LangGraph restores from checkpoint). The
        # graph never replays classify_intent or set_goal on resume.
        sg.add_edge("classify_intent", "set_goal")
        sg.add_edge("set_goal", "prepare_ask_user")
        sg.add_edge("prepare_ask_user", "wait_for_answer")
        sg.add_edge("wait_for_answer", "select_mode")
        sg.add_conditional_edges(
            "select_mode",
            self._edge_after_select_mode,
            {
                "run_direct_chat": "run_direct_chat",
                "run_sequential": "run_sequential",
                END: END,
            },
        )
        sg.add_edge("run_direct_chat", END)
        sg.add_edge("run_sequential", "evaluate_goal")
        sg.add_conditional_edges(
            "evaluate_goal",
            self._edge_after_evaluate_goal,
            {
                "refine": "refine",
                END: END,
            },
        )
        sg.add_edge("refine", "run_sequential")

        return sg.compile(checkpointer=checkpointer)

    async def _get_graph(self) -> Any:
        """Return the compiled graph, building it lazily with a checkpointer.

        When DATABASE_URL is set, uses AsyncPostgresSaver backed by an
        AsyncConnectionPool so that checkpoint state persists across HTTP
        requests (required for cross-request HITL resume).

        Falls back to MemorySaver when DATABASE_URL is absent (unit tests,
        CI without DB).
        """
        if self._graph is not None:
            return self._graph

        import os

        if self._checkpoint_pool is not None:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

            checkpointer: Any = AsyncPostgresSaver(conn=self._checkpoint_pool)
        else:
            database_url = os.environ.get("DATABASE_URL", "")
            if database_url:
                from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
                from psycopg import AsyncConnection
                from psycopg.rows import dict_row
                from psycopg_pool import AsyncConnectionPool

                psycopg_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
                pool: AsyncConnectionPool[AsyncConnection[dict[str, Any]]] = (
                    AsyncConnectionPool(
                        psycopg_url,
                        max_size=5,
                        kwargs={
                            "autocommit": True,
                            "prepare_threshold": 0,
                            "row_factory": dict_row,
                        },
                        open=False,
                    )
                )
                await pool.open()
                checkpointer = AsyncPostgresSaver(conn=pool)
            else:
                from langgraph.checkpoint.memory import MemorySaver

                checkpointer = MemorySaver()

        self._graph = self._build_graph(checkpointer=checkpointer)
        return self._graph

    # ------------------------------------------------------------------
    # Core streaming runner — replaces ainvoke() / astream() calls
    # ------------------------------------------------------------------

    async def _astream_run(
        self, initial_state: Any, config: dict[str, Any]
    ) -> dict[str, Any]:
        """Run the graph via astream_events, emitting graph_node SSE events for
        orchestrator nodes, and return the final state dict.

        Interrupt detection: LangGraph emits the interrupt value in an on_chain_stream
        event (chunk={"__interrupt__": ...}) on the root chain before on_chain_end.
        We capture that here and inject it into final_state so callers can detect it.
        """
        graph = await self._get_graph()
        node_start_times: dict[str, float] = {}
        final_state: dict[str, Any] | None = None
        interrupt_chunk: Any = None

        async for ev in graph.astream_events(initial_state, config=config, version="v2"):
            ev_type: str = ev["event"]
            name: str = ev.get("name", "")
            run_id: str = str(ev.get("run_id", ""))

            # Capture interrupt from root chain stream (fires before on_chain_end on pause)
            if ev_type == "on_chain_stream" and not ev.get("parent_ids"):
                chunk = ev.get("data", {}).get("chunk", {})
                if isinstance(chunk, dict) and "__interrupt__" in chunk:
                    interrupt_chunk = chunk["__interrupt__"]
                continue

            # Capture final state from the root chain end event
            if ev_type == "on_chain_end" and not ev.get("parent_ids"):
                output = ev.get("data", {}).get("output", {})
                if isinstance(output, dict):
                    final_state = output
                continue

            if name not in _ORCHESTRATOR_NODES:
                continue

            if ev_type == "on_chain_start":
                node_start_times[run_id] = time.monotonic()
                await self._push({
                    "type": "graph_node", "event": "start",
                    "kind": "orchestrator", "name": name,
                    "run_id": run_id, "timestamp": _iso_now(),
                    "status": "ok",
                    "meta": {"model_name": _get_orchestrator_model_name(self._llm_client)},
                })
            elif ev_type == "on_chain_end":
                duration_ms = int(
                    (time.monotonic() - node_start_times.pop(run_id, time.monotonic())) * 1000
                )
                meta = _extract_orch_meta(name, ev.get("data", {}).get("output", {}))
                meta["model_name"] = _get_orchestrator_model_name(self._llm_client)
                await self._push({
                    "type": "graph_node", "event": "end",
                    "kind": "orchestrator", "name": name,
                    "run_id": run_id, "timestamp": _iso_now(),
                    "duration_ms": duration_ms, "status": "ok", "meta": meta,
                })

        # LangGraph does not emit on_chain_end for the interrupted node — emit a
        # synthetic end event so the execution trace remains consistent (start/end pairs).
        if interrupt_chunk is not None:
            for orphan_run_id, t0 in node_start_times.items():
                duration_ms = int((time.monotonic() - t0) * 1000)
                await self._push({
                    "type": "graph_node", "event": "end",
                    "kind": "orchestrator", "name": "wait_for_answer",
                    "run_id": orphan_run_id, "timestamp": _iso_now(),
                    "duration_ms": duration_ms, "status": "interrupted",
                    "meta": {"model_name": _get_orchestrator_model_name(self._llm_client)},
                })
            fs: dict[str, Any] = dict(final_state) if isinstance(final_state, dict) else {}
            fs["__interrupt__"] = interrupt_chunk
            return fs

        return final_state or {}

    # ------------------------------------------------------------------
    # Public run()
    # ------------------------------------------------------------------

    def _parse_error_response(
        self, session_id: UUID, exc: LLMResponseParseError
    ) -> SessionResponse:
        reply = exc.raw_text.strip() or "（モデルが応答を返しませんでした）"
        return SessionResponse(
            mode="direct_chat",
            reply=reply,
            intent=SessionIntent(category="unknown", confidence=0.0, rationale="llm_parse_error"),
            route=AgentRoute(mode="direct_chat", rationale="llm_parse_error"),
        )

    # ------------------------------------------------------------------
    # Resume checkpoint guard
    # ------------------------------------------------------------------

    async def has_pending_interrupt(self, session_id: UUID) -> bool:
        """Return True only when the thread has a checkpoint AND a pending interrupt.

        Uses ``graph.aget_state(config)`` to inspect the most-recent checkpoint:
        - No checkpoint (metadata is None): no interrupt possible → False.
        - Checkpoint present but ``state_snapshot.interrupts`` is empty: the graph
          ran to completion or was never paused → False.
        - Checkpoint present AND ``state_snapshot.interrupts`` is non-empty: a
          ``wait_for_answer`` (ask_user) or approval interrupt is pending → True.

        Both the ask_user flow (``wait_for_answer`` node) and the approval flow
        expose their pending interrupt through ``StateSnapshot.interrupts``.
        """
        config: dict[str, Any] = {
            "configurable": {
                "thread_id": str(session_id),
            }
        }
        graph = await self._get_graph()
        snapshot = await graph.aget_state(config)
        if snapshot.metadata is None:
            # Thread has never been checkpointed.
            return False
        return len(snapshot.interrupts) > 0

    async def run(self, session_id: UUID, query: SessionUserQuery) -> SessionResponse:
        if isinstance(query, SessionGoal):
            query = SessionUserQuery(
                text=query.text,
                weight_override_json=query.weight_override_json,
            )

        self._schedule_status_update(session_id, "running")

        initial_state: OrchestratorState = {
            "session_id": str(session_id),
            "query": query.model_dump(),
            "intent": None,
            "route": None,
            "result": None,
            "error": None,
            "ask_user_id": None,
            "ask_user_question": None,
            "ask_user_answer": None,
            "goal": None,
            "goal_eval": None,
            "refine_count": 0,
            "refinement_feedback": None,
        }

        config: dict[str, Any] = {
            "configurable": {
                "thread_id": str(session_id),
                "sse_queue": self._sse_queue,
                "event_persister": self._event_persister,
            },
            # Propagate session_id so callback handlers can attribute LLM calls
            # that fire inside the orchestrator graph to the correct session.
            "metadata": {
                "session_id": str(session_id),
                "agent_step_id": None,
                "specialist_role": "orchestrator",
            },
        }

        try:
            final_state = await self._astream_run(initial_state, config)
        except LLMResponseParseError as exc:
            resp = self._parse_error_response(session_id, exc)
            self._schedule_status_update(session_id, "completed")
            await self._push({
                "type": "done",
                "session_id": str(session_id),
                "reply": resp.reply,
                "timestamp": _iso_now(),
            })
            return resp
        except Exception as exc:
            self._schedule_status_update(session_id, "failed")
            await self._push({
                "type": "error",
                "code": "orchestration_failed",
                "message": str(exc),
                "recoverable": False,
                "timestamp": _iso_now(),
            })
            raise

        # LangGraph stores GraphInterrupt in final_state["__interrupt__"] rather than
        # raising — re-raise so callers can distinguish paused from completed.
        if "__interrupt__" in final_state:
            from langgraph.errors import GraphInterrupt

            raise GraphInterrupt(final_state["__interrupt__"])

        raw_result = final_state.get("result")
        if raw_result is None:
            raise RuntimeError("Orchestrator graph produced no result")
        if not isinstance(raw_result, SessionResponse):
            raise RuntimeError(f"Orchestrator graph returned unexpected type: {type(raw_result)}")

        # Populate goal_evaluation from state when present.
        goal_eval = final_state.get("goal_eval")
        if goal_eval is not None:
            raw_result = raw_result.model_copy(update={"goal_evaluation": goal_eval})

        return raw_result

    async def resume(self, session_id: UUID, approval_id: UUID) -> SessionResponse:
        """Resume graph execution from the last LangGraph checkpoint for this session."""
        if not await self.has_pending_interrupt(session_id):
            raise NoPendingInterruptError(session_id)

        config: dict[str, Any] = {
            "configurable": {
                "thread_id": str(session_id),
                "sse_queue": self._sse_queue,
                "event_persister": self._event_persister,
            },
            "metadata": {
                "session_id": str(session_id),
                "agent_step_id": None,
                "specialist_role": "orchestrator",
            },
        }

        try:
            final_state = await self._astream_run(None, config)
        except LLMResponseParseError as exc:
            resp = self._parse_error_response(session_id, exc)
            self._schedule_status_update(session_id, "completed")
            await self._push({
                "type": "done",
                "session_id": str(session_id),
                "reply": resp.reply,
                "timestamp": _iso_now(),
            })
            return resp
        except Exception as exc:
            self._schedule_status_update(session_id, "failed")
            await self._push({
                "type": "error",
                "code": "orchestration_failed",
                "message": str(exc),
                "recoverable": False,
                "timestamp": _iso_now(),
            })
            raise

        result = final_state.get("result")
        if result is None:
            raise RuntimeError(f"Graph resume produced no result for session {session_id}")
        return cast(SessionResponse, result)

    async def answer_ask_user(self, session_id: UUID, answer: str) -> SessionResponse:
        """Resume a graph paused at wait_for_answer with the user's answer."""
        if not await self.has_pending_interrupt(session_id):
            raise NoPendingInterruptError(session_id)

        from langgraph.types import Command

        config: dict[str, Any] = {
            "configurable": {
                "thread_id": str(session_id),
                "sse_queue": self._sse_queue,
                "event_persister": self._event_persister,
            },
            "metadata": {
                "session_id": str(session_id),
                "agent_step_id": None,
                "specialist_role": "orchestrator",
            },
        }

        try:
            final_state = await self._astream_run(Command(resume={"answer": answer}), config)
        except LLMResponseParseError as exc:
            resp = self._parse_error_response(session_id, exc)
            self._schedule_status_update(session_id, "completed")
            await self._push({
                "type": "done",
                "session_id": str(session_id),
                "reply": resp.reply,
                "timestamp": _iso_now(),
            })
            return resp
        except Exception as exc:
            self._schedule_status_update(session_id, "failed")
            await self._push({
                "type": "error", "code": "ask_user_resume_failed",
                "message": str(exc), "recoverable": False,
                "timestamp": _iso_now(),
            })
            raise

        result = final_state.get("result")
        if result is None:
            raise RuntimeError(f"ask_user resume produced no result for session {session_id}")
        return cast(SessionResponse, result)
