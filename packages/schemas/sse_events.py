from __future__ import annotations

from typing import Annotated, Literal, Union
from uuid import UUID

from pydantic import BaseModel, Field


class RoutingDecisionEvent(BaseModel):
    type: Literal["routing_decision"] = "routing_decision"
    route: list[str]
    rationale: str
    timestamp: str


class StepStartedEvent(BaseModel):
    type: Literal["step_started"] = "step_started"
    step_id: str
    specialist_role: str
    step_type: str
    started_at: str
    input_summary: str | None = None


class StepCompletedEvent(BaseModel):
    type: Literal["step_completed"] = "step_completed"
    step_id: str
    specialist_role: str
    step_type: str | None = None
    duration_ms: int = 0
    output_preview: str | None = None
    output_summary: str | None = None
    tokens: int | None = None
    cost_usd: float | None = None
    selected_roles: list[str] | None = None
    ended_at: str | None = None


class SpecialistStartedEvent(BaseModel):
    type: Literal["specialist_started"] = "specialist_started"
    specialist_name: str
    specialist_role: str
    task_id: str
    started_at: str
    input_summary: str | None = None


class SpecialistCompletedEvent(BaseModel):
    type: Literal["specialist_completed"] = "specialist_completed"
    specialist_name: str
    specialist_role: str
    task_id: str
    duration_ms: int = 0
    output_summary: str | None = None
    timestamp: str


class ToolCalledEvent(BaseModel):
    type: Literal["tool_called"] = "tool_called"
    tool_name: str
    tool_call_id: str
    step_id: str | None = None
    specialist_role: str
    input: dict | None = None
    timestamp: str


class ToolCompletedEvent(BaseModel):
    type: Literal["tool_completed"] = "tool_completed"
    tool_name: str
    tool_call_id: str
    specialist_role: str
    duration_ms: int = 0
    output: dict | None = None
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


class RecommendationReadyEvent(BaseModel):
    type: Literal["recommendation_ready"] = "recommendation_ready"
    recommendation_id: str
    risk_level: Literal["low", "medium", "high"]
    requires_approval: bool
    auto_execute: bool = False
    timestamp: str


class AutoExecutedEvent(BaseModel):
    type: Literal["auto_executed"] = "auto_executed"
    recommendation_id: str
    timestamp: str


class AwaitingApprovalEvent(BaseModel):
    type: Literal["awaiting_approval"] = "awaiting_approval"
    approval_id: str
    recommendation_id: str
    expires_at: str
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
        RoutingDecisionEvent,
        StepStartedEvent,
        StepCompletedEvent,
        SpecialistStartedEvent,
        SpecialistCompletedEvent,
        ToolCalledEvent,
        ToolCompletedEvent,
        MemoryRetrievedEvent,
        MemoryWrittenEvent,
        RecommendationReadyEvent,
        AutoExecutedEvent,
        AwaitingApprovalEvent,
        ErrorEvent,
        DoneEvent,
    ],
    Field(discriminator="type"),
]
