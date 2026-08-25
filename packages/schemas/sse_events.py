from __future__ import annotations

from typing import Annotated, Any, Literal, Union
from uuid import UUID

from pydantic import BaseModel, Field


class TokenCost(BaseModel):
    input_tokens: int
    output_tokens: int
    cost_usd: float


class GraphNodeEvent(BaseModel):
    type: Literal["graph_node"] = "graph_node"
    event: Literal["start", "end"]
    kind: Literal["orchestrator", "agent", "tool"]
    name: str
    run_id: str
    parent_run_id: str | None = None
    timestamp: str
    # "start" only:
    input_summary: str | None = None
    # "end" only:
    duration_ms: int | None = None
    status: Literal["ok", "error"] = "ok"
    meta: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] | None = None
    token_cost: TokenCost | None = None
    error: str | None = None


class MemoryRetrievedEvent(BaseModel):
    type: Literal["memory_retrieved"] = "memory_retrieved"
    count: int
    source: str | None = None
    timestamp: str


class MemoryWrittenEvent(BaseModel):
    type: Literal["memory_written"] = "memory_written"
    timestamp: str


class ResponseReadyEvent(BaseModel):
    type: Literal["response_ready"] = "response_ready"
    mode: str
    risk_level: Literal["low", "medium", "high"] | None = None
    requires_approval: bool | None = None
    timestamp: str


class AutoExecutedEvent(BaseModel):
    type: Literal["auto_executed"] = "auto_executed"
    recommendation_id: str
    timestamp: str


class ApprovalRequestedEvent(BaseModel):
    type: Literal["approval_requested"] = "approval_requested"
    approval_id: str
    expires_at: str
    risk_level: Literal["low", "medium", "high"]
    timestamp: str


class AwaitingApprovalEvent(BaseModel):
    type: Literal["awaiting_approval"] = "awaiting_approval"
    session_id: str
    approval_id: str
    tool_name: str
    tool_input: dict[str, Any]
    job_id: str | None = None
    description: str
    timestamp: str


class AskUserRequiredEvent(BaseModel):
    type: Literal["ask_user_required"] = "ask_user_required"
    session_id: str
    ask_user_id: str
    question: str
    suggestions: list[str] = []
    timestamp: str


class ClarificationRequiredEvent(BaseModel):
    type: Literal["clarification_required"] = "clarification_required"
    session_id: str
    round: int
    message: str
    timestamp: str


class SessionPausedEvent(BaseModel):
    type: Literal["session_paused"] = "session_paused"
    session_id: str
    approval_id: str
    tool_name: str
    timestamp: str


class JobFile(BaseModel):
    file_name: str
    download_url: str


class JobCompletedEvent(BaseModel):
    type: Literal["job_completed"] = "job_completed"
    job_id: str
    job_type: str
    file_count: int
    files: list[JobFile]
    timestamp: str


class JobFailedEvent(BaseModel):
    type: Literal["job_failed"] = "job_failed"
    job_id: str
    job_type: str
    error: str
    timestamp: str


class JobReportEvent(BaseModel):
    """Emitted after a background job completes or fails (T-602).

    Carries the assistant report text so a live SSE subscriber can render it
    as a new assistant message without waiting for a page reload.
    """
    type: Literal["job_report"] = "job_report"
    session_id: str | None = None
    content: str
    timestamp: str


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    step_id: str | None = None
    code: str
    message: str
    recoverable: bool
    timestamp: str


class TextDeltaEvent(BaseModel):
    type: Literal["text_delta"] = "text_delta"
    session_id: str
    delta: str
    timestamp: str


class TextResetEvent(BaseModel):
    """Emitted before a second synthesis pass when the first was degenerate.

    Signals clients to discard all previously received text_delta events for
    this session and treat the next text_delta events as the authoritative reply.
    This is emitted by run_sequential on goal-refinement when the first control-agent
    reply was degenerate (D-014 fix).
    """
    type: Literal["text_reset"] = "text_reset"
    session_id: str
    reason: str
    timestamp: str


class DoneEvent(BaseModel):
    type: Literal["done"] = "done"
    session_id: UUID
    reply: str | None = None
    timestamp: str


class AwaitingInputEvent(BaseModel):
    """Emitted when the graph is paused at wait_for_answer (ask_user interrupt).
    Signals the SSE stream to terminate cleanly without a reply."""
    type: Literal["awaiting_input"] = "awaiting_input"
    session_id: UUID
    ask_user_id: str
    timestamp: str


SseEvent = Annotated[
    Union[
        GraphNodeEvent,
        MemoryRetrievedEvent,
        MemoryWrittenEvent,
        ResponseReadyEvent,
        ApprovalRequestedEvent,
        AutoExecutedEvent,
        AwaitingApprovalEvent,
        AskUserRequiredEvent,
        ClarificationRequiredEvent,
        SessionPausedEvent,
        JobCompletedEvent,
        JobFailedEvent,
        JobReportEvent,
        ErrorEvent,
        TextDeltaEvent,
        TextResetEvent,
        DoneEvent,
        AwaitingInputEvent,
    ],
    Field(discriminator="type"),
]
