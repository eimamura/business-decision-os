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
from pydantic import BaseModel
from typing_extensions import TypedDict

from packages.tools.audit_tool import AuditLogTool

if TYPE_CHECKING:
    from packages.agent.orchestrator import SpecialistResult, SpecialistTask
    from packages.tools.base import ToolContext

_log = structlog.get_logger(__name__)

_MAX_ITERATIONS = 10

# Intents eligible for the LLM groundedness check (ADR 2026-06-10 §2).
_GROUNDED_VERIFY_INTENTS: frozenset[str] = frozenset(
    {"domain_analysis", "cross_domain_analysis", "decision_support", "supply_chain"}
)

# Maximum length (characters) of a serialized tool result value before truncation.
_TOOL_RESULT_VALUE_TRUNCATE = 500


class GroundednessVerdict(BaseModel):
    """Structured output schema for the LLM groundedness check."""

    grounded: bool
    unsupported_claims: list[str] = []


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

# Patterns that indicate a nil-claim conclusion (used by Rule 1b).
_NIL_CLAIM_RE = re.compile(
    r"\b(no |none|nothing|ない|なし|ゼロ|0件|例外なし|リスクなし)",
    re.IGNORECASE,
)


def _has_non_empty_tool_data(tool_results: list[dict[str, Any]]) -> bool:
    """Return True if any result in tool_results contains data (count > 0 or non-empty items)."""
    for entry in tool_results:
        # Each entry is {tool_name: result_dict}
        for result in entry.values():
            if not isinstance(result, dict):
                continue
            # Check top-level "count" key
            count = result.get("count")
            if isinstance(count, int) and count > 0:
                return True
            # Check top-level "items" key
            items = result.get("items")
            if isinstance(items, list) and len(items) > 0:
                return True
            # Check one level of nesting (e.g. result["data"]["count"])
            for v in result.values():
                if not isinstance(v, dict):
                    continue
                nested_count = v.get("count")
                if isinstance(nested_count, int) and nested_count > 0:
                    return True
                nested_items = v.get("items")
                if isinstance(nested_items, list) and len(nested_items) > 0:
                    return True
    return False


async def _emit(event: dict[str, Any], sse_queue: Any, persister: Any) -> None:
    """Put *event* on the SSE queue and fire-and-forget the persister.

    Both operations are best-effort:
    - ``sse_queue`` may be None (tests, CLI entry points) — skipped silently.
    - ``persister`` may be None or may raise — never propagates an exception so
      that persister failures can never interrupt an agent run.
    """
    from packages.agent.orchestrator.parsing import json_safe as _json_safe

    safe = _json_safe(event)
    if sse_queue is not None:
        await sse_queue.put(safe)
    if persister is not None:
        try:
            await persister(safe)
        except Exception:
            pass  # persister failures must never break the run


_FENCED_CODE_RE = re.compile(r"```[^\n]*\n?.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`]+`")


def _strip_code_from_conclusion(text: str) -> str:
    """Remove fenced code blocks (```...```) and inline code spans (`...`) from *text*.

    Used by Rule 1 so that digits or keywords inside code (e.g. SQL responses)
    do not trigger the fabrication heuristic.  Prose-level digits are unaffected.
    """
    text = _FENCED_CODE_RE.sub("", text)
    text = _INLINE_CODE_RE.sub("", text)
    return text


def _rule_based_verify(
    tool_results: list[dict[str, Any]],
    conclusion: str,
) -> str:
    """Rule-based findings verifier — no LLM call.

    Rule 1:  No tool calls made AND conclusion (with fenced/inline code stripped)
             contains a number or "no"/"none"/"なし"
             → fabricated data → "blocked"
             Code blocks and inline code spans are excluded from the digit/keyword
             scan so that legitimate SQL-writing answers are not blocked stochastically.
             Rules 1b and 2 operate on the original (unstripped) conclusion.
    Rule 1b: Tool calls were made AND any result has count > 0 or non-empty items list
             AND conclusion matches a nil-claim pattern → "blocked"
    Rule 2:  Tool calls were made AND conclusion is shorter than _DEGENERATE_RESPONSE_MIN_LEN
             → response too short to be meaningful → "blocked"
    Rule 3:  All other cases → "pass"
    """
    has_tool_results = bool(tool_results)
    conclusion_stripped = conclusion.strip()

    if not has_tool_results and _FABRICATED_NO_DATA_RE.search(
        _strip_code_from_conclusion(conclusion_stripped)
    ):
        return "blocked"

    if has_tool_results and _has_non_empty_tool_data(tool_results) and _NIL_CLAIM_RE.search(
        conclusion_stripped
    ):
        return "blocked"

    if has_tool_results and len(conclusion_stripped) < _DEGENERATE_RESPONSE_MIN_LEN:
        return "blocked"

    return "pass"


def _truncate_tool_results_for_prompt(
    tool_results: list[dict[str, Any]],
    max_value_len: int = _TOOL_RESULT_VALUE_TRUNCATE,
) -> list[dict[str, Any]]:
    """Return a copy of tool_results with large string values truncated.

    Each entry is ``{tool_name: result_dict}``.  Walks one level of nesting
    and truncates any string value longer than *max_value_len*.
    """
    from packages.agent.orchestrator.parsing import json_safe

    def _trim(val: Any) -> Any:
        if isinstance(val, str) and len(val) > max_value_len:
            return val[:max_value_len] + "…"
        if isinstance(val, dict):
            return {k: _trim(v) for k, v in val.items()}
        if isinstance(val, list):
            # Keep up to 20 items to avoid prompt bloat
            return [_trim(v) for v in val[:20]]
        return val

    safe = json_safe(tool_results)
    return [_trim(entry) for entry in safe]


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


class ToolPlan(TypedDict):
    """A single step in the pre-call tool plan for complex intents."""

    tool: str
    purpose: str
    depends_on: list[str]


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
    # Truthful reason for status="blocked" — set by each blocking site; None otherwise.
    blocked_reason: str | None
    # HITL state — set by prepare_hitl, consumed by execute_tools
    pending_hitl_approval_id: str | None
    pending_hitl_job_id: str | None
    # History compression — set by compress_history node; call_model prefers this over messages
    # when not None. Uses None sentinel so operator.add accumulation is bypassed.
    compressed_messages: list[Any] | None
    # Tool plan — set by plan_tools node for complex intents; empty list means no plan
    tool_plan: list[ToolPlan]
    # Groundedness verdict — set by verify_findings node when LLM check runs; None otherwise.
    groundedness: dict[str, Any] | None
    # Revised flag — set by call_model_final to prevent a second revision cycle.
    revised: bool


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

    # Intents that benefit from pre-call tool planning (complex, multi-step analysis).
    _PLAN_TOOLS_INTENTS: frozenset[str] = frozenset(
        {"domain_analysis", "cross_domain_analysis", "decision_support"}
    )

    async def _plan_tools_node(
        self, state: AgentState, config: RunnableConfig
    ) -> dict[str, Any]:
        """Pre-call tool planning node (Gap 1 — P64).

        Fires only for complex intents (domain_analysis, cross_domain_analysis,
        decision_support). Skips when tool_plan is already populated or when
        the intent is not in _PLAN_TOOLS_INTENTS.

        Asks the LLM to produce a JSON array of ToolPlan objects and stores the
        result in state["tool_plan"]. The plan is injected as context in the next
        _call_model_node invocation.
        """
        if state.get("tool_plan"):
            # Already planned — skip
            return {}

        configurable = config.get("configurable") or {}
        task: Any = configurable.get("task")
        intent_category: str = ""
        if task is not None:
            intent_category = (
                (getattr(task, "context_payload", None) or {}).get("intent") or {}
            ).get("category") or ""

        if intent_category not in self._PLAN_TOOLS_INTENTS:
            return {}

        if self._lc_model is None:
            return {}

        llm_tools: list[Any] = configurable.get("llm_tools", [])
        tool_names = [t.name for t in llm_tools] if llm_tools else []
        instruction = getattr(task, "instruction", "") if task is not None else ""

        plan_prompt = (
            "Given the following user question and the available tools, produce a JSON array "
            "of tool-plan steps. Each step must have: "
            '"tool" (tool name), "purpose" (one sentence why), '
            '"depends_on" (list of tool names whose results are needed first, or empty list).\n\n'
            f"User question:\n{instruction}\n\n"
            f"Available tools: {tool_names}\n\n"
            "Respond with ONLY a JSON array, e.g.: "
            '[{"tool": "list_stockout_risk", "purpose": "enumerate all at-risk SKUs", '
            '"depends_on": []}]'
        )

        try:
            from langchain_core.messages import HumanMessage

            ai_msg = await self._lc_model.ainvoke([HumanMessage(plan_prompt)])
            raw_content: str = ai_msg.content if isinstance(ai_msg.content, str) else ""
            # Extract JSON array from the response
            match = re.search(r"\[.*\]", raw_content, re.DOTALL)
            if match:
                parsed: list[Any] = json.loads(match.group(0))
                tool_plan: list[ToolPlan] = [
                    ToolPlan(
                        tool=str(step.get("tool", "")),
                        purpose=str(step.get("purpose", "")),
                        depends_on=[str(d) for d in step.get("depends_on", [])],
                    )
                    for step in parsed
                    if isinstance(step, dict) and step.get("tool")
                ]
                _log.info(
                    "plan_tools node produced tool plan",
                    agent_role=self.role,
                    intent=intent_category,
                    plan_steps=len(tool_plan),
                )
                return {"tool_plan": tool_plan}
        except Exception:
            _log.warning(
                "plan_tools node failed — continuing without plan",
                agent_role=self.role,
                intent=intent_category,
            )
        return {}

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

                # Inject tool plan context if plan_tools node produced one
                tool_plan = state.get("tool_plan")
                if tool_plan:
                    lc_msgs.append(
                        HumanMessage(
                            "## Tool Plan\n\n" + json.dumps(
                                [
                                    {
                                        "tool": step["tool"],
                                        "purpose": step["purpose"],
                                        "depends_on": step["depends_on"],
                                    }
                                    for step in tool_plan
                                ],
                                indent=2,
                            )
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

        _configurable = config.get("configurable") or {}
        sse_queue = _configurable.get("sse_queue")
        persister = _configurable.get("event_persister")
        ctx: ToolContext = _configurable["ctx"]

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
        await _emit({
            "type": "awaiting_approval",
            "session_id": str(ctx.session_id),
            "approval_id": _approval_id,
            "tool_name": hitl_call["name"],
            "tool_input": tool_input,
            "job_id": _job_id,
            "description": _job_description,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, sse_queue, persister)

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
        _configurable = config.get("configurable") or {}
        sse_queue = _configurable.get("sse_queue")
        persister = _configurable.get("event_persister")
        ctx: ToolContext = _configurable["ctx"]

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
        await _emit({
            "type": "session_paused",
            "session_id": str(ctx.session_id),
            "approval_id": approval_id,
            "tool_name": tool_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, sse_queue, persister)

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

    async def _run_single_read_only_tool(
        self,
        call: dict[str, Any],
        ctx: "ToolContext",
        sse_queue: Any,
        agent_run_id: str,
        persister: Any = None,
    ) -> tuple[dict[str, Any], Any]:
        """Execute one non-HITL tool call and return (tool_result_dict, llm_message).

        Returns (result_entry, message) where result_entry is ``{tool_name: output}``
        and message is an ``LLMMessage(role="tool", ...)`` ready to feed back to the LLM.
        Raises on tool failure (caller must handle).
        """
        from packages.agent.llm import LLMMessage
        from packages.agent.orchestrator.parsing import json_safe

        tool = self._tool_registry.get(call["name"])
        if tool is None:
            return {}, None

        tool_call_id = call["id"]
        tool_input = call.get("input", {})

        tool_t0 = time.monotonic()
        await _emit({
            "type": "graph_node", "event": "start",
            "kind": "tool", "name": call["name"],
            "run_id": tool_call_id, "parent_run_id": agent_run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "input_summary": str(tool_input)[:200],
            "status": "ok", "meta": {},
        }, sse_queue, persister)
        try:
            tool_result = await tool.handle(tool_input, ctx)
            tool_duration_ms = int((time.monotonic() - tool_t0) * 1000)
            tool_output = tool_result.output
            executed_query = (
                tool_output.get("executed_query")
                if isinstance(tool_output, dict)
                else None
            )
            output_with_query: dict[str, Any] = (
                {**tool_output, "executed_query": executed_query}
                if isinstance(tool_output, dict) and executed_query is not None
                else (tool_output if isinstance(tool_output, dict) else {})
            )
            await _emit({
                "type": "graph_node", "event": "end",
                "kind": "tool", "name": call["name"],
                "run_id": tool_call_id, "parent_run_id": agent_run_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "duration_ms": tool_duration_ms,
                "status": "ok", "output": output_with_query, "meta": {},
            }, sse_queue, persister)
            msg = LLMMessage(
                role="tool",
                content=json.dumps(json_safe(tool_output)),
                tool_call_id=call["id"],
            )
            return {call["name"]: tool_output}, msg
        except Exception as exc:
            tool_duration_ms = int((time.monotonic() - tool_t0) * 1000)
            await _emit({
                "type": "graph_node", "event": "end",
                "kind": "tool", "name": call["name"],
                "run_id": tool_call_id, "parent_run_id": agent_run_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "duration_ms": tool_duration_ms,
                "status": "error", "error": str(exc), "meta": {},
            }, sse_queue, persister)
            raise

    async def _execute_tools_node(
        self, state: AgentState, config: RunnableConfig
    ) -> dict[str, Any]:
        from packages.agent.llm import LLMMessage
        from packages.agent.orchestrator.parsing import json_safe

        configurable = config.get("configurable") or {}
        sse_queue = configurable.get("sse_queue")
        persister = configurable.get("event_persister")
        ctx: ToolContext = configurable["ctx"]
        agent_run_id: str = configurable.get("agent_run_id", "")

        response = state.get("response")
        if response is None:
            return {}

        new_messages: list[Any] = []
        new_tool_results: list[dict[str, Any]] = []

        pending_job_id: str | None = state.get("pending_hitl_job_id")

        # Split tool calls into HITL and parallel (non-HITL) groups.
        # HITL tools must remain sequential; non-HITL tools can be gathered.
        hitl_calls: list[dict[str, Any]] = []
        parallel_calls: list[dict[str, Any]] = []

        for call in response.tool_calls:
            tool = self._tool_registry.get(call["name"])
            if tool is None:
                continue
            is_hitl = (
                getattr(tool, "safety_level", None) in ("hitl", "write")
                or call["name"] == "request_approval"
                or (
                    pending_job_id is not None
                    and getattr(tool, "safety_level", None) == "hitl"
                )
            )
            if is_hitl:
                hitl_calls.append(call)
            else:
                parallel_calls.append(call)

        # Execute non-HITL tool calls in parallel
        if parallel_calls:
            gather_results = await asyncio.gather(
                *[
                    self._run_single_read_only_tool(call, ctx, sse_queue, agent_run_id, persister)
                    for call in parallel_calls
                ],
                return_exceptions=True,
            )
            for outcome in gather_results:
                if isinstance(outcome, BaseException):
                    raise outcome
                result_entry, msg = outcome
                if result_entry:
                    new_tool_results.append(result_entry)
                if msg is not None:
                    new_messages.append(msg)

        # Execute HITL tool calls sequentially
        for call in hitl_calls:
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
                await _emit({
                    "type": "graph_node", "event": "start",
                    "kind": "tool", "name": call["name"],
                    "run_id": tool_call_id, "parent_run_id": agent_run_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "input_summary": str(tool_input)[:200],
                    "status": "ok", "meta": {},
                }, sse_queue, persister)
                try:
                    job_result = await execute_job(_UUID(pending_job_id), sse_queue=sse_queue)
                    tool_duration_ms = int((time.monotonic() - tool_t0) * 1000)
                    result_output: dict[str, Any] = job_result.get("result_json") or {}
                    if isinstance(result_output, str):
                        import json as _json
                        result_output = _json.loads(result_output)
                    new_tool_results.append({call["name"]: result_output})
                    await _emit({
                        "type": "graph_node", "event": "end",
                        "kind": "tool", "name": call["name"],
                        "run_id": tool_call_id, "parent_run_id": agent_run_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "duration_ms": tool_duration_ms,
                        "status": "ok", "output": result_output, "meta": {},
                    }, sse_queue, persister)
                    new_messages.append(LLMMessage(
                        role="tool",
                        content=json.dumps(json_safe(result_output)),
                        tool_call_id=call["id"],
                    ))
                except Exception as exc:
                    tool_duration_ms = int((time.monotonic() - tool_t0) * 1000)
                    await _emit({
                        "type": "graph_node", "event": "end",
                        "kind": "tool", "name": call["name"],
                        "run_id": tool_call_id, "parent_run_id": agent_run_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "duration_ms": tool_duration_ms,
                        "status": "error", "error": str(exc), "meta": {},
                    }, sse_queue, persister)
                    raise
                # Clear HITL job id after use
                pending_job_id = None
                continue

            # Non-job HITL tool (e.g. write safety_level) — execute sequentially
            result_entry, msg = await self._run_single_read_only_tool(
                call, ctx, sse_queue, agent_run_id, persister
            )
            if result_entry:
                new_tool_results.append(result_entry)
            if msg is not None:
                new_messages.append(msg)

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
        self, state: AgentState, config: RunnableConfig
    ) -> dict[str, Any]:
        """Rule-based pre-filter followed by optional LLM groundedness check (P72).

        Phase 1 — Rule-based pre-filter (always runs, no LLM):
          "blocked" → status="blocked" (short-circuits; no LLM check)
          "pass"    → continue to Phase 2

        Phase 2 — LLM groundedness check (gated):
          Runs ONLY when ALL of the following hold:
            - intent_category ∈ _GROUNDED_VERIFY_INTENTS
            - tool_results is non-empty
            - _lc_model is available (model_registry was supplied)
            - state["revised"] is False (one revision max)
          On any exception the check is silently skipped (fail-open).

          GroundednessVerdict.grounded is False → status="needs_revision",
            groundedness dict stored in state.
          GroundednessVerdict.grounded is True  → status="completed".
        """
        response = state.get("response")
        conclusion = response.text if response is not None else ""
        tool_results: list[dict[str, Any]] = state.get("tool_results") or []

        # --- Phase 1: rule-based pre-filter ---
        verify_status = _rule_based_verify(tool_results, conclusion)

        _log.info(
            "verify_findings rule-based result",
            agent_role=self.role,
            verify_status=verify_status,
        )

        if verify_status == "blocked":
            return {
                "status": "blocked",
                "blocked_reason": "findings verifier: response not grounded in tool results",
            }

        # --- Phase 2: LLM groundedness check (gated) ---

        # Gate: one revision max — if already revised, skip the LLM check
        if state.get("revised"):
            return {"status": "completed"}

        # Gate: need a usable model
        if self._lc_model is None:
            return {"status": "completed"}

        # Gate: intent must be in eligible set
        configurable = config.get("configurable") or {}
        task: Any = configurable.get("task")
        intent_category: str = ""
        if task is not None:
            intent_category = (
                (getattr(task, "context_payload", None) or {}).get("intent") or {}
            ).get("category") or ""

        if intent_category not in _GROUNDED_VERIFY_INTENTS:
            return {"status": "completed"}

        # Gate: tool_results must be non-empty
        if not tool_results:
            return {"status": "completed"}

        # Run the LLM groundedness check (fail-open)
        try:
            compact_results = _truncate_tool_results_for_prompt(tool_results)
            tool_results_json = json.dumps(compact_results, default=str)

            from langchain_core.messages import HumanMessage, SystemMessage

            groundedness_prompt = [
                SystemMessage(
                    "You are a factual grounding verifier. "
                    "Given tool results (JSON) and a draft answer, decide whether "
                    "EVERY factual claim in the answer is supported by the tool results. "
                    "Return grounded=true if all claims are supported. "
                    "Return grounded=false and list the specific unsupported claims "
                    "in unsupported_claims if any claim lacks evidence."
                ),
                HumanMessage(
                    f"## Tool results (compact JSON)\n{tool_results_json}\n\n"
                    f"## Draft answer\n{conclusion}"
                ),
            ]

            verdict: GroundednessVerdict = await (
                self._lc_model.with_structured_output(GroundednessVerdict).ainvoke(
                    groundedness_prompt
                )
            )

            _log.info(
                "verify_findings groundedness verdict",
                agent_role=self.role,
                grounded=verdict.grounded,
                unsupported_count=len(verdict.unsupported_claims),
                intent=intent_category,
            )

            if not verdict.grounded:
                return {
                    "status": "needs_revision",
                    "groundedness": {
                        "grounded": verdict.grounded,
                        "unsupported_claims": verdict.unsupported_claims,
                    },
                }

            return {
                "status": "completed",
                "groundedness": {
                    "grounded": verdict.grounded,
                    "unsupported_claims": [],
                },
            }

        except Exception as exc:
            _log.warning(
                "verify_findings groundedness check failed — falling back to rule-based pass",
                agent_role=self.role,
                intent=intent_category,
                error=str(exc),
            )
            return {"status": "completed"}

    # ------------------------------------------------------------------
    # Conditional edge after verify_findings
    # ------------------------------------------------------------------

    def _after_verify(self, state: AgentState) -> str:
        """Conditional edge after verify_findings.

        "blocked"        → END  (rule-based block)
        "needs_revision" → "add_revision_message"  (LLM verdict: ungrounded)
        "completed"      → END  (grounded or gated-skip)
        """
        status = state.get("status", "completed")
        if status == "needs_revision":
            return "add_revision_message"
        return END

    # ------------------------------------------------------------------
    # Node: add_revision_message
    # ------------------------------------------------------------------

    async def _add_revision_message_node(
        self, state: AgentState, config: RunnableConfig  # noqa: ARG002
    ) -> dict[str, Any]:
        from packages.agent.llm import LLMMessage

        groundedness: dict[str, Any] | None = state.get("groundedness")
        unsupported_claims: list[str] = (
            groundedness.get("unsupported_claims") or []
            if isinstance(groundedness, dict)
            else []
        )

        if unsupported_claims:
            claims_block = "\n".join(
                f"{i + 1}. {claim}" for i, claim in enumerate(unsupported_claims)
            )
            content = (
                "A groundedness check identified the following claims in your previous "
                "response that are NOT supported by the tool results:\n\n"
                f"{claims_block}\n\n"
                "Please revise your answer so that every factual claim is directly "
                "supported by what the tools actually returned. "
                "Do not assert facts that are absent from the tool results."
            )
        else:
            content = (
                "Your previous response may not be fully grounded in the tool results. "
                "Please review the tool results above and revise your answer, "
                "ensuring every claim is supported by what the tools actually returned."
            )

        revision_msg = LLMMessage(role="user", content=content)
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
        """Retry LLM call after needs_revision. Lightweight degenerate check before returning.

        Sets revised=True in state so that a second pass through verify_findings
        skips the LLM verdict (one revision max per turn).
        """
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
            result["blocked_reason"] = "degenerate response after revision"
        else:
            result["status"] = "completed"
        # Mark revised so verify_findings skips the LLM verdict on re-entry
        result["revised"] = True
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
        sg.add_node("plan_tools", self._plan_tools_node)
        sg.add_node("call_model", self._call_model_node)
        sg.add_node("prepare_hitl", self._prepare_hitl_node)
        sg.add_node("wait_for_approval", self._wait_for_approval_node)
        sg.add_node("execute_tools", self._execute_tools_node)
        sg.add_node("verify_findings", self._verify_findings_node)
        sg.add_node("add_revision_message", self._add_revision_message_node)
        sg.add_node("call_model_final", self._call_model_final_node)

        sg.add_edge(START, "compress_history")
        sg.add_edge("compress_history", "plan_tools")
        sg.add_edge("plan_tools", "call_model")
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
        sg.add_conditional_edges(
            "verify_findings",
            self._after_verify,
            {
                END: END,
                "add_revision_message": "add_revision_message",
            },
        )
        sg.add_edge("add_revision_message", "call_model_final")
        sg.add_edge("call_model_final", END)

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
            },
            # Propagate session context so UsageRecordingCallbackHandler can attribute
            # every LLM call inside the graph to the correct session and step.
            "metadata": {
                "session_id": str(ctx.session_id) if ctx.session_id else None,
                "agent_step_id": str(ctx.agent_step_id) if ctx.agent_step_id else None,
                "specialist_role": self.role,
            },
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
            "blocked_reason": None,
            "pending_hitl_approval_id": None,
            "pending_hitl_job_id": None,
            "compressed_messages": None,
            "tool_plan": [],
            "groundedness": None,
            "revised": False,
        }

        final_state: dict[str, Any] = await graph.ainvoke(initial_state, config=run_config)

        # Reconstruct tool_results dict from the accumulated list of dicts
        merged_tool_results: dict[str, Any] = {}
        for item in final_state.get("tool_results") or []:
            merged_tool_results.update(item)

        last_response = final_state.get("response")
        run_status = final_state.get("status", "completed")

        # Map internal graph status to SpecialistResult status
        # "blocked" is a soft-fail: verifier declined the answer but the run itself completed.
        # It maps to "completed" so the prepared fallback text is surfaced rather than a hard
        # SSE error. Genuine "error" status (LLM/infra failure) still maps to "failed".
        specialist_status: str
        if run_status == "completed":
            specialist_status = "completed"
        elif run_status == "blocked":
            specialist_status = "completed"
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

        # T-460: surface groundedness verdict in output meta (omitted when no verdict ran)
        # T-501/T-502: also carry blocked_reason into verification meta when run was blocked.
        groundedness_result: dict[str, Any] | None = final_state.get("groundedness")
        is_revised: bool = bool(final_state.get("revised", False))
        run_blocked_reason: str | None = final_state.get("blocked_reason")
        if groundedness_result is not None or run_status == "blocked":
            if isinstance(output, dict):
                verification: dict[str, Any] = {
                    "grounded": bool(
                        groundedness_result.get("grounded", True)
                        if isinstance(groundedness_result, dict)
                        else True
                    ),
                    "revised": is_revised,
                }
                if run_blocked_reason is not None:
                    verification["blocked_reason"] = run_blocked_reason
                output["verification"] = verification
        # blocked_error: use the truthful blocked_reason from graph state (T-501).
        # For genuine error-status runs, surface the error string.
        # For blocked runs (now soft-fail/completed), error stays None.
        blocked_error: str | None
        if run_status == "error":
            blocked_error = final_state.get("error")
        else:
            blocked_error = None

        # Auto-trigger audit log (non-fatal) — AuditLogTool is no longer LLM-callable (P64-B-02)
        if specialist_status != "failed":
            try:
                await AuditLogTool().handle(
                    {
                        "event_type": "agent_run_complete",
                        "payload": {
                            "session_id": str(ctx.session_id),
                            "agent_role": self.role,
                            "status": specialist_status,
                            "tool_count": len(final_state.get("tool_results") or []),
                        },
                    },
                    ctx,
                )
            except Exception:
                _log.warning(
                    "AuditLogTool auto-call failed — non-fatal",
                    agent_role=self.role,
                    session_id=str(ctx.session_id),
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
