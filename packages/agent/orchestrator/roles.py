from __future__ import annotations

DOMAIN_AGENT_ROLES = {"control"}

CROSS_DOMAIN_AGENT_CLASSES: dict[str, type] = {}

VALID_AGENT_ROLES = DOMAIN_AGENT_ROLES | set(CROSS_DOMAIN_AGENT_CLASSES)
