from __future__ import annotations

import asyncio
import json
import operator
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Annotated, Any, Callable

import structlog
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from typing_extensions import TypedDict

if TYPE_CHECKING:
    from packages.agent.orchestrator import SpecialistResult, SpecialistTask
    from packages.tools.base import ToolContext

_log = structlog.get_logger(__name__)

_MAX_ITERATIONS = 10
SUMMARY_THRESHOLD = 30
_MAX_TOKENS_WARN_THRESHOLD = 4000
_DEGENERATE_RESPONSE_MIN_LEN = 10


@dataclass
class _LCResponse:
    """Checkpoint-serializable response object for the LangChain path in AgentRuntime."""

    text: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: str = "stop"
    model: str = "langchain"
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost_usd: float = 0.0

    # Adapter so callers using response.usage.input_tokens still work.
    @property
    def usage(self) -> "_LCUsage":
        return _LCUsage(
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            total_cost_usd=self.total_cost_usd,
        )


@dataclass
class _LCUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost_usd: float = 0.0

OutputBuilder = Callable[[dict[str, Any], Any], dict[str, Any]]

_FALLBACK_DEGENERATE = "Could not produce a complete response. Please try again."

# Patterns that indicate a fabricated no-data conclusion when no tools were called.
_FABRICATED_NO_DATA_RE = re.compile(r"\d|no\b|none\b|なし", re.IGNORECASE)


def _rule_based_verify(
    tool_results: list[dict[str, Any]],
    conclusion: str,
) -> str:
    """Rule-based findings verifier — no LLM call.

    Rule 1: No tool calls made AND conclusion contains a number or "no"/"none"/"なし"
            → fabricated data → "blocked"
    Rule 2: Tool calls were made AND conclusion is shorter than _DEGENERATE_RESPONSE_MIN_LEN
            → response too short to be meaningful → "blocked"
    Rule 3: All other cases → "pass"
    """
    has_tool_results = bool(tool_results)
    conclusion_stripped = conclusion.strip()

    if not has_tool_results and _FABRICATED_NO_DATA_RE.search(conclusion_stripped):
        return "blocked"

    if has_tool_results and len(conclusion_stripped) < _DEGENERATE_RESPONSE_MIN_LEN:
        return "blocked"

    return "pass"


def _default_output_builder(name: str) -> OutputBuilder:
    def _build(tool_results: dict[str, Any], response: Any) -> dict[str, Any]:
        text = response.text if response else ""
        output: dict[str, Any] = {"text": text, "specialist": name}
        if tool_results:
            output["tool_results"] = tool_results
        return output

    return _build


# ---------------------------------------------------------------------------
# History compression helper
# ---------------------------------------------------------------------------


async def _summarize_messages(
    messages: list[Any],
    lc_model: Any,
) -> str:
    """Cheap LLM call to summarize a slice of conversation history."""
    from langchain_core.messages import HumanMessage, SystemMessage

    text_content = "\n".join(
        f"{m.role}: {m.content if isinstance(m.content, str) else '[tool call]'}"
        for m in messages
    )
    ai_msg = await lc_model.ainvoke([
        SystemMessage("Summarize this conversation history in 2-3 sentences."),
        HumanMessage(text_content),
    ])
    return str(ai_msg.content)


# ---------------------------------------------------------------------------
# LangGraph state
# ---------------------------------------------------------------------------


class AgentState(TypedDict):
    messages: Annotated[list[Any], operator.add]  # accumulates LLMMessage objects
    response: Any | None  # last LLMResponse; None until first call_model run
    input_tokens: Annotated[int, operator.add]
    output_tokens: Annotated[int, operator.add]
    cost_usd: Annotated[float, operator.add]
    tool_results: Annotated[list[dict[str, Any]], operator.add]
    iteration: int
    status: str  # "running" | "completed" | "error" | "blocked"
    error: str | None
    # HITL state — set by prepare_hitl, consumed by execute_tools
    pending_hitl_approval_id: str | None
    pending_hitl_job_id: str | None
    # History compression — set by compress_history node; call_model prefers this over messages
    # when not None. Uses None sentinel so operator.add accumulation is bypassed.
    compressed_messages: list[Any] | None


# ---------------------------------------------------------------------------
# AgentRuntime
# ---------------------------------------------------------------------------


class AgentRuntime:
    def __init__(
        self,
        name: str,
        role: str,
        llm_client: Any,  # Any: structural match to LLMClient Protocol
        tool_registry: Any,  # Any: structural match to ToolRegistry Protocol
        sse_queue: Any = None,  # Any: asyncio.Queue not generically typeable at runtime
        system_prompt: str | None = None,
        output_builder: OutputBuilder | None = None,
        model_registry: Any = None,  # Any: ModelRegistry | None — lazy import avoids circular dep
    ) -> None:
        self.name = name
        self.role = role
        self._tool_registry = tool_registry
        self._sse_queue = sse_queue
        self._system_prompt = system_prompt or f"You are a {role} specialist."
        self._output_builder: OutputBuilder = output_builder or _default_output_builder(name)
        self._model_registry = model_registry
        self._lc_model: Any = (  # Any: BaseChatModel — avoid langchain_core circular import
            model_registry.get("control") if model_registry is not None else None
        )

    # ------------------------------------------------------------------
    # Node: call_model
    # ------------------------------------------------------------------

    async def _call_model_node(self, state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        from packages.agent.llm import LLMMessage, LLMToolSpec

        llm_tools: list[LLMToolSpec] = (config.get("configurable") or {}).get("llm_tools", [])

        # Prefer compressed_messages when the compress_history node has run
        effective_messages: list[Any] = state.get("compressed_messages") or state["messages"]

        if self._lc_model is None:
            raise RuntimeError("AgentRuntime requires model_registry — _lc_model is not set")

        delays = [1, 4]
        last_exc: Exception | None = None
        response = None

        for attempt in range(3):
            try:
                _log.info(
                    "specialist calling LLM",
                    agent_role=self.role,
                    attempt=attempt,
                    model=getattr(self._lc_model, "model", "langchain"),
                )

                from langchain_core.messages import (
                    AIMessage,
                    HumanMessage,
                    SystemMessage,
                    ToolMessage,
                )

                # Convert LLMMessage list to LangChain message list
                lc_msgs: list[Any] = []
                if self._system_prompt:
                    lc_msgs.append(SystemMessage(self._system_prompt))
                for m in effective_messages:
                    if m.role == "system":
                        lc_msgs.append(
                            SystemMessage(
                                m.content if isinstance(m.content, str) else ""
                            )
                        )
                    elif m.role == "user":
                        lc_msgs.append(
                            HumanMessage(
                                m.content if isinstance(m.content, str) else ""
                            )
                        )
                    elif m.role == "assistant":
                        lc_msgs.append(
                            AIMessage(
                                content=(
                                    m.content if isinstance(m.content, str) else ""
                                )
                            )
                        )
                    elif m.role == "tool":
                        # Extract tool_call_id from content_blocks if available
                        tool_call_id = m.tool_call_id or ""
                        has_blocks = hasattr(m, "content_blocks") and m.content_blocks
                        if not tool_call_id and has_blocks:
                            for block in m.content_blocks:
                                if block.get("type") == "tool_result":
                                    tool_call_id = block.get("tool_use_id", "")
                                    break
                        lc_msgs.append(
                            ToolMessage(
                                content=(
                                    m.content if isinstance(m.content, str) else ""
                                ),
                                tool_call_id=tool_call_id,
                            )
                        )

                # Convert LLMToolSpec list to OpenAI function-format dicts for bind_tools
                tool_dicts = [
                    {
                        "type": "function",
                        "function": {
                            "name": t.name,
                            "description": t.description,
                            "parameters": t.input_schema,
                        },
                    }
                    for t in llm_tools
                ] if llm_tools else []

                bound_model = (
                    self._lc_model.bind_tools(tool_dicts) if tool_dicts else self._lc_model
                )
                ai_msg = await bound_model.ainvoke(lc_msgs)

                # Map AIMessage.tool_calls [{"name", "args", "id"}] → [{"name", "input", "id"}]
                mapped_tool_calls = [
                    {"name": tc["name"], "id": tc["id"], "input": tc.get("args", {})}
                    for tc in (ai_msg.tool_calls or [])
                ]

                usage_meta: dict[str, Any] = getattr(ai_msg, "usage_metadata", {}) or {}

                response = _LCResponse(
                    text=str(ai_msg.content),
                    tool_calls=mapped_tool_calls,
                    finish_reason="tool_use" if mapped_tool_calls else "stop",
                    model=getattr(self._lc_model, "model", "langchain"),
                    input_tokens=int(usage_meta.get("input_tokens", 0)),
                    output_tokens=int(usage_meta.get("output_tokens", 0)),
                )
                break
            except Exception as exc:
                last_exc = exc
                _log.warning(
                    "LLM call attempt failed",
                    agent_role=self.role,
                    attempt=attempt + 1,
                    error=str(exc),
                )
                if attempt < len(delays):
                    await asyncio.sleep(delays[attempt])

        if response is None:
            return {
                "status": "error",
                "error": str(last_exc) if last_exc is not None else "LLM call failed",
                "response": None,
            }

        _log.info(
            "specialist LLM response received",
            agent_role=self.role,
            finish_reason=response.finish_reason,
            tool_call_count=len(response.tool_calls),
            model=response.model,
        )
        if response.output_tokens >= _MAX_TOKENS_WARN_THRESHOLD:
            _log.warning(
                "output_tokens near max_tokens limit — response may be truncated",
                output_tokens=response.output_tokens,
                threshold=_MAX_TOKENS_WARN_THRESHOLD,
                agent_role=self.role,
            )

        # Append the assistant response as content blocks to messages
        new_messages: list[Any] = []
        if response.tool_calls or response.finish_reason == "tool_use":
            content_blocks: list[dict[str, Any]] = []
            if response.text:
                content_blocks.append({"type": "text", "text": response.text})
            for call in response.tool_calls:
                content_blocks.append({
                    "type": "tool_use",
                    "id": call["id"],
                    "name": call["name"],
                    "input": call.get("input", {}),
                })
            new_messages.append(LLMMessage(
                role="assistant", content=response.text, content_blocks=content_blocks
            ))

        return {
            "response": response,
            "messages": new_messages,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "cost_usd": float(response.usage.total_cost_usd),
            "iteration": state["iteration"] + 1,
            "status": "running",
        }

    # ------------------------------------------------------------------
    # Conditional edge: should_continue
    # ------------------------------------------------------------------

    def _should_continue(self, state: AgentState) -> str:
        response = state.get("response")
        if response is None:
            return "verify_findings"
        if state["iteration"] >= _MAX_ITERATIONS:
            _log.warning(
                "max iterations reached — forcing verify_findings",
                agent_role=self.role,
                iteration=state["iteration"],
            )
            return "verify_findings"
        # Detect duplicate tool calls — force verify_findings to break the loop
        seen_tool_names: list[str] = []
        for tr in (state.get("tool_results") or []):
            seen_tool_names.extend(tr.keys())
        if len(seen_tool_names) != len(set(seen_tool_names)):
            _log.warning(
                "duplicate tool call detected — forcing verify_findings",
                agent_role=self.role,
                seen_tools=seen_tool_names,
            )
            return "verify_findings"
        if not response.tool_calls or response.finish_reason == "stop":
            return "verify_findings"
        # Check if any pending HITL approval needs processing
        if state.get("pending_hitl_approval_id") is not None:
            return "prepare_hitl"
        # Check if first tool call is HITL
        for call in response.tool_calls:
            tool = self._tool_registry.get(call["name"])
            if tool is not None and getattr(tool, "safety_level", None) == "hitl":
                return "prepare_hitl"
        return "execute_tools"

    # ------------------------------------------------------------------
    # Node: prepare_hitl
    # ------------------------------------------------------------------

    async def _prepare_hitl_node(
        self, state: AgentState, config: RunnableConfig
    ) -> dict[str, Any]:
        """Create DB rows for HITL approval and job. No interrupt here — only side effects."""
        from uuid import UUID as _UUID
        from uuid import uuid4 as _uuid4

        from packages.persistence.approvals_repo import ApprovalsRepository

        sse_queue = (config.get("configurable") or {}).get("sse_queue")
        ctx: ToolContext = (config.get("configurable") or {})["ctx"]

        response = state.get("response")
        if response is None or not response.tool_calls:
            return {}

        # Find the first HITL tool call
        hitl_call: dict[str, Any] | None = None
        for call in response.tool_calls:
            tool = self._tool_registry.get(call["name"])
            if tool is not None and getattr(tool, "safety_level", None) == "hitl":
                hitl_call = call
                break

        if hitl_call is None:
            return {}

        tool_input = hitl_call.get("input", {})

        # Create approval row (DB side effect — safe here, not in wait_for_approval)
        _repo = ApprovalsRepository()
        try:
            created = await _repo.create({
                "session_id": str(ctx.session_id),
                "status": "pending",
                "actor": getattr(ctx, "actor", "orchestrator"),
                "reason": f"HITL tool: {hitl_call['name']}",
            })
            _approval_id = str(created.get("id", _uuid4()))
        except Exception:
            _approval_id = str(_uuid4())

        _job_id: str | None = None
        _job_description: str = ""
        if hitl_call["name"] == "job_dispatch":
            from packages.persistence.jobs_repo import JobsRepository as _JobsRepo
            _jr = _JobsRepo()
            try:
                _job = await _jr.create(
                    session_id=ctx.session_id,
                    job_type=tool_input.get("job_type", "unknown"),
                    params=tool_input.get("params", {}),
                    approval_id=_UUID(_approval_id),
                )
                _job_id = str(_job["id"])
            except Exception:
                pass
            _job_description = tool_input.get("description", "")

        # Emit awaiting_approval SSE event (informs session_orchestrator catch block is gone)
        if sse_queue is not None:
            from packages.agent.orchestrator.parsing import json_safe
            await sse_queue.put(json_safe({
                "type": "awaiting_approval",
                "session_id": str(ctx.session_id),
                "approval_id": _approval_id,
                "tool_name": hitl_call["name"],
                "tool_input": tool_input,
                "job_id": _job_id,
                "description": _job_description,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }))

        return {
            "pending_hitl_approval_id": _approval_id,
            "pending_hitl_job_id": _job_id,
        }

    # ------------------------------------------------------------------
    # Node: wait_for_approval — ZERO DB side effects
    # ------------------------------------------------------------------

    async def _wait_for_approval_node(
        self, state: AgentState, config: RunnableConfig
    ) -> dict[str, Any]:
        """Interrupt graph execution to wait for HITL approval.

        CRITICAL: This node has ZERO DB writes.  LangGraph re-executes a node
        from its beginning when the graph resumes after interrupt().  Any DB write
        inside this node would execute twice.
        """
        sse_queue = (config.get("configurable") or {}).get("sse_queue")
        ctx: ToolContext = (config.get("configurable") or {})["ctx"]

        approval_id = state.get("pending_hitl_approval_id")
        response = state.get("response")
        tool_name: str = ""
        tool_input: dict[str, Any] = {}

        if response is not None and response.tool_calls:
            for call in response.tool_calls:
                tool = self._tool_registry.get(call["name"])
                if tool is not None and getattr(tool, "safety_level", None) == "hitl":
                    tool_name = call["name"]
                    tool_input = call.get("input", {})
                    break

        # Emit session_paused SSE and update session status before interrupting
        if sse_queue is not None:
            from packages.agent.orchestrator.parsing import json_safe
            await sse_queue.put(json_safe({
                "type": "session_paused",
                "session_id": str(ctx.session_id),
                "approval_id": approval_id,
                "tool_name": tool_name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }))

        # interrupt() suspends execution here; resumes when Command(resume=...) is sent
        interrupt({
            "approval_id": approval_id,
            "tool_name": tool_name,
            "tool_input": tool_input,
        })

        # Execution resumes here after approval — graph continues to execute_tools
        return {}

    # ------------------------------------------------------------------
    # Node: execute_tools
    # ------------------------------------------------------------------

    async def _execute_tools_node(
        self, state: AgentState, config: RunnableConfig
    ) -> dict[str, Any]:
        from packages.agent.llm import LLMMessage
        from packages.agent.orchestrator.parsing import json_safe

        configurable = config.get("configurable") or {}
        sse_queue = configurable.get("sse_queue")
        ctx: ToolContext = configurable["ctx"]
        agent_run_id: str = configurable.get("agent_run_id", "")

        response = state.get("response")
        if response is None:
            return {}

        new_messages: list[Any] = []
        new_tool_results: list[dict[str, Any]] = []

        pending_job_id: str | None = state.get("pending_hitl_job_id")

        for call in response.tool_calls:
            tool = self._tool_registry.get(call["name"])
            if tool is None:
                continue

            tool_call_id = call["id"]
            tool_input = call.get("input", {})

            # If this call has an approved HITL job, execute via execute_job (no duplicate rows)
            if (
                pending_job_id is not None
                and getattr(tool, "safety_level", None) == "hitl"
            ):
                from uuid import UUID as _UUID

                from packages.agent.job_executor import execute_job

                tool_t0 = time.monotonic()
                if sse_queue is not None:
                    await sse_queue.put(json_safe({
                        "type": "graph_node", "event": "start",
                        "kind": "tool", "name": call["name"],
                        "run_id": tool_call_id, "parent_run_id": agent_run_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "input_summary": str(tool_input)[:200],
                        "status": "ok", "meta": {},
                    }))
                try:
                    job_result = await execute_job(_UUID(pending_job_id), sse_queue=sse_queue)
                    tool_duration_ms = int((time.monotonic() - tool_t0) * 1000)
                    result_output: dict[str, Any] = job_result.get("result_json") or {}
                    if isinstance(result_output, str):
                        import json as _json
                        result_output = _json.loads(result_output)
                    new_tool_results.append({call["name"]: result_output})
                    if sse_queue is not None:
                        await sse_queue.put(json_safe({
                            "type": "graph_node", "event": "end",
                            "kind": "tool", "name": call["name"],
                            "run_id": tool_call_id, "parent_run_id": agent_run_id,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "duration_ms": tool_duration_ms,
                            "status": "ok", "output": result_output, "meta": {},
                        }))
                    new_messages.append(LLMMessage(
                        role="tool",
                        content=json.dumps(json_safe(result_output)),
                        tool_call_id=call["id"],
                    ))
                except Exception as exc:
                    tool_duration_ms = int((time.monotonic() - tool_t0) * 1000)
                    if sse_queue is not None:
                        await sse_queue.put(json_safe({
                            "type": "graph_node", "event": "end",
                            "kind": "tool", "name": call["name"],
                            "run_id": tool_call_id, "parent_run_id": agent_run_id,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "duration_ms": tool_duration_ms,
                            "status": "error", "error": str(exc), "meta": {},
                        }))
                    raise
                # Clear HITL job id after use
                pending_job_id = None
                continue

            # Normal (non-HITL) tool execution
            tool_t0 = time.monotonic()
            if sse_queue is not None:
                await sse_queue.put(json_safe({
                    "type": "graph_node", "event": "start",
                    "kind": "tool", "name": call["name"],
                    "run_id": tool_call_id, "parent_run_id": agent_run_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "input_summary": str(tool_input)[:200],
                    "status": "ok", "meta": {},
                }))
            try:
                tool_result = await tool.handle(tool_input, ctx)
                tool_duration_ms = int((time.monotonic() - tool_t0) * 1000)
                tool_output = tool_result.output
                executed_query = (
                    tool_output.get("executed_query")
                    if isinstance(tool_output, dict)
                    else None
                )
                new_tool_results.append({call["name"]: tool_output})
                if sse_queue is not None:
                    output_with_query: dict[str, Any] = (
                        {**tool_output, "executed_query": executed_query}
                        if isinstance(tool_output, dict) and executed_query is not None
                        else (tool_output if isinstance(tool_output, dict) else {})
                    )
                    await sse_queue.put(json_safe({
                        "type": "graph_node", "event": "end",
                        "kind": "tool", "name": call["name"],
                        "run_id": tool_call_id, "parent_run_id": agent_run_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "duration_ms": tool_duration_ms,
                        "status": "ok", "output": output_with_query, "meta": {},
                    }))
            except Exception as exc:
                tool_duration_ms = int((time.monotonic() - tool_t0) * 1000)
                if sse_queue is not None:
                    await sse_queue.put(json_safe({
                        "type": "graph_node", "event": "end",
                        "kind": "tool", "name": call["name"],
                        "run_id": tool_call_id, "parent_run_id": agent_run_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "duration_ms": tool_duration_ms,
                        "status": "error", "error": str(exc), "meta": {},
                    }))
                raise

            new_messages.append(LLMMessage(
                role="tool",
                content=json.dumps(json_safe(tool_output)),
                tool_call_id=call["id"],
            ))

        return {
            "messages": new_messages,
            "tool_results": new_tool_results,
            # Clear HITL state after execution
            "pending_hitl_job_id": None,
            "pending_hitl_approval_id": None,
        }

    # ------------------------------------------------------------------
    # Node: verify_findings
    # ------------------------------------------------------------------

    async def _verify_findings_node(
        self, state: AgentState, config: RunnableConfig  # noqa: ARG002
    ) -> dict[str, Any]:
        """Rule-based findings verifier — no LLM call.

        Applies three deterministic rules (see _rule_based_verify) and transitions:
          "pass"    -> END (status = "completed")
          "blocked" -> END (status = "blocked")
        """
        response = state.get("response")
        conclusion = response.text if response is not None else ""
        tool_results: list[dict[str, Any]] = state.get("tool_results") or []

        verify_status = _rule_based_verify(tool_results, conclusion)

        _log.info(
            "verify_findings complete",
            agent_role=self.role,
            verify_status=verify_status,
        )

        if verify_status == "blocked":
            return {"status": "blocked"}

        return {"status": "completed"}

    # ------------------------------------------------------------------
    # Conditional edge after verify_findings
    # ------------------------------------------------------------------

    def _after_verify(self, state: AgentState) -> str:  # noqa: ARG002
        # Rule-based verifier only emits "pass" (completed) or "blocked" — always END.
        return END

    # ------------------------------------------------------------------
    # Node: add_revision_message
    # ------------------------------------------------------------------

    async def _add_revision_message_node(
        self, state: AgentState, config: RunnableConfig
    ) -> dict[str, Any]:
        from packages.agent.llm import LLMMessage

        revision_msg = LLMMessage(
            role="user",
            content=(
                "Your previous response may not be fully grounded in the tool results. "
                "Please review the tool results above and revise your answer, "
                "ensuring every claim is supported by what the tools actually returned."
            ),
        )
        return {
            "messages": [revision_msg],
            "status": "running",
        }

    # ------------------------------------------------------------------
    # Conditional edge after add_revision_message
    # ------------------------------------------------------------------

    def _after_revision(self, state: AgentState) -> str:
        # After revision, go back to call_model then skip verify (one retry only)
        return "call_model_final"

    # ------------------------------------------------------------------
    # Node: call_model_final (retry after needs_revision — no second verify)
    # ------------------------------------------------------------------

    async def _call_model_final_node(
        self, state: AgentState, config: RunnableConfig
    ) -> dict[str, Any]:
        """Retry LLM call after needs_revision. Lightweight degenerate check before returning."""
        result = await self._call_model_node(state, config)
        response = result.get("response")
        final_text = (response.text or "").strip() if response is not None else ""
        if not final_text or len(final_text) < _DEGENERATE_RESPONSE_MIN_LEN:
            _log.warning(
                "call_model_final produced degenerate response — marking blocked",
                agent_role=self.role,
                response_len=len(final_text),
            )
            result["status"] = "blocked"
        else:
            result["status"] = "completed"
        return result

    # ------------------------------------------------------------------
    # Node: compress_history
    # ------------------------------------------------------------------

    async def _compress_history_node(
        self, state: AgentState, config: RunnableConfig  # noqa: ARG002
    ) -> dict[str, Any]:
        """Pre-processing node. When messages exceed SUMMARY_THRESHOLD, replace the
        list with a summary message + the 10 most recent messages.

        Zero LLM calls when len(messages) <= SUMMARY_THRESHOLD.
        """
        messages: list[Any] = state["messages"]
        if len(messages) <= SUMMARY_THRESHOLD:
            return {}  # no-op — do not set compressed_messages

        oldest = messages[:-10]
        recent = messages[-10:]

        _log.info(
            "compress_history: summarising %d messages",
            len(oldest),
            agent_role=self.role,
        )
        summary_text = await _summarize_messages(oldest, self._lc_model)

        from packages.agent.llm import LLMMessage

        summary_message = LLMMessage(
            role="system",
            content=f"[Conversation summary: {summary_text}]",
        )
        return {"compressed_messages": [summary_message] + recent}

    # ------------------------------------------------------------------
    # Build the StateGraph
    # ------------------------------------------------------------------

    def _build_graph(self, checkpointer: Any) -> Any:
        sg: StateGraph = StateGraph(AgentState)  # type: ignore[type-arg]

        sg.add_node("compress_history", self._compress_history_node)
        sg.add_node("call_model", self._call_model_node)
        sg.add_node("prepare_hitl", self._prepare_hitl_node)
        sg.add_node("wait_for_approval", self._wait_for_approval_node)
        sg.add_node("execute_tools", self._execute_tools_node)
        sg.add_node("verify_findings", self._verify_findings_node)

        sg.add_edge(START, "compress_history")
        sg.add_edge("compress_history", "call_model")
        sg.add_conditional_edges(
            "call_model",
            self._should_continue,
            {
                "verify_findings": "verify_findings",
                "execute_tools": "execute_tools",
                "prepare_hitl": "prepare_hitl",
            },
        )
        sg.add_edge("prepare_hitl", "wait_for_approval")
        sg.add_edge("wait_for_approval", "execute_tools")
        sg.add_edge("execute_tools", "call_model")
        sg.add_edge("verify_findings", END)

        return sg.compile(checkpointer=checkpointer)

    # ------------------------------------------------------------------
    # Public run() — preserves existing public interface
    # ------------------------------------------------------------------

    async def run(
        self,
        task: "SpecialistTask",
        ctx: "ToolContext",
        max_iterations: int | None = None,
        checkpointer: Any = None,
        agent_run_id: str = "",
    ) -> "SpecialistResult":
        from packages.agent.llm import LLMMessage, LLMToolSpec
        from packages.agent.orchestrator import SpecialistResult
        from packages.tools.schema_context import get_schema_context

        schema = get_schema_context()

        # T-008: 3-block prompt caching
        system_blocks: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": self._system_prompt,
                "cache_control": {"type": "ephemeral"},
            },
            {
                "type": "text",
                "text": (
                    f"Operational DB schema (use exact column names):\n{schema}" if schema else ""
                ),
                "cache_control": {"type": "ephemeral"},
            },
            {
                "type": "text",
                "text": (
                    f"Role: {self.role}\n"
                    f"Available tools: {len(self._tool_registry.list_for_role(self.role))}\n"
                    "Always respond in the same language the user writes in."
                ),
            },
        ]

        agent_role_tools = self._tool_registry.list_for_role(self.role)
        user_filtered_tools = self._tool_registry.filter_for_user_role(
            ctx.user_role, agent_role_tools
        )
        tool_objects = [
            t for t in user_filtered_tools
            if t.name in set(task.allowed_tools or [])
        ]
        llm_tools = [
            LLMToolSpec(name=t.name, description=t.description, input_schema=t.input_schema)
            for t in tool_objects
        ]

        initial_messages: list[Any] = [
            LLMMessage(role="system", content="", content_blocks=system_blocks),
            LLMMessage(role="user", content=task.instruction),
        ]

        if checkpointer is None:
            checkpointer = MemorySaver()

        import uuid
        thread_id = str(uuid.uuid4())

        graph = self._build_graph(checkpointer)

        run_config: dict[str, Any] = {
            "configurable": {
                "thread_id": thread_id,
                "task": task,
                "ctx": ctx,
                "llm_tools": llm_tools,
                "sse_queue": self._sse_queue,
                "agent_run_id": agent_run_id,
            }
        }

        initial_state: AgentState = {
            "messages": initial_messages,
            "response": None,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
            "tool_results": [],
            "iteration": 0,
            "status": "running",
            "error": None,
            "pending_hitl_approval_id": None,
            "pending_hitl_job_id": None,
            "compressed_messages": None,
        }

        final_state: dict[str, Any] = await graph.ainvoke(initial_state, config=run_config)

        # Reconstruct tool_results dict from the accumulated list of dicts
        merged_tool_results: dict[str, Any] = {}
        for item in final_state.get("tool_results") or []:
            merged_tool_results.update(item)

        last_response = final_state.get("response")
        run_status = final_state.get("status", "completed")

        # Map internal graph status to SpecialistResult status
        specialist_status: str
        if run_status == "completed":
            specialist_status = "completed"
        elif run_status == "blocked":
            specialist_status = "failed"
        elif run_status == "error":
            specialist_status = "failed"
        else:
            specialist_status = "completed"

        # Collect tool_calls_made from context — approximate using step_id repeated per tool result
        tool_calls_made = [ctx.agent_step_id] * len(merged_tool_results)

        # Guard: detect degenerate (too-short) final text responses.
        # Skip when last_response is None or when the final turn ended with tool_use
        # (in which case there is no final assistant text to evaluate).
        final_text = (last_response.text or "").strip() if last_response else ""
        is_degenerate = (
            last_response is not None
            and last_response.finish_reason != "tool_use"
            and bool(final_text)
            and len(final_text) < _DEGENERATE_RESPONSE_MIN_LEN
        )
        if is_degenerate:
            _log.warning(
                "Degenerate LLM response detected — overriding output",
                role=self.role,
                response_len=len(final_text),
                response_preview=final_text,
            )
            specialist_status = "failed"

        output = self._output_builder(merged_tool_results, last_response)
        if is_degenerate:
            if isinstance(output, dict):
                output["text"] = _FALLBACK_DEGENERATE
        if run_status == "blocked":
            if isinstance(output, dict):
                output["text"] = (
                    "Could not verify findings. Please rephrase your question or try again."
                )
        blocked_error = (
            final_state.get("error") or "run blocked by tool-loop guard"
            if run_status == "blocked"
            else final_state.get("error")
        )

        return SpecialistResult(
            task_id=task.task_id,
            output=output,
            tool_calls_made=tool_calls_made,
            status=specialist_status,  # type: ignore[arg-type]
            error=blocked_error,
            usage={
                "input_tokens": final_state.get("input_tokens", 0),
                "output_tokens": final_state.get("output_tokens", 0),
                "cost_usd": final_state.get("cost_usd", 0.0),
            },
        )
