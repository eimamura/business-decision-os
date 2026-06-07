"""Check that the configured LLM backend meets Business Decision OS requirements.

Usage:
    uv run python scripts/check_llm.py
    make check-llm

Exit code 0 = all checks passed. Non-zero = at least one check failed.

Checks:
  1. Basic completion       — model responds at all
  2. Function calling       — model calls a tool instead of generating apology text
  3. Multi-turn loop        — model generates a coherent answer after receiving a tool result
  4. JSON structured output — model returns valid JSON when instructed (required for intent
                              classification and routing; models that only output <think> blocks
                              or free text will fail this check)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

# Load .env from project root so this works without docker.
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

# Add project root to path so packages can be imported.
sys.path.insert(0, str(Path(__file__).parent.parent))

from packages.agent.llm import LLMMessage, LLMToolSpec, create_llm_client  # noqa: E402

_TOOL = LLMToolSpec(
    name="calculate_stockout_risk",
    description="Calculate stockout risk for a SKU given current inventory and demand.",
    input_schema={
        "type": "object",
        "properties": {
            "sku_id": {"type": "string", "description": "Product SKU identifier"},
        },
        "required": ["sku_id"],
    },
)

_SYSTEM = (
    "You are a supply chain analyst. "
    "Always use the available tools to retrieve data — never apologise for lacking data."
)


def _label(ok: bool) -> str:
    return "✓ PASS" if ok else "✗ FAIL"


async def check_basic(client: object) -> bool:
    """Model responds to a simple question."""
    resp = await client.complete(  # type: ignore[attr-defined]
        messages=[
            LLMMessage(role="system", content=_SYSTEM),
            LLMMessage(role="user", content="Reply with the single word: READY"),
        ],
        tools=None,
    )
    return bool(resp.text and resp.text.strip())


async def check_function_calling(client: object) -> bool:
    """Model calls a tool instead of generating an apology."""
    resp = await client.complete(  # type: ignore[attr-defined]
        messages=[
            LLMMessage(role="system", content=_SYSTEM),
            LLMMessage(role="user", content="What is the stockout risk for SKU-001?"),
        ],
        tools=[_TOOL],
    )
    return bool(resp.tool_calls)


async def check_multi_turn(client: object) -> bool:
    """Model produces a coherent final answer after receiving a tool result."""
    # Round 1: model should call the tool
    resp1 = await client.complete(  # type: ignore[attr-defined]
        messages=[
            LLMMessage(role="system", content=_SYSTEM),
            LLMMessage(role="user", content="What is the stockout risk for SKU-001?"),
        ],
        tools=[_TOOL],
    )
    if not resp1.tool_calls:
        return False  # function calling already failed — skip

    call = resp1.tool_calls[0]
    tool_result_content = json.dumps(
        {"sku_id": "SKU-001", "risk_level": "high", "days_of_supply": 3}
    )

    # Round 2: inject tool result and ask for a final answer
    resp2 = await client.complete(  # type: ignore[attr-defined]
        messages=[
            LLMMessage(role="system", content=_SYSTEM),
            LLMMessage(role="user", content="What is the stockout risk for SKU-001?"),
            LLMMessage(
                role="assistant",
                content=resp1.text or "",
                content_blocks=[
                    *(
                        [{"type": "text", "text": resp1.text}]
                        if resp1.text
                        else []
                    ),
                    {
                        "type": "tool_use",
                        "id": call["id"],
                        "name": call["name"],
                        "input": call.get("input", {}),
                    },
                ],
            ),
            LLMMessage(
                role="tool",
                content=tool_result_content,
                tool_call_id=call["id"],
                tool_name=call["name"],
            ),
        ],
        tools=[_TOOL],
    )
    return bool(resp2.text and resp2.text.strip() and not resp2.tool_calls)


async def check_json_output(client: object) -> bool:
    """Model returns valid JSON when asked for structured output (no tools).

    Intent classification and routing both require the model to respond with a
    JSON object. Fails for:
    - Models that ignore the format instruction entirely
    - Qwen3 thinking models (e.g. qwen3.5:2b) that return content="" + reasoning="..."
      via Ollama's OpenAI-compat endpoint — the actual JSON never lands in content
    - Models that output only <think> blocks with no follow-up JSON
    """
    import re

    resp = await client.complete(  # type: ignore[attr-defined]
        messages=[
            LLMMessage(
                role="system",
                content=(
                    "You are a classifier. "
                    "Always respond with a JSON object only — no prose, no markdown fences. "
                    'Example: {"label": "positive", "score": 0.9}'
                ),
            ),
            LLMMessage(
                role="user",
                content=(
                    'Classify the sentiment of: "I love this product!"\n'
                    'Respond with {"label": "positive"|"negative"|"neutral", "score": <float 0-1>}'
                ),
            ),
        ],
        tools=None,
        temperature=0.0,
        max_tokens=128,
    )
    if not resp.text:
        print(
            "\n    [!] Model returned empty text. If using Ollama, this may be a Qwen3 "
            "thinking model (e.g. qwen3.5:2b) that puts output in 'reasoning' rather "
            "than 'content'. These models are not compatible — switch to a non-thinking "
            "variant (qwen2.5:7b, llama3.1:8b, mistral-nemo, etc.).",
            end="",
        )
        return False
    text = resp.text.strip()
    # strip <think>...</think> blocks (non-thinking output should follow)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    if not text:
        print(
            "\n    [!] Model returned only a <think> block with no follow-up JSON. "
            "Disable thinking mode or switch to a non-thinking model.",
            end="",
        )
        return False
    # strip optional markdown code fence
    if text.startswith("```"):
        text = "\n".join(
            line for line in text.splitlines() if not line.startswith("```")
        ).strip()
    try:
        parsed = json.loads(text)
        return isinstance(parsed, dict) and "label" in parsed
    except (json.JSONDecodeError, ValueError):
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return False
        try:
            parsed = json.loads(m.group())
            return isinstance(parsed, dict) and "label" in parsed
        except (json.JSONDecodeError, ValueError):
            return False


async def main() -> int:
    provider = os.environ.get("LLM_PROVIDER", "anthropic").lower()
    if provider == "ollama":
        model_name = os.environ.get("OLLAMA_MODEL", "gpt-oss:20b")
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        label = f"ollama  model={model_name}  base_url={base_url}"
    else:
        model_name = os.environ.get("TEST_MODEL", "claude-sonnet-4-6")
        label = f"anthropic  model={model_name}"

    print(f"\nLLM backend: {label}\n")

    try:
        client = create_llm_client()
    except RuntimeError as exc:
        print(f"  [!] Cannot create LLM client: {exc}")
        return 1

    results: list[tuple[str, bool | str]] = []

    checks: list[tuple[str, object]] = [
        ("1. Basic completion      ", check_basic),
        ("2. Function calling      ", check_function_calling),
        ("3. Multi-turn loop       ", check_multi_turn),
        ("4. JSON structured output", check_json_output),
    ]

    for name, fn in checks:
        print(f"  {name}... ", end="", flush=True)
        try:
            ok = await fn(client)  # type: ignore[operator]
            print(_label(ok))
            results.append((name, ok))
        except Exception as exc:
            msg = f"ERROR — {exc}"
            print(f"  {msg}")
            results.append((name, False))

    passed = sum(1 for _, ok in results if ok is True)
    total = len(results)
    print(f"\n  {passed}/{total} checks passed")

    if passed < total:
        print(
            "\n  Tip: models must support function calling AND return valid JSON when\n"
            "  instructed (checks 2–4).\n"
            "\n"
            "  Known-good models (LLM_PROVIDER=ollama):\n"
            "    qwen2.5:7b, llama3.1:8b, mistral-nemo, deepseek-r1:14b\n"
            "\n"
            "  Known-failing (Qwen3 thinking models — content empty via OpenAI-compat API):\n"
            "    qwen3.5:2b, qwen3:8b and other qwen3.x variants\n"
            "    → Switch to qwen2.5 or set OLLAMA_MODEL to a non-thinking model.\n"
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
