from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Callable

import structlog

if TYPE_CHECKING:
    from packages.agent.orchestrator import SpecialistResult, SpecialistTask
    from packages.tools.base import ToolContext

_log = structlog.get_logger(__name__)

_MAX_ITERATIONS = 10

OutputBuilder = Callable[[dict[str, Any], Any], dict[str, Any]]

_VERIFIER_PROMPT = (
    "You are a findings verifier. Review the tool results and the agent's proposed conclusion.\n"
    "\n"
    "Check for:\n"
    "1. Are conclusions grounded in actual tool execution results? (Not invented data)\n"
    "2. Do numerical claims match what the tool results returned?\n"
    "3. Are all fetched tool results reflected — even implicitly — in the conclusion?\n"
    "\n"
    "Tool results:\n"
    "{tool_results_summary}\n"
    "\n"
    "Agent conclusion:\n"
    "{conclusion}\n"
    "\n"
    'Respond with exactly one of: "pass", "needs_revision", or "blocked"\n'
    "followed by a brief reason on the same line.\n"
    'Use "blocked" only if there is evidence of fabricated data or unauthorized action.\n'
    'Use "needs_revision" if minor corrections are needed.\n'
    'Use "pass" if the conclusion is well-grounded.'
)


def _default_output_builder(name: str) -> OutputBuilder:
    def _build(tool_results: dict[str, Any], response: Any) -> dict[str, Any]:
        text = response.text if response else ""
        output: dict[str, Any] = {"text": text, "specialist": name}
        if tool_results:
            output["tool_results"] = tool_results
        return output

    return _build


def _parse_verifier_status(text: str) -> str:
    """Extract 'pass', 'needs_revision', or 'blocked' from verifier response text."""
    lowered = text.strip().lower()
    for status in ("blocked", "needs_revision", "pass"):
        if re.search(rf"\b{re.escape(status)}\b", lowered):
            return status
    return "pass"


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
    ) -> None:
        self.name = name
        self.role = role
        self._llm_client = llm_client
        self._tool_registry = tool_registry
        self._sse_queue = sse_queue
        self._system_prompt = system_prompt or f"You are a {role} specialist."
        self._output_builder: OutputBuilder = output_builder or _default_output_builder(name)

    async def _push(self, event: dict[str, Any]) -> None:
        if self._sse_queue is not None:
            from packages.agent.orchestrator.parsing import json_safe
            await self._sse_queue.put(json_safe(event))

    async def _verify_findings(
        self,
        tool_results: dict[str, Any],
        conclusion: str,
        task_id: Any,
    ) -> str:
        """
        Make a single LLM call to verify that the agent's conclusion is grounded
        in the actual tool results.

        Returns one of: "pass", "needs_revision", "blocked".
        """
        from packages.agent.llm import LLMMessage

        tool_results_summary = "\n".join(
            f"  {name}: {json.dumps(result, default=str)[:300]}"
            for name, result in tool_results.items()
        ) or "  (no tool calls made)"

        verifier_content = _VERIFIER_PROMPT.format(
            tool_results_summary=tool_results_summary,
            conclusion=conclusion[:2000],
        )

        verifier_messages: list[LLMMessage] = [
            LLMMessage(role="user", content=verifier_content),
        ]

        _log.info("running verify_findings", agent_role=self.role)
        try:
            response = await self._llm_client.complete(
                messages=verifier_messages,
                tools=None,
                temperature=0.0,
                max_tokens=256,
                agent_step_id=task_id,
                specialist_role=self.role,
            )
        except Exception:
            _log.exception(
                "verify_findings LLM call failed; defaulting to pass",
                agent_role=self.role,
            )
            return "pass"

        status = _parse_verifier_status(response.text)
        _log.info("verify_findings complete", agent_role=self.role, verify_status=status)
        return status

    async def run(
        self,
        task: "SpecialistTask",
        ctx: "ToolContext",
        max_iterations: int | None = None,
    ) -> "SpecialistResult":
        from packages.agent.llm import LLMMessage, LLMToolSpec
        from packages.agent.orchestrator import SpecialistResult
        from packages.tools.schema_context import get_schema_context

        schema = get_schema_context()

        # T-008: 3-block prompt caching
        # Block 1: static base prompt (cacheable — changes only when system_prompt changes)
        # Block 2: schema context (cacheable — changes rarely)
        # Block 3: dynamic context (per-request — not cached)
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

        tool_calls_made: list[Any] = []
        tool_results: dict[str, Any] = {}
        last_response: Any = None
        _total_input_tokens = 0
        _total_output_tokens = 0
        _total_cost_usd: Decimal = Decimal("0")

        _verify_findings_done = False

        _iteration_limit = max_iterations if max_iterations is not None else _MAX_ITERATIONS

        async def _run_tool_loop(messages: list[LLMMessage]) -> list[LLMMessage]:
            nonlocal last_response, _total_input_tokens, _total_output_tokens, _total_cost_usd

            for _ in range(_iteration_limit):
                _log.info(
                    "specialist calling LLM",
                    agent_role=self.role,
                    model=getattr(self._llm_client, "_model", "?"),
                )
                response = await self._llm_client.complete(
                    messages=messages,
                    tools=llm_tools if llm_tools else None,
                    temperature=0.0,
                    agent_step_id=task.task_id,
                    specialist_role=self.role,
                )
                last_response = response
                _total_input_tokens += response.usage.input_tokens
                _total_output_tokens += response.usage.output_tokens
                _total_cost_usd += response.usage.total_cost_usd
                _log.info(
                    "specialist LLM response received",
                    agent_role=self.role,
                    finish_reason=response.finish_reason,
                    tool_call_count=len(response.tool_calls),
                    model=response.model,
                )

                if not response.tool_calls or response.finish_reason == "stop":
                    break

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
                messages.append(LLMMessage(
                    role="assistant", content=response.text, content_blocks=content_blocks
                ))

                for call in response.tool_calls:
                    tool = self._tool_registry.get(call["name"])
                    if tool is not None:
                        tool_call_id = call["id"]
                        tool_input = call.get("input", {})

                        # HITL intercept: pause execution and request human approval
                        if getattr(tool, "safety_level", None) == "hitl":
                            from uuid import UUID as _UUID
                            from uuid import uuid4 as _uuid4

                            from packages.agent.orchestrator.hitl import HITLPause
                            from packages.persistence.approvals_repo import ApprovalsRepository

                            _repo = ApprovalsRepository()
                            try:
                                created = await _repo.create({
                                    "session_id": str(ctx.session_id),
                                    "status": "pending",
                                    "actor": ctx.actor,
                                    "reason": f"HITL tool: {call['name']}",
                                })
                                _approval_id = str(created.get("id", _uuid4()))
                            except Exception:
                                _approval_id = str(_uuid4())

                            _job_id: str | None = None
                            _job_description: str = ""
                            if call["name"] == "job_dispatch":
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

                            await self._push({
                                "type": "awaiting_approval",
                                "session_id": str(ctx.session_id),
                                "approval_id": _approval_id,
                                "tool_name": call["name"],
                                "tool_input": tool_input,
                                "job_id": _job_id,
                                "description": _job_description,
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            })
                            raise HITLPause(
                                approval_id=_approval_id,
                                tool_name=call["name"],
                                tool_input=tool_input,
                            )

                        tool_t0 = time.monotonic()
                        await self._push({
                            "type": "tool_started",
                            "tool_name": call["name"],
                            "tool_call_id": tool_call_id,
                            "step_id": str(ctx.agent_step_id),
                            "agent_role": self.role,
                            "input": tool_input,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })
                        try:
                            tool_result = await tool.handle(tool_input, ctx)
                            tool_duration_ms = int((time.monotonic() - tool_t0) * 1000)
                            tool_calls_made.append(ctx.agent_step_id)
                            tool_results[call["name"]] = tool_result.output
                            executed_query = (
                                tool_result.output.get("executed_query")
                                if isinstance(tool_result.output, dict)
                                else None
                            )
                            await self._push({
                                "type": "tool_completed",
                                "tool_name": call["name"],
                                "tool_call_id": tool_call_id,
                                "agent_role": self.role,
                                "duration_ms": tool_duration_ms,
                                "output": tool_result.output,
                                "executed_query": executed_query,
                                "status": "success",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            })
                        except Exception as exc:
                            tool_duration_ms = int((time.monotonic() - tool_t0) * 1000)
                            await self._push({
                                "type": "tool_completed",
                                "tool_name": call["name"],
                                "tool_call_id": tool_call_id,
                                "agent_role": self.role,
                                "duration_ms": tool_duration_ms,
                                "status": "error",
                                "error": str(exc),
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            })
                            raise
                        from packages.agent.orchestrator.parsing import json_safe
                        messages.append(LLMMessage(
                            role="tool",
                            content=json.dumps(json_safe(tool_result.output)),
                            tool_call_id=call["id"],
                        ))

            return messages

        # Build the initial message list with 3-block system prompt
        messages: list[LLMMessage] = [
            LLMMessage(role="system", content="", content_blocks=system_blocks),
            LLMMessage(role="user", content=task.instruction),
        ]

        messages = await _run_tool_loop(messages)

        # T-007: verify_findings step
        # Derive conclusion text from the last LLM response
        conclusion = last_response.text if last_response else ""
        verify_status = await self._verify_findings(tool_results, conclusion, task.task_id)

        if verify_status == "needs_revision" and not _verify_findings_done:
            _verify_findings_done = True
            _log.info(
                "verify_findings=needs_revision; retrying tool loop once",
                agent_role=self.role,
            )
            # Re-append a user message asking the agent to revise
            messages.append(
                LLMMessage(
                    role="user",
                    content=(
                        "Your previous response may not be fully grounded in the tool results. "
                        "Please review the tool results above and revise your answer, "
                        "ensuring every claim is supported by what the tools actually returned."
                    ),
                )
            )
            messages = await _run_tool_loop(messages)

        return SpecialistResult(
            task_id=task.task_id,
            output=self._output_builder(tool_results, last_response),
            tool_calls_made=tool_calls_made,
            status="completed",
            usage={
                "input_tokens": _total_input_tokens,
                "output_tokens": _total_output_tokens,
                "cost_usd": float(_total_cost_usd),
            },
        )
