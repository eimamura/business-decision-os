"""Unit tests for _normalize_llm_text (T-346).

Six cases covering normal content, <think> tag stripping, multi-block stripping,
and side-channel fallback paths (reasoning / thinking fields).
"""
from __future__ import annotations

import logging


# ---------------------------------------------------------------------------
# Case (a): normal content is returned unchanged
# ---------------------------------------------------------------------------


def test_normalize_llm_text_plain_content_returned_unchanged() -> None:
    from packages.agent.llm import _normalize_llm_text

    message = {"content": "Hello, world!"}
    result = _normalize_llm_text(message, model_name="test-model")

    assert result == "Hello, world!"


# ---------------------------------------------------------------------------
# Case (b): single <think>…</think> block is stripped
# ---------------------------------------------------------------------------


def test_normalize_llm_text_single_think_block_removed() -> None:
    from packages.agent.llm import _normalize_llm_text

    message = {"content": "<think>internal reasoning</think>Final answer."}
    result = _normalize_llm_text(message, model_name="qwen3:7b")

    assert result == "Final answer."


# ---------------------------------------------------------------------------
# Case (c): multiple <think>…</think> blocks are all removed
# ---------------------------------------------------------------------------


def test_normalize_llm_text_multiple_think_blocks_all_removed() -> None:
    from packages.agent.llm import _normalize_llm_text

    message = {
        "content": (
            "<think>step one</think>Part A. <think>step two\nmultiline</think>Part B."
        )
    }
    result = _normalize_llm_text(message, model_name="deepseek-r1")

    assert result == "Part A. Part B."


# ---------------------------------------------------------------------------
# Case (d): empty content + reasoning field → returns reasoning + emits warning
# ---------------------------------------------------------------------------


def test_normalize_llm_text_empty_content_uses_reasoning_field(
    caplog: pytest.LogCaptureFixture,
) -> None:
    import pytest  # noqa: F401 — imported for type annotation in signature above
    from packages.agent.llm import _normalize_llm_text

    message = {"content": "", "reasoning": "deep thought here"}
    with caplog.at_level(logging.WARNING, logger="packages.agent.llm"):
        result = _normalize_llm_text(message, model_name="qwen3:7b")

    assert result == "deep thought here"
    assert any("reasoning/thinking" in record.message for record in caplog.records)


# ---------------------------------------------------------------------------
# Case (e): empty content + thinking field → returns thinking + emits warning
# ---------------------------------------------------------------------------


def test_normalize_llm_text_empty_content_uses_thinking_field(
    caplog: pytest.LogCaptureFixture,
) -> None:
    import pytest  # noqa: F401 — imported for type annotation in signature above
    from packages.agent.llm import _normalize_llm_text

    message = {"content": "", "thinking": "  thought process  "}
    with caplog.at_level(logging.WARNING, logger="packages.agent.llm"):
        result = _normalize_llm_text(message, model_name="deepseek-r1")

    assert result == "thought process"
    assert any("reasoning/thinking" in record.message for record in caplog.records)


# ---------------------------------------------------------------------------
# Case (f): empty content + no side-channel → returns empty string
# ---------------------------------------------------------------------------


def test_normalize_llm_text_empty_content_no_side_channel_returns_empty() -> None:
    from packages.agent.llm import _normalize_llm_text

    message: dict = {"content": ""}
    result = _normalize_llm_text(message, model_name="some-model")

    assert result == ""
