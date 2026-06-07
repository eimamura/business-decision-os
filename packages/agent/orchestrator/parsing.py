from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, cast
from uuid import UUID


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_safe(value: Any) -> Any:
    """Recursively convert non-JSON-serializable types to their safe equivalents."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return value


class LLMResponseParseError(ValueError):
    """Raised when the LLM returns text that cannot be parsed as the expected JSON structure."""

    def __init__(self, raw_text: str) -> None:
        super().__init__("no JSON object in LLM response")
        self.raw_text = raw_text


def _json_obj(text: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise LLMResponseParseError(text)
    try:
        return cast(dict[str, Any], json.loads(match.group()))
    except json.JSONDecodeError:
        raise LLMResponseParseError(text)


def _json_array(text: str) -> list[dict[str, Any]]:
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        raise LLMResponseParseError(text)
    try:
        return cast(list[dict[str, Any]], json.loads(match.group()))
    except json.JSONDecodeError:
        raise LLMResponseParseError(text)
