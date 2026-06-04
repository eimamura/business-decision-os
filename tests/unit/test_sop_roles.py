from __future__ import annotations

from typing import get_args

from packages.agent.base import SpecialistRole
from packages.agent.orchestrator.roles import CROSS_DOMAIN_AGENT_CLASSES, DOMAIN_AGENT_ROLES


def test_specialist_role_includes_sop_roles() -> None:
    literal_values = set(get_args(SpecialistRole))
    for role in {"supply_planning", "finance_impact", "sop"}:
        assert role in literal_values, (
            f"Expected '{role}' in SpecialistRole Literal"
        )


def test_domain_agent_roles_includes_sop_agents() -> None:
    for role in {"supply_planning", "finance_impact", "sop"}:
        assert role in DOMAIN_AGENT_ROLES, (
            f"Expected '{role}' in DOMAIN_AGENT_ROLES"
        )


def test_sop_not_in_cross_domain_agent_classes() -> None:
    assert "sop" not in CROSS_DOMAIN_AGENT_CLASSES
