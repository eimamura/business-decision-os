from __future__ import annotations

from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel

from packages.schemas.recommendation import Recommendation


class SessionGoal(BaseModel):
    text: str
    weight_override_json: dict | None = None


class SpecialistTask(BaseModel):
    task_id: UUID
    instruction: str
    context_payload: dict
    allowed_tools: list[str]


class SpecialistResult(BaseModel):
    task_id: UUID
    output: dict
    tool_calls_made: list[UUID]
    status: Literal["completed", "failed", "needs_input"]
    error: str | None = None


class Orchestrator(Protocol):
    async def run(self, session_id: UUID, goal: SessionGoal) -> Recommendation: ...
    async def resume(self, session_id: UUID, approval_id: UUID) -> Recommendation: ...
