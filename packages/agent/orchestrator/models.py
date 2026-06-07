from __future__ import annotations

from typing import Any, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, Field

from packages.schemas.recommendation import Candidate, TradeoffExplanation

ExecutionMode = Literal[
    "direct_chat",
    "single_agent",
    "sequential_agents",
    "planned_execution",
    "dag_execution",
]


class SessionUserQuery(BaseModel):
    text: str
    conversation_context: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    weight_override_json: dict[str, Any] | None = None


class SessionIntent(BaseModel):
    category: str
    confidence: float
    rationale: str
    goal_text: str | None = None


class AgentRoute(BaseModel):
    mode: ExecutionMode
    agents: list[str] = Field(default_factory=list)
    requires_planning: bool = False
    requires_dag: bool = False
    rationale: str


class AskUserDecision(BaseModel):
    needs_input: bool
    question: str | None = None
    suggestions: list[str] | None = None


class PlanStep(BaseModel):
    id: str
    agent_role: str
    instruction: str
    tools: list[str] = Field(default_factory=list)


class ExecutionPlan(BaseModel):
    steps: list[PlanStep]


class TaskNode(BaseModel):
    id: str
    agent_role: str
    deps: list[str] = Field(default_factory=list)
    instruction: str = ""
    tools: list[str] = Field(default_factory=list)

    @property
    def specialist_type(self) -> str:
        return self.agent_role


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
    # keys: input_tokens, output_tokens, cost_usd
    usage: dict[str, Any] | None = None


class SessionResponse(BaseModel):
    mode: ExecutionMode
    reply: str
    intent: SessionIntent
    route: AgentRoute
    agent_results: dict[str, SpecialistResult] = Field(default_factory=dict)
    primary: Candidate | None = None
    alternatives: list[Candidate] = Field(default_factory=list)
    tradeoff: TradeoffExplanation | None = None
    risk_level: Literal["low", "medium", "high"] = "low"
    requires_approval: bool = False


class Orchestrator(Protocol):
    async def run(self, session_id: UUID, query: SessionUserQuery) -> SessionResponse: ...
    async def resume(self, session_id: UUID, approval_id: UUID) -> SessionResponse: ...
    async def answer_ask_user(self, session_id: UUID, answer: str) -> SessionResponse: ...  # NEW
