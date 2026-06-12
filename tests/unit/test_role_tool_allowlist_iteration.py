"""D-010 regression: _RoleToolAllowlist.items() and .values() must trigger lazy
resolution of the "control" entry even when __getitem__ has never been called.

Without the fix, a freshly restarted API process returns tools: [] from
GET /api/v1/admin/registry because get_registry() iterates .items()/.values()
before any agent run has triggered __getitem__("control").

Test strategy: use monkeypatch to simulate a fresh process state by resetting
the module-global _CONTROL_ALLOWLIST_READY flag and the "control" entry to [].
After reset, call .items() / .values() directly (no __getitem__ first) and
assert the control list equals the sorted union of _INTENT_TOOL_SUBSET.
"""
from __future__ import annotations

import packages.tools.base as _base_module
from packages.agent.control.control_agent import _INTENT_TOOL_SUBSET
from packages.tools.base import _ROLE_TOOL_ALLOWLIST


def _expected_control_tools() -> list[str]:
    all_tools: set[str] = set()
    for tool_list in _INTENT_TOOL_SUBSET.values():
        all_tools.update(tool_list)
    return sorted(all_tools)


def test_items_resolves_control_on_fresh_state(monkeypatch: object) -> None:
    """_ROLE_TOOL_ALLOWLIST.items() must return the full control list even when
    __getitem__ has never been called (fresh-process simulation).

    monkeypatch resets _CONTROL_ALLOWLIST_READY and the "control" dict entry
    so the module behaves as if the process just started.
    """
    import pytest
    # mypy doesn't know monkeypatch type; use the pytest fixture protocol
    mp: pytest.MonkeyPatch = monkeypatch  # type: ignore[assignment]

    # Reset module-global lazy flag and control entry to simulate fresh process.
    mp.setattr(_base_module, "_CONTROL_ALLOWLIST_READY", False)
    # Use dict.__setitem__ to bypass the override (matches internal convention).
    original_control = dict.__getitem__(_ROLE_TOOL_ALLOWLIST, "control")
    dict.__setitem__(_ROLE_TOOL_ALLOWLIST, "control", [])

    try:
        # Iterate .items() without any prior __getitem__ call.
        items_dict = dict(_ROLE_TOOL_ALLOWLIST.items())
        control_from_items = items_dict.get("control", [])
    finally:
        # Restore: reset flag and entry so other tests are unaffected.
        dict.__setitem__(_ROLE_TOOL_ALLOWLIST, "control", original_control)
        mp.setattr(_base_module, "_CONTROL_ALLOWLIST_READY", True)

    expected = _expected_control_tools()
    assert control_from_items == expected, (
        f"items() returned unresolved control list.\n"
        f"Expected ({len(expected)}): {expected}\n"
        f"Got ({len(control_from_items)}): {control_from_items}"
    )


def test_values_resolves_control_on_fresh_state(monkeypatch: object) -> None:
    """_ROLE_TOOL_ALLOWLIST.values() must include the full control list even when
    __getitem__ has never been called (fresh-process simulation).
    """
    import pytest
    mp: pytest.MonkeyPatch = monkeypatch  # type: ignore[assignment]

    mp.setattr(_base_module, "_CONTROL_ALLOWLIST_READY", False)
    original_control = dict.__getitem__(_ROLE_TOOL_ALLOWLIST, "control")
    dict.__setitem__(_ROLE_TOOL_ALLOWLIST, "control", [])

    try:
        all_values = list(_ROLE_TOOL_ALLOWLIST.values())
        # "control" is the non-empty entry; "orchestrator" is always [].
        non_empty = [v for v in all_values if v]
    finally:
        dict.__setitem__(_ROLE_TOOL_ALLOWLIST, "control", original_control)
        mp.setattr(_base_module, "_CONTROL_ALLOWLIST_READY", True)

    expected = _expected_control_tools()
    assert len(non_empty) == 1, (
        f"Expected exactly one non-empty value list from values(), got: {non_empty}"
    )
    assert non_empty[0] == expected, (
        f"values() returned unresolved control list.\n"
        f"Expected ({len(expected)}): {expected}\n"
        f"Got ({len(non_empty[0])}): {non_empty[0]}"
    )
