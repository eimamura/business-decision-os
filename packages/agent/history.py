from __future__ import annotations

import logging
from typing import Any

import anthropic

logger = logging.getLogger(__name__)

SUMMARY_THRESHOLD = 30
RECENT_KEEP = 10


async def compress_history(
    messages: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str | None]:
    """Returns (messages_to_use, summary_prefix | None).

    If message count <= SUMMARY_THRESHOLD, returns (messages, None) unchanged.
    Otherwise summarizes the oldest messages using Claude Haiku and returns
    (recent_10_messages, summary_string).
    """
    if len(messages) <= SUMMARY_THRESHOLD:
        return messages, None

    to_summarize = messages[:-RECENT_KEEP]
    recent = messages[-RECENT_KEEP:]

    try:
        summary = await _summarize(to_summarize)
    except Exception:
        logger.warning("History summarization failed; using full history", exc_info=True)
        return messages, None

    logger.info("Summarized %d messages into history summary", len(to_summarize))
    return recent, summary


async def _summarize(messages: list[dict[str, Any]]) -> str:
    transcript = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in messages
    )
    client = anthropic.AsyncAnthropic()
    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=(
            "Summarize the following conversation history concisely. "
            "Focus on the business decisions discussed and key facts. Plain text only."
        ),
        messages=[{"role": "user", "content": transcript}],
    )
    block = response.content[0]
    if not isinstance(block, anthropic.types.TextBlock):
        raise ValueError(f"Unexpected content block type: {type(block)}")
    return block.text.strip()
