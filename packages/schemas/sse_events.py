from __future__ import annotations

from typing import Annotated, Any, Literal, Union
from uuid import UUID

from pydantic import BaseModel, Field


class QueryReceivedEvent(BaseModel):
    type: Literal["query_received"] = "query_received"
    session_id: str
    timestamp: str


class IntentClassifiedEvent(BaseModel):
    type: Literal["intent_classified"] = "intent_classified"
    category: str
    confidence: float
    rationale: str
    goal_text: str | None = None
    timestamp: str


class ExecutionModeSelectedEvent(BaseModel):
    type: Literal["execution_mode_selected"] = "execution_mode_selected"
    mode: str
    agents: list[str]
    requires_planning: bool
    requires_dag: bool
    rationale: str
    timestamp: str


class PlanCreatedEvent(BaseModel):
    type: Literal["plan_created"] = "plan_created"
    mode: str
    steps: list[dict[str, Any]] | None = None
    nodes: list[dict[str, Any]] | None = None
    timestamp: str


class AgentStartedEvent(BaseModel):
    type: Literal["agent_started"] = "agent_started"
    agent_name: str
    agent_role: str
    task_id: str
    started_at: str
    input_summary: str | None = None


class AgentCompletedEvent(BaseModel):
    type: Literal["agent_completed"] = "agent_completed"
    agent_name: str
    agent_role: str
    task_id: str
    duration_ms: int = 0
    output_summary: str | None = None
    timestamp: str
    # token cost for this agent invocation
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None


class ToolStartedEvent(BaseModel):
    type: Literal["tool_started"] = "tool_started"
    tool_name: str
    tool_call_id: str
    step_id: str | None = None
    agent_role: str
    input: dict[str, Any] | None = None
    timestamp: str


class ToolCompletedEvent(BaseModel):
    type: Literal["tool_completed"] = "tool_completed"
    tool_name: str
    tool_call_id: str
    agent_role: str
    duration_ms: int = 0
    output: dict[str, Any] | None = None
    executed_query: str | None = None
    status: Literal["success", "error"] = "success"
    error: str | None = None
    timestamp: str


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
    ask_user_id: str          # NEW — UUID identifying this specific ask-user interrupt
    question: str
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


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    step_id: str | None = None
    code: str
    message: str
    recoverable: bool
    timestamp: str


class DoneEvent(BaseModel):
    type: Literal["done"] = "done"
    session_id: UUID
    reply: str | None = None
    timestamp: str


SseEvent = Annotated[
    Union[
        QueryReceivedEvent,
        IntentClassifiedEvent,
        ExecutionModeSelectedEvent,
        PlanCreatedEvent,
        AgentStartedEvent,
        AgentCompletedEvent,
        ToolStartedEvent,
        ToolCompletedEvent,
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
        ErrorEvent,
        DoneEvent,
    ],
    Field(discriminator="type"),
]
