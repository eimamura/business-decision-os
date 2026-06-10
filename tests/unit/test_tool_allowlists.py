from __future__ import annotations

"""T-436: Tests for the surviving _ROLE_TOOL_ALLOWLIST reality after B-01.

B-01 removed 14 dead role entries; only "orchestrator" and "control" remain.
"control" is auto-derived from _INTENT_TOOL_SUBSET via _get_control_allowlist().

Coverage here avoids duplicating test_control_allowlist_derived.py, which
already asserts:
  - _ROLE_TOOL_ALLOWLIST["control"] equals the sorted union of _INTENT_TOOL_SUBSET
  - the list is non-empty and lexicographically sorted

What this file adds:
  - orchestrator entry is an empty-list safety guard
  - only "orchestrator" and "control" keys are present (no dead-role debris)
  - direct access to a removed dead role raises KeyError
  - list_for_role() on an unknown role falls through to all-tools (expected
    permissive default: the caller is responsible for providing a known role)
"""

import pytest

from packages.tools.base import ToolRegistry, _ROLE_TOOL_ALLOWLIST
from packages.tools.base import ToolContext, ToolResult


class _FakeTool:
    name = "fake_allowlist_test_tool"
    description = "Fake tool for allowlist tests"
    input_schema: dict = {}
    output_schema: dict = {}
    safety_level = "read_only"

    async def handle(self, input: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(output={}, audit_payload={})


# ---------------------------------------------------------------------------
# Guard: orchestrator entry must stay an empty-list safety net
# ---------------------------------------------------------------------------

def test_orchestrator_allowlist_is_empty_list() -> None:
    """_ROLE_TOOL_ALLOWLIST["orchestrator"] must be [] — safety guard, not None."""
    assert _ROLE_TOOL_ALLOWLIST["orchestrator"] == []


# ---------------------------------------------------------------------------
# Guard: no dead-role debris — only "orchestrator" and "control" exist
# ---------------------------------------------------------------------------

def test_allowlist_keys_are_only_orchestrator_and_control() -> None:
    """After B-01, the only explicit keys must be 'orchestrator' and 'control'."""
    keys = set(_ROLE_TOOL_ALLOWLIST.keys())
    assert keys == {"orchestrator", "control"}, (
        f"Unexpected keys in _ROLE_TOOL_ALLOWLIST: {keys - {'orchestrator', 'control'}!r}"
    )


# ---------------------------------------------------------------------------
# Guard: accessing a removed dead-role key raises KeyError
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("dead_role", [
    "demand",
    "inventory",
    "replenishment",
    "data_engineer",
    "simulation_optimizer",
    "evaluator",
])
def test_dead_role_direct_access_raises_key_error(dead_role: str) -> None:
    """Removed role names must not silently return values — they must KeyError."""
    with pytest.raises(KeyError):
        _ = _ROLE_TOOL_ALLOWLIST[dead_role]


# ---------------------------------------------------------------------------
# Behaviour: list_for_role() with an unknown role falls through to all tools
# (ToolRegistry.list_for_role uses .get(), so None → return all)
# ---------------------------------------------------------------------------

def test_list_for_role_unknown_role_returns_all_tools() -> None:
    """list_for_role with an unrecognized role returns all registered tools.

    This is the permissive fallthrough defined in ToolRegistry.list_for_role:
      allowed = _ROLE_TOOL_ALLOWLIST.get(role)  # → None for unknown roles
      if allowed is None:
          return list(self._tools.values())
    """
    registry = ToolRegistry()
    registry.register(_FakeTool())
    tools = registry.list_for_role("some_unknown_role")
    names = {t.name for t in tools}
    assert "fake_allowlist_test_tool" in names
