from __future__ import annotations

from packages.agent.domain.sop import SopAgent, _SYSTEM_PROMPT
from packages.agent.llm import StubClaudeClient
from packages.tools.base import ToolRegistry


def test_sop_agent_instantiates_with_correct_role() -> None:
    agent = SopAgent(llm_client=StubClaudeClient(), tool_registry=ToolRegistry())
    assert agent.role == "sop"
    assert agent.name == "sop"


def test_sop_agent_system_prompt_references_structured_output() -> None:
    assert "S&OP" in _SYSTEM_PROMPT
    assert "Next actions" in _SYSTEM_PROMPT
    assert "Decision" in _SYSTEM_PROMPT
