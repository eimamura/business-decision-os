from __future__ import annotations

import re

from packages.agent.control.control_agent import _SYSTEM_PROMPT
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
