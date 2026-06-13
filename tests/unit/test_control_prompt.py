from __future__ import annotations

import re

from packages.agent.control.control_agent import (
    _INTENT_TOOL_SUBSET,
    _SYSTEM_PROMPT,
    render_routing_policy,
    render_tool_catalog,
)
from packages.tools import create_tool_registry

_RESERVED = {"None", "True", "False", "list", "dict", "str", "int", "bool", "float", "set", "tuple"}


def test_system_prompt_tool_names_all_registered() -> None:
    """Every backtick-quoted identifier in _SYSTEM_PROMPT that looks like a tool name
    (snake_case with at least one underscore) must exist in the ToolRegistry.

    This ensures prompt references do not silently rot when tools are renamed.
    """
    # Extract all backtick-quoted identifiers
    backtick_ids = re.findall(r"`([^`]+)`", _SYSTEM_PROMPT)

    # Strip call-expression suffixes so `list_stockout_risk(horizon_days=7)` → `list_stockout_risk`
    bare_ids = [name.split("(")[0] for name in backtick_ids]

    # Filter to identifiers that look like tool names: snake_case, has underscore, not reserved
    tool_name_candidates = [
        name for name in bare_ids
        if "_" in name and name not in _RESERVED
    ]

    if not tool_name_candidates:
        # No tool-name candidates found — structural change may have happened; fail loudly
        raise AssertionError(
            "_SYSTEM_PROMPT contains no backtick-quoted snake_case identifiers. "
            "If tool name references were intentionally removed, delete this test too."
        )

    registered_names = set(create_tool_registry()._tools.keys())
    missing = [name for name in tool_name_candidates if name not in registered_names]

    assert missing == [], (
        f"_SYSTEM_PROMPT references tool names not in ToolRegistry: {missing}\n"
        "Either rename the tool in the prompt, or register the tool."
    )


def test_render_routing_policy_contains_all_tool_names() -> None:
    """render_routing_policy must mention every unique tool name from _INTENT_TOOL_SUBSET.

    This guards against a tool being added to the SSoT dict but silently omitted
    from the generated routing text.
    """
    result = render_routing_policy(_INTENT_TOOL_SUBSET)

    all_tools: set[str] = {
        tool
        for tools in _INTENT_TOOL_SUBSET.values()
        for tool in tools
    }

    missing = [tool for tool in sorted(all_tools) if tool not in result]

    assert missing == [], (
        f"render_routing_policy output is missing tool names: {missing}\n"
        "Add the tool name to the rendered policy or update the SSoT dict."
    )


def test_render_tool_catalog_format() -> None:
    """render_tool_catalog must include each intent key and at least one of its tools.

    This ensures the catalog format is correct and that the intent→tool mapping
    is faithfully reflected in the rendered string.
    """
    catalog = render_tool_catalog(_INTENT_TOOL_SUBSET)

    for intent, tools in _INTENT_TOOL_SUBSET.items():
        assert intent in catalog, (
            f"render_tool_catalog output is missing intent key: {intent!r}"
        )
        assert any(tool in catalog for tool in tools), (
            f"render_tool_catalog output contains intent {intent!r} "
            f"but none of its tools appear: {tools}"
        )
