from __future__ import annotations

import logging

from packages.agent.llm import LLMMessage, create_llm_client
from packages.memory import ShortTermMemory

logger = logging.getLogger(__name__)

SUMMARY_THRESHOLD = 30
RECENT_KEEP = 10


async def compress_history(
    messages: list[ShortTermMemory],
) -> tuple[list[ShortTermMemory], str | None]:
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


async def _summarize(messages: list[ShortTermMemory]) -> str:
    transcript = "\n".join(f"{m.role.upper()}: {m.content}" for m in messages)
    llm = create_llm_client()
    llm_messages: list[LLMMessage] = [
        LLMMessage(
            role="system",
            content=(
                "Summarize the following conversation history concisely. "
                "Focus on the business decisions discussed and key facts. Plain text only."
            ),
        ),
        LLMMessage(role="user", content=transcript),
    ]
    response = await llm.complete(llm_messages, max_tokens=512)
    return response.text.strip()
