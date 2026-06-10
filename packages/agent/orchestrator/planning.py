from __future__ import annotations

from typing import Any
from uuid import UUID

from packages.agent.orchestrator.models import (
    SessionIntent,
    SessionUserQuery,
    SpecialistResult,
)


async def _run_agents_in_order(
    orchestrator: Any,
    session_id: UUID,
    query: SessionUserQuery,
    agent_roles: list[str],
    intent: SessionIntent,
) -> dict[str, SpecialistResult]:
    from packages.agent.orchestrator.runtime import _default_tools, _run_agent

    results: dict[str, SpecialistResult] = {}
    for agent_role in agent_roles:
        context_payload = {
            "query": query.text,
            "conversation_context": query.conversation_context,
            "intent": intent.model_dump(),
            "previous_results": {role: result.output for role, result in results.items()},
        }
        result = await _run_agent(
            orchestrator=orchestrator,
            session_id=session_id,
            agent_role=agent_role,
            instruction=intent.goal_text or query.text,
            context_payload=context_payload,
            allowed_tools=_default_tools(agent_role),
        )
        results[agent_role] = result
    return results
