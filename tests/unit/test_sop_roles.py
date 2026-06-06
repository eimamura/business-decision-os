from __future__ import annotations

from packages.agent.orchestrator.roles import CROSS_DOMAIN_AGENT_CLASSES


def test_sop_not_in_cross_domain_agent_classes() -> None:
    assert "sop" not in CROSS_DOMAIN_AGENT_CLASSES
