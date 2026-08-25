"""Deterministic scripted chat model for e2e testing (D-026 seam).

Activated only via ``LLM_DRIVER=scripted`` at model-construction time (see
:func:`packages.agent.model_registry.create_model_registry`). The API server's
single construction seam routes every role (orchestrator / planner / control)
to this model, so job-flow e2e scenarios do not depend on live gemma4:12b
natural-language routing decisions.

Behaviour (purely message-derived — no hidden mutable state):

- Structured-output request (``bind_tools([schema], tool_choice="any")``):
  returns a canned, schema-valid tool call for the requested schema name.
  Unknown schema names raise ``ValueError`` — no silent fallback.
- Control turn with ``job_dispatch`` among the bound tools and no ToolMessage
  in the conversation yet: emits one deterministic ``job_dispatch`` tool call.
- Control turn after a ToolMessage is observed (post-approval resume): emits a
  plain-text final answer with no tool calls.
- Bare invocation (no bound tools): emits a fixed plain-text response.

temperature=0 invariant: this model contains zero randomness — identical
inputs always produce identical outputs. All call ids are constants so
checkpoint replay on HITL resume stays consistent.
"""

from __future__ import annotations

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

_MODEL_TAG = "scripted-driver"
_PROVIDER_TAG = "scripted"

_STRUCT_CALL_ID = "call_scripted_structured_0"
_DISPATCH_CALL_ID = "call_scripted_job_dispatch_0"

_DISPATCH_TOOL_NAME = "job_dispatch"

# Deterministic job_dispatch arguments. job_type="simulate" maps to
# SimulationTool in the job executor, which always completes and attaches a
# generated_files CSV row — exactly what test_job_approve_executes_and_completes
# asserts.
_DISPATCH_TOOL_ARGS: dict[str, Any] = {
    "job_type": "simulate",
    "params": {"sku_id": "SKU-001", "order_qty": 100.0, "horizon_days": 30},
    "description": "Scripted inventory simulation dispatched by LLM_DRIVER=scripted",
}

_FINAL_ANSWER_TEXT = (
    "**Job report — simulate dispatched.** "
    "The inventory simulation job was approved and handed to the background "
    "runner. A completion report will be added to this chat when it finishes."
)

_BARE_TEXT = (
    "Scripted driver response: this deterministic e2e driver performs no "
    "tool calls for unbound requests."
)

_GOAL_TEXT_MAX_CHARS = 200


def _last_human_text(messages: list[BaseMessage]) -> str:
    """Return the most recent HumanMessage text, truncated deterministically."""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage) and isinstance(msg.content, str):
            return msg.content.strip()[:_GOAL_TEXT_MAX_CHARS]
    return ""


def _canned_structured_args(
    schema_name: str, messages: list[BaseMessage]
) -> dict[str, Any]:
    """Canned args for supported structured-output schema names.

    Keyed by class name because PydanticToolsParser validates against the real
    schema at parse time; this module intentionally does not import those
    schemas (avoids cycles and keeps the canned table self-contained).
    """
    if schema_name == "SessionIntent":
        return {
            "category": "supply_chain",
            "confidence": 1.0,
            "rationale": "Scripted driver deterministic intent (LLM_DRIVER=scripted)",
            # Empty → downstream falls back to query.text as instruction.
            "goal_text": "",
        }
    if schema_name == "GoalSpec":
        return {"goal_text": _last_human_text(messages), "success_criteria": []}
    if schema_name == "AskUserDecision":
        return {"needs_input": False, "question": None, "suggestions": []}
    if schema_name == "GroundednessVerdict":
        return {"grounded": True, "unsupported_claims": []}
    if schema_name == "GoalEvaluation":
        return {"satisfied": True, "missing": None, "reroute_category": None}
    raise ValueError(
        f"ScriptedDriverModel does not support structured-output schema "
        f"{schema_name!r}. Supported schemas: SessionIntent, GoalSpec, "
        "AskUserDecision, GroundednessVerdict, GoalEvaluation."
    )


def _tool_name(entry: Any) -> str | None:
    """Extract a tool name from an OpenAI-format dict, Pydantic class, or object."""
    if isinstance(entry, dict):
        function = entry.get("function")
        if isinstance(function, dict) and function.get("name"):
            return str(function["name"])
        return None
    try:
        from langchain_core.utils.function_calling import convert_to_openai_tool

        function = convert_to_openai_tool(entry).get("function", {})
        if function.get("name"):
            return str(function["name"])
    except Exception:
        pass
    name = getattr(entry, "name", None)
    return str(name) if name else None


class ScriptedDriverModel(BaseChatModel):
    """BaseChatModel emitting a fixed job_dispatch sequence (test-only driver).

    Implements the same bind_tools / with_structured_output surface as the
    production ChatOllama models so AgentRuntime and SessionOrchestrator need
    no changes. bind_tools returns an immutable copy carrying the binding;
    the shared registry instance itself is never mutated.
    """

    _model = _MODEL_TAG  # StubClaudeClient-compatible attribute for trace meta

    bound_tool_entries: list[Any] = []
    bound_tool_choice: Any = None

    @property
    def _llm_type(self) -> str:
        return _PROVIDER_TAG

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"model": _MODEL_TAG}

    def bind_tools(
        self, tools: Any, *, tool_choice: Any = None, **kwargs: Any
    ) -> "ScriptedDriverModel":
        # kwargs swallows provider-specific options such as
        # ls_structured_output_format passed by with_structured_output().
        return self.model_copy(
            update={"bound_tool_entries": list(tools), "bound_tool_choice": tool_choice}
        )

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=self._build_response(messages))])

    def _build_response(self, messages: list[BaseMessage]) -> AIMessage:
        names = [n for n in (_tool_name(e) for e in self.bound_tool_entries) if n]

        # Structured-output binding: with_structured_output() always passes
        # tool_choice="any" with exactly one schema.
        if self.bound_tool_choice == "any":
            if len(names) != 1:
                raise ValueError(
                    f"ScriptedDriverModel expected exactly one structured-output "
                    f"schema, got: {names}"
                )
            args = _canned_structured_args(names[0], messages)
            return self._ai_message(
                content="",
                tool_calls=[{
                    "name": names[0],
                    "args": args,
                    "id": _STRUCT_CALL_ID,
                    "type": "tool_call",
                }],
            )

        if _DISPATCH_TOOL_NAME in names:
            has_tool_result = any(isinstance(m, ToolMessage) for m in messages)
            if has_tool_result:
                # Post-approval resume: produce the final prose answer.
                return self._ai_message(content=_FINAL_ANSWER_TEXT, tool_calls=[])
            return self._ai_message(
                content="",
                tool_calls=[{
                    "name": _DISPATCH_TOOL_NAME,
                    "args": dict(_DISPATCH_TOOL_ARGS),
                    "id": _DISPATCH_CALL_ID,
                    "type": "tool_call",
                }],
            )

        # Bare invocation (synthesis, plan_tools, history summary).
        if self.bound_tool_entries:
            raise ValueError(
                f"ScriptedDriverModel cannot handle bound tools {names}. Only "
                f"{_DISPATCH_TOOL_NAME}-containing control bindings and "
                "with_structured_output schemas are supported."
            )
        return self._ai_message(content=_BARE_TEXT, tool_calls=[])

    def _ai_message(self, content: str, tool_calls: list[dict[str, Any]]) -> AIMessage:
        return AIMessage(
            content=content,
            tool_calls=tool_calls,
            usage_metadata={
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
            },
            response_metadata={"model_name": _MODEL_TAG},
        )
