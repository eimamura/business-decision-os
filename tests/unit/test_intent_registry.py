from __future__ import annotations

import pytest

from packages.agent.orchestrator.intent_registry import (
    INTENT_REGISTRY,
    IntentConfig,
    get_intent_config,
)


@pytest.mark.parametrize(
    ("category", "expected_max_tool_calls"),
    [
        ("chat", 0),
        ("lookup", 5),
        ("domain_analysis", 10),
        ("cross_domain_analysis", 15),
        ("decision_support", 20),
    ],
)
def test_get_intent_config_returns_correct_max_tool_calls(
    category: str, expected_max_tool_calls: int
) -> None:
    config = get_intent_config(category)
    assert config.max_tool_calls == expected_max_tool_calls


def test_get_intent_config_unknown_raises_key_error() -> None:
    with pytest.raises(KeyError):
        get_intent_config("nonexistent_category")


def test_chat_skips_tool_loop() -> None:
    config = get_intent_config("chat")
    assert config.skip_tool_loop is True


def test_all_five_categories_registered() -> None:
    expected = {"chat", "lookup", "domain_analysis", "cross_domain_analysis", "decision_support"}
    assert set(INTENT_REGISTRY.keys()) == expected


def test_intent_config_is_frozen() -> None:
    config = get_intent_config("lookup")
    with pytest.raises((AttributeError, TypeError)):
        config.max_tool_calls = 999  # type: ignore[misc]


def test_non_chat_intents_do_not_skip_tool_loop() -> None:
    for category in ("lookup", "domain_analysis", "cross_domain_analysis", "decision_support"):
        config = get_intent_config(category)
        assert config.skip_tool_loop is False, (
            f"Expected {category}.skip_tool_loop to be False"
        )


def test_intent_config_types() -> None:
    for category, config in INTENT_REGISTRY.items():
        assert isinstance(config, IntentConfig), f"{category} value is not IntentConfig"
        assert isinstance(config.description, str)
        assert isinstance(config.plan_prompt, str)
        assert isinstance(config.allowed_agent_roles, list)
        assert isinstance(config.max_tool_calls, int)
        assert isinstance(config.skip_tool_loop, bool)
