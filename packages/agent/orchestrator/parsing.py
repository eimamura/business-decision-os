from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, cast


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_obj(text: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("no JSON object in LLM response")
    return cast(dict[str, Any], json.loads(match.group()))


def _json_array(text: str) -> list[dict[str, Any]]:
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        raise ValueError("no JSON array in LLM response")
    return cast(list[dict[str, Any]], json.loads(match.group()))
