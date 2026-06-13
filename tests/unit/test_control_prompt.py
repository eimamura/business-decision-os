from __future__ import annotations

import re

from packages.agent.control.control_agent import (
    _INTENT_TOOL_SUBSET,
    _SYSTEM_PROMPT,
    render_business_guidelines,
    render_response_format,
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


def test_render_business_guidelines_contains_no_tool_names() -> None:
    """render_business_guidelines must not contain backtick-quoted tool names.

    The function describes what the agent IS, not how it routes.  Embedding
    tool names there would couple the role description to the tool registry and
    cause prompt rot when tools are renamed.
    """
    result = render_business_guidelines()
    all_tool_names = {name for names in _INTENT_TOOL_SUBSET.values() for name in names}
    for tool_name in all_tool_names:
        assert f"`{tool_name}`" not in result, (
            f"Tool name `{tool_name}` found in render_business_guidelines()"
        )


def test_render_response_format_contains_required_sections() -> None:
    """render_response_format must contain all four required response-format section headers.

    These section headers are load-bearing: they shape how the agent structures
    every response.  Missing one means a section silently disappears from the prompt.
    """
    result = render_response_format()
    for section in ["Situation", "Root Cause", "Recommended Actions", "Confidence Level"]:
        assert section in result, f"Section '{section}' missing from render_response_format()"


def test_render_response_format_contains_no_tool_names() -> None:
    """render_response_format must not contain backtick-quoted tool names.

    Rules 11-12 (grounding constraints) were moved to render_routing_policy() by B-01.
    The response format section must remain free of tool name references to prevent
    prompt rot when tools are renamed.
    """
    result = render_response_format()
    all_tool_names = {name for names in _INTENT_TOOL_SUBSET.values() for name in names}
    for tool_name in all_tool_names:
        assert f"`{tool_name}`" not in result, (
            f"Tool name `{tool_name}` found in render_response_format()"
        )


def test_make_schema_example_empty_string_returns_empty() -> None:
    """_make_schema_example('') must return '' without raising or hitting the DB."""
    from packages.agent.control.control_agent import _make_schema_example

    assert _make_schema_example("") == ""


def test_make_schema_example_uses_provided_schema() -> None:
    """_make_schema_example must use the schema string passed as argument.

    Passing a minimal schema containing the four required tables must produce
    output that references 'sku_master'.  This confirms the function reads the
    supplied string rather than calling get_schema_context() internally.
    """
    from packages.agent.control.control_agent import _make_schema_example

    minimal_schema = (
        "sku_master(sku_id TEXT)\n"
        "demand_history(sku_id TEXT, quantity NUMERIC)\n"
        "inventory_snapshot(sku_id TEXT, on_hand NUMERIC)\n"
        "supply_orders(sku_id TEXT, quantity NUMERIC)"
    )
    result = _make_schema_example(minimal_schema)
    assert "sku_master" in result


def test_render_routing_policy_contains_rule_11_for_decision_support() -> None:
    """Rule 11 must cover decision_support optimization/approval tools."""
    result = render_routing_policy(_INTENT_TOOL_SUBSET)
    for tool in ("optimize_replenishment", "request_approval", "evaluate_candidates", "forecast", "simulate_inventory"):
        assert tool in result, f"Rule 11 (decision_support) is missing tool: {tool}"
    # Rule 11 must appear in the output (after renumbering)
    assert "11." in result, "render_routing_policy output is missing Rule 11"


def test_render_routing_policy_schema_example_after_synthesis_instruction() -> None:
    """{schema_example} placeholder must appear after 'do NOT call any tool again'."""
    raw = render_routing_policy(_INTENT_TOOL_SUBSET)
    synthesis_phrase = "do NOT call any tool again"
    schema_placeholder = "{schema_example}"
    assert synthesis_phrase in raw, f"Synthesis instruction not found in routing policy"
    assert schema_placeholder in raw, f"{{schema_example}} placeholder not found in routing policy"
    synthesis_pos = raw.index(synthesis_phrase)
    schema_pos = raw.index(schema_placeholder)
    assert schema_pos > synthesis_pos, (
        f"{{schema_example}} appears at position {schema_pos} but synthesis instruction "
        f"appears at position {synthesis_pos}; schema_example must come AFTER synthesis"
    )


def test_render_routing_policy_no_spec_q_references() -> None:
    """render_routing_policy must not contain any (SPEC Q#) references."""
    result = render_routing_policy(_INTENT_TOOL_SUBSET)
    for label in ("(SPEC Q5)", "(SPEC Q7)", "(SPEC Q8)", "(SPEC Q9)", "(SPEC Q10)"):
        assert label not in result, (
            f"Found obsolete SPEC reference {label!r} in render_routing_policy output. "
            "Replace with inline semantic label."
        )


def test_build_system_prompt_intent_narrows_tool_subset() -> None:
    """_build_system_prompt(intent='lookup') must omit supply_chain-exclusive tools from the
    tool availability catalog section.

    render_routing_policy() emits a 'Tool availability by intent:' catalog at the top that
    lists exactly which tools are available per intent.  When called with intent='lookup',
    _build_system_prompt narrows render_routing_policy() to the lookup subset only, so
    supply_chain-exclusive tools must not appear in that catalog line.
    """
    from packages.agent.control.control_agent import _build_system_prompt, _INTENT_TOOL_SUBSET

    # Tools that exist in supply_chain but NOT in lookup
    supply_chain_only = [
        t for t in _INTENT_TOOL_SUBSET["supply_chain"]
        if t not in _INTENT_TOOL_SUBSET["lookup"]
    ]
    assert supply_chain_only, "Test precondition: supply_chain must have tools not in lookup"

    result = _build_system_prompt(intent="lookup")

    # Extract the tool-availability catalog line (format: "lookup: tool1, tool2, ...")
    catalog_line = ""
    for line in result.splitlines():
        if line.startswith("lookup:"):
            catalog_line = line
            break
    assert catalog_line, "No 'lookup:' catalog line found in prompt built for intent='lookup'"

    for tool in supply_chain_only:
        assert tool not in catalog_line, (
            f"Tool {tool!r} (supply_chain-exclusive) appears in 'lookup:' catalog line "
            f"of prompt built for intent='lookup'"
        )
    # nl_query must still appear (common to both)
    assert "nl_query" in catalog_line, "nl_query must appear in lookup-intent catalog line"


def test_build_system_prompt_intent_none_includes_all_intents() -> None:
    """_build_system_prompt(intent=None) must include routing section for every intent."""
    from packages.agent.control.control_agent import _build_system_prompt, _INTENT_TOOL_SUBSET

    result = _build_system_prompt(intent=None)
    for intent_key in _INTENT_TOOL_SUBSET:
        assert intent_key in result, (
            f"Intent key {intent_key!r} not found in prompt built with intent=None"
        )
