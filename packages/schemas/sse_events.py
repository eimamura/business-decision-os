from __future__ import annotations

from typing import Annotated, Any, Literal, Union
from uuid import UUID

from pydantic import BaseModel, Field


class SessionStartedEvent(BaseModel):
    event: Literal["session_started"] = "session_started"
    session_id: UUID
    timestamp: str


class SpecialistActivatedEvent(BaseModel):
    event: Literal["specialist_activated"] = "specialist_activated"
    session_id: UUID
    timestamp: str
    specialist_role: str
    step_id: UUID


class ToolCalledEvent(BaseModel):
    event: Literal["tool_called"] = "tool_called"
    session_id: UUID
    timestamp: str
    tool_call_id: UUID
    step_id: UUID
    tool_name: str
    input: dict[str, Any]
    specialist_role: str


class ToolCompletedEvent(BaseModel):
    event: Literal["tool_completed"] = "tool_completed"
    session_id: UUID
    timestamp: str
    tool_call_id: UUID
    tool_name: str
    duration_ms: int
    output: dict[str, Any]
    executed_query: str | None = None
    status: Literal["success", "error"]
    error: str | None = None


class RecommendationReadyEvent(BaseModel):
    event: Literal["recommendation_ready"] = "recommendation_ready"
    session_id: UUID
    timestamp: str
    recommendation_id: UUID
    risk_level: Literal["low", "medium", "high"]
    requires_approval: bool
    auto_execute: bool = False


class AutoExecutedEvent(BaseModel):
    event: Literal["auto_executed"] = "auto_executed"
    session_id: UUID
    timestamp: str
    recommendation_id: UUID


class AwaitingApprovalEvent(BaseModel):
    event: Literal["awaiting_approval"] = "awaiting_approval"
    session_id: UUID
    timestamp: str
    approval_id: UUID
    recommendation_id: UUID
    expires_at: str


class ErrorEvent(BaseModel):
    event: Literal["error"] = "error"
    session_id: UUID
    timestamp: str
    code: str
    message: str
    recoverable: bool


class DoneEvent(BaseModel):
    event: Literal["done"] = "done"
    session_id: UUID
    timestamp: str


SseEvent = Annotated[
    Union[
        SessionStartedEvent,
        SpecialistActivatedEvent,
        ToolCalledEvent,
        ToolCompletedEvent,
        RecommendationReadyEvent,
        AutoExecutedEvent,
        AwaitingApprovalEvent,
        ErrorEvent,
        DoneEvent,
    ],
    Field(discriminator="event"),
]
