from __future__ import annotations

from typing import Any, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel

from packages.schemas.recommendation import Recommendation


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
