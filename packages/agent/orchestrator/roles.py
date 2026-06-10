from __future__ import annotations

DOMAIN_AGENT_ROLES = {"control"}

# Empty since P38/P45 — all cross-domain agent classes removed in P65.
# Kept as a public name because tests/unit/test_sop_roles.py and
# apps/api/routers/admin.py still import it (B-02 / future cleanup will remove it).
CROSS_DOMAIN_AGENT_CLASSES: dict[str, type] = {}

VALID_AGENT_ROLES = DOMAIN_AGENT_ROLES | set(CROSS_DOMAIN_AGENT_CLASSES)
