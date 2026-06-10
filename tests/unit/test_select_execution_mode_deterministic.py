"""T-493 — Unit tests for deterministic select_execution_mode.

Verifies that:
1. Every category in _INTENT_MODE_MAP (chat, lookup, domain_analysis,
   cross_domain_analysis, supply_chain, decision_support) plus an unknown
   category (falls back to direct_chat) yields a route that passes
   validate_route and has the expected mode/agents shape.
2. No LLM call is made during routing — the orchestrator-role model is
   never invoked from select_execution_mode.
"""
from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from packages.agent.orchestrator.models import SessionIntent, SessionUserQuery
from packages.agent.orchestrator.routing import validate_route


def _make_orchestrator(model_registry: object | None = None) -> object:
    from packages.agent.orchestrator.session_orchestrator import SessionOrchestrator

    return SessionOrchestrator(
        llm_client=MagicMock(),
        tool_registry=MagicMock(),
        memory_store=MagicMock(),
        model_registry=model_registry,
    )


def _intent(category: str) -> SessionIntent:
    return SessionIntent(category=category, confidence=0.9, rationale="test")


def _query() -> SessionUserQuery:
    return SessionUserQuery(text="test query")


# ---------------------------------------------------------------------------
# Parametrized: every known category + unknown fallback
# ---------------------------------------------------------------------------

_CATEGORY_MODE_PAIRS = [
    ("chat", "direct_chat"),
    ("lookup", "single_agent"),
    ("domain_analysis", "single_agent"),
    ("cross_domain_analysis", "single_agent"),
    ("supply_chain", "single_agent"),
    ("decision_support", "single_agent"),
    ("totally_unknown_xyz", "direct_chat"),
]


@pytest.mark.parametrize("category,expected_mode", _CATEGORY_MODE_PAIRS)
async def test_select_execution_mode_route_passes_validate_route(
    category: str, expected_mode: str
) -> None:
    """Route returned for every category must satisfy validate_route."""
    orchestrator = _make_orchestrator()
    route = await orchestrator.select_execution_mode(_query(), _intent(category), uuid4())
    validate_route(route)  # raises if invalid


@pytest.mark.parametrize("category,expected_mode", _CATEGORY_MODE_PAIRS)
async def test_select_execution_mode_returns_expected_mode(
    category: str, expected_mode: str
) -> None:
    """Route mode must match the deterministic mapping for every category."""
    orchestrator = _make_orchestrator()
    route = await orchestrator.select_execution_mode(_query(), _intent(category), uuid4())
    assert route.mode == expected_mode


@pytest.mark.parametrize("category,expected_mode", _CATEGORY_MODE_PAIRS)
async def test_select_execution_mode_agents_shape(
    category: str, expected_mode: str
) -> None:
    """direct_chat routes have no agents; single_agent routes have exactly one agent."""
    orchestrator = _make_orchestrator()
    route = await orchestrator.select_execution_mode(_query(), _intent(category), uuid4())
    if expected_mode == "direct_chat":
        assert route.agents == []
    elif expected_mode == "single_agent":
        assert len(route.agents) == 1


# ---------------------------------------------------------------------------
# No LLM call during routing
# ---------------------------------------------------------------------------


async def test_select_execution_mode_never_invokes_model_registry() -> None:
    """Routing must be fully deterministic — model registry must not be queried."""
    spy_registry = MagicMock()
    orchestrator = _make_orchestrator(model_registry=spy_registry)

    for category, _ in _CATEGORY_MODE_PAIRS:
        await orchestrator.select_execution_mode(_query(), _intent(category), uuid4())

    spy_registry.get.assert_not_called()
