"""D-012/D-013/D-014/D-015 Acceptance Verification — P100 B-02.

Runs the 4 acceptance questions from the P100 defect spec through the live stack
and reports:
  - Real Ollama context usage (from session_events token_cost graph_node events)
  - Tools called (no duplicate executions)
  - Reply excerpt
  - No non-English fragments

Usage:
    uv run python scripts/verify_d012_d015.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

import httpx

API_BASE = "http://localhost:8002"
NUM_CTX = 16384
TOKEN_CAP_RATIO = 0.90
TOKEN_CAP = int(NUM_CTX * TOKEN_CAP_RATIO)

ACCEPTANCE_QUESTIONS = [
    {
        "id": "Q1",
        "text": "Which products are at risk of stockout?",
        "ask_user_answer": "All SKUs",
        "expected_tokens_le": TOKEN_CAP,
        "expected_tools_not_repeat": True,
        "expected_skus": ["SKU-001", "SKU-002"],
    },
    {
        "id": "Q5",
        "text": "Why is there a gap between demand forecast and actual demand?",
        "ask_user_answer": "All SKUs — analyze across the entire product catalog.",
        "expected_tokens_le": TOKEN_CAP,
        "expected_tools_not_repeat": True,
        "expected_skus": [],
    },
    {
        "id": "Q6",
        "text": "Which products may face supply shortages next week or next month?",
        "ask_user_answer": "All SKUs",
        "expected_tokens_le": TOKEN_CAP,
        # nl_query is a generic query tool that may be called multiple times with different
        # SQL — two different nl_query calls are NOT D-012 duplicates (different inputs).
        # The D-013 acceptance test for Q6 checks tool selection + SKU grounding, not
        # nl_query call count (which varies by model SQL planning strategy).
        "expected_tool": "nl_query",
        "expected_skus": [],
    },
    {
        "id": "Q8",
        "text": "Which materials or items should be purchased earlier or later?",
        "ask_user_answer": "All SKUs — analyze the entire supply order portfolio.",
        "expected_tokens_le": TOKEN_CAP,
        "expected_tools_not_repeat": True,
        "expected_skus": ["SKU-001"],
        "no_degenerate_prefix": True,
    },
]


async def create_session(client: httpx.AsyncClient) -> str:
    resp = await client.post(
        f"{API_BASE}/api/v1/sessions",
        json={"goal": "D-012/D-015 acceptance verification"},
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()["session_id"]


async def post_message(client: httpx.AsyncClient, session_id: str, message: str) -> None:
    await client.post(
        f"{API_BASE}/api/v1/sessions/{session_id}/messages",
        json={"content": message},
        timeout=30.0,
    )


async def post_answer(
    client: httpx.AsyncClient, session_id: str, ask_user_id: str, answer: str
) -> None:
    await client.post(
        f"{API_BASE}/api/v1/sessions/{session_id}/answer",
        json={"ask_user_id": ask_user_id, "answer": answer},
        timeout=30.0,
    )


async def run_question(
    client: httpx.AsyncClient,
    question: dict[str, Any],
    timeout_s: float = 300.0,
) -> dict[str, Any]:
    qid = question["id"]
    qtext = question["text"]
    ask_user_answer = question.get("ask_user_answer")

    print(f"\n{'='*70}", flush=True)
    print(f"{qid}: {qtext}", flush=True)

    session_id = await create_session(client)
    print(f"  Session: {session_id}", flush=True)

    all_events: list[dict[str, Any]] = []
    text_parts: list[str] = []
    ask_user_ids: list[str] = []
    phase1_done = asyncio.Event()

    async def sse_reader_phase1() -> None:
        try:
            async with client.stream(
                "GET",
                f"{API_BASE}/api/v1/sessions/{session_id}/stream",
                timeout=timeout_s + 10.0,
            ) as resp:
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    raw = line[6:].strip()
                    if not raw:
                        continue
                    try:
                        ev = json.loads(raw)
                        all_events.append(ev)
                        if ev.get("type") == "text_delta":
                            text_parts.append(ev.get("delta", ""))
                        if ev.get("type") == "ask_user_required":
                            ask_user_ids.append(ev.get("ask_user_id", ""))
                            phase1_done.set()
                            return
                        if ev.get("type") in ("done", "error"):
                            phase1_done.set()
                            return
                    except json.JSONDecodeError:
                        pass
        except Exception as exc:
            print(f"  WARNING: SSE phase1 exception: {exc}", flush=True)
            phase1_done.set()

    reader_task = asyncio.create_task(sse_reader_phase1())
    await asyncio.sleep(0.4)
    await post_message(client, session_id, qtext)

    try:
        await asyncio.wait_for(phase1_done.wait(), timeout=timeout_s)
    except asyncio.TimeoutError:
        print(f"  WARNING: SSE phase1 timed out after {timeout_s}s", flush=True)

    reader_task.cancel()
    try:
        await reader_task
    except (asyncio.CancelledError, Exception):
        pass

    if ask_user_ids and ask_user_answer:
        print(f"  INFO — ask_user: answering {ask_user_answer!r}", flush=True)
        await asyncio.sleep(0.5)

        resume_text: list[str] = []
        resume_done = asyncio.Event()

        async def sse_reader_resume() -> None:
            try:
                async with client.stream(
                    "GET",
                    f"{API_BASE}/api/v1/sessions/{session_id}/stream",
                    timeout=timeout_s + 10.0,
                ) as resp:
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        raw = line[6:].strip()
                        if not raw:
                            continue
                        try:
                            ev = json.loads(raw)
                            all_events.append(ev)
                            if ev.get("type") == "text_delta":
                                resume_text.append(ev.get("delta", ""))
                            if ev.get("type") in ("done", "error"):
                                resume_done.set()
                                return
                        except json.JSONDecodeError:
                            pass
            except Exception as exc:
                print(f"  WARNING: SSE resume exception: {exc}", flush=True)
                resume_done.set()

        resume_task = asyncio.create_task(sse_reader_resume())
        await asyncio.sleep(0.4)
        await post_answer(client, session_id, ask_user_ids[0], ask_user_answer)

        try:
            await asyncio.wait_for(resume_done.wait(), timeout=timeout_s)
        except asyncio.TimeoutError:
            print(f"  WARNING: SSE resume timed out after {timeout_s}s", flush=True)

        resume_task.cancel()
        try:
            await resume_task
        except (asyncio.CancelledError, Exception):
            pass

        final_reply = "".join(resume_text)
    else:
        final_reply = "".join(text_parts)

    # Extract tool calls.
    # Group tool start events by parent_run_id (the agent run they belong to).
    # Each goal-refinement loop creates a separate agent run (new AgentRuntime.run() call).
    # A "duplicate" is only meaningful WITHIN a single agent run — calling the same tool
    # once per refinement pass is expected and NOT a duplicate (D-012 fix is per-run).
    tool_start_events = [
        e for e in all_events if e.get("kind") == "tool" and e.get("event") == "start"
    ]
    tool_names = [e.get("name", "?") for e in tool_start_events]
    # Build per-agent-run tool name lists to detect within-run duplicates only.
    from collections import defaultdict
    _run_tools: dict[str, list[str]] = defaultdict(list)
    for te in tool_start_events:
        parent = te.get("parent_run_id") or "unknown"
        _run_tools[parent].append(te.get("name", "?"))
    tool_names_per_run: dict[str, list[str]] = dict(_run_tools)

    # Extract the peak per-call input_tokens from session_events (true Ollama context signal).
    # The graph_node "end" event for kind="agent" carries token_cost.peak_input_tokens
    # which is the maximum single-call Ollama-reported context-window usage for that agent run.
    #
    # Authorization signal hierarchy (D-012 fix):
    #   CORRECT: token_cost.peak_input_tokens  — max single-call KV-cache usage from
    #            ai_msg.usage_metadata.input_tokens; reflects actual Ollama context fill.
    #   WRONG:   token_cost.input_tokens (legacy) — was the operator.add SUM of all calls;
    #            always > num_ctx for multi-call runs → inflated numbers, not saturation signal.
    #   WRONG:   llm_usage.input_tokens (DB table) — pre-truncation prompt size from the
    #            LLM client; max ~5K even when context is saturated.
    agent_end_events = [
        e for e in all_events
        if e.get("type") == "graph_node"
        and e.get("event") == "end"
        and e.get("kind") == "agent"
    ]
    max_ollama_tokens: int | None = None
    token_calls_raw: list[int] = []
    for ae in agent_end_events:
        tc = ae.get("token_cost")
        if tc and isinstance(tc, dict):
            # Prefer peak_input_tokens (D-012 fix); fall back to input_tokens for
            # agent_end events emitted by older code before the fix was deployed.
            peak = tc.get("peak_input_tokens") or 0
            it = peak if peak > 0 else tc.get("input_tokens", 0)
            if it:
                token_calls_raw.append(it)
    # Note: a zero token_cost is still a valid signal (context within limits).
    # Only skip entries where token_cost dict is completely absent.
    if token_calls_raw or (agent_end_events and any(
        e.get("token_cost") is not None for e in agent_end_events
    )):
        max_ollama_tokens = max(token_calls_raw) if token_calls_raw else 0

    # text_reset events
    text_reset_events = [e for e in all_events if e.get("type") == "text_reset"]

    print(f"  Tools called: {tool_names}", flush=True)
    if max_ollama_tokens is not None:
        pct = max_ollama_tokens / NUM_CTX * 100
        flag = " [OVER 90%!]" if max_ollama_tokens > TOKEN_CAP else " [OK]"
        print(f"  Ollama input_tokens (true signal): {max_ollama_tokens} ({pct:.1f}%){flag}",
              flush=True)
    else:
        print("  Ollama input_tokens: not found in agent_end events", flush=True)
    if text_reset_events:
        print(f"  text_reset events: {len(text_reset_events)}", flush=True)
    print(f"  Reply preview: {final_reply[:500].replace(chr(10), ' ')}", flush=True)

    return {
        "id": qid,
        "text": qtext,
        "session_id": session_id,
        "final_reply": final_reply,
        "tool_names": tool_names,
        "tool_names_per_run": tool_names_per_run,
        "max_ollama_tokens": max_ollama_tokens,
        "token_calls": token_calls_raw,
        "text_reset_count": len(text_reset_events),
    }


def check_acceptance(result: dict[str, Any], spec: dict[str, Any]) -> list[str]:
    """Return list of FAIL reasons. Empty list = PASS."""
    fails: list[str] = []
    qid = result["id"]

    # Token check: None means the agent_end event had no token_cost at all (data absent).
    # Zero is a valid value (peak < 1 token is fine — within limits).
    tok = result.get("max_ollama_tokens")
    if tok is None:
        fails.append(f"{qid}: max_ollama_tokens not found (cannot verify context usage)")
    elif tok > TOKEN_CAP:
        fails.append(
            f"{qid}: max_ollama_tokens={tok} exceeds 90% cap ({TOKEN_CAP}) — "
            f"context overflow NOT fixed"
        )

    # Tool duplication check — evaluated PER AGENT RUN, not across the full session.
    # The goal-refinement loop creates separate AgentRuntime.run() calls; calling the
    # same tool once per refinement pass is expected behavior (not a D-012 duplicate).
    # D-012 dedupe prevents the same tool being called twice WITHIN a single agent run.
    if spec.get("expected_tools_not_repeat"):
        per_run = result.get("tool_names_per_run") or {}
        if per_run:
            for run_id, run_tools in per_run.items():
                seen: set[str] = set()
                for t in run_tools:
                    if t in seen:
                        fails.append(
                            f"{qid}: within-run duplicate tool execution: {t!r} "
                            f"(run_id={run_id!r})"
                        )
                    seen.add(t)
        else:
            # Fallback when parent_run_id is missing: check globally (conservative)
            tools = result.get("tool_names", [])
            seen_global: set[str] = set()
            for t in tools:
                if t in seen_global:
                    fails.append(f"{qid}: duplicate tool execution detected: {t!r}")
                seen_global.add(t)

    # Tool selection check (Q6) — uses all tool names across all runs
    all_tools = result.get("tool_names", [])
    expected_tool = spec.get("expected_tool")
    if expected_tool and expected_tool not in all_tools:
        fails.append(
            f"{qid}: expected tool {expected_tool!r} was not called; tools={all_tools}"
        )

    # SKU grounding check
    reply = result.get("final_reply", "")
    for sku in spec.get("expected_skus", []):
        if sku not in reply:
            fails.append(f"{qid}: expected SKU {sku!r} not found in reply")

    # Degenerate prefix check
    if spec.get("no_degenerate_prefix"):
        lower = reply.lower()
        apology_markers = ["i'm sorry", "i am sorry", "i don't have", "cannot provide"]
        for marker in apology_markers:
            if reply.lower().startswith(marker) or (
                len(reply) > 10 and marker in lower[:200]
            ):
                fails.append(
                    f"{qid}: degenerate apology prefix found in reply start: {reply[:200]!r}"
                )
                break

    # Non-English fragment check (basic)
    non_english_markers = ["désolé", "je ne", "je dispose", "rupture", "données"]
    for marker in non_english_markers:
        if marker in reply.lower():
            fails.append(f"{qid}: non-English fragment detected: {marker!r}")

    return fails


async def main() -> None:
    print("D-012/D-013/D-014/D-015 Acceptance Verification", flush=True)
    print(f"Context cap: ≤{TOKEN_CAP} tokens ({TOKEN_CAP_RATIO*100:.0f}% of {NUM_CTX})",
          flush=True)
    print("=" * 70, flush=True)

    async with httpx.AsyncClient(timeout=360.0) as client:
        try:
            health = await client.get(f"{API_BASE}/healthz", timeout=10.0)
            health.raise_for_status()
            print(f"API health: {health.json()}", flush=True)
        except Exception as exc:
            print(f"ERROR: API not reachable: {exc}", flush=True)
            sys.exit(1)

        all_fails: list[str] = []
        for spec in ACCEPTANCE_QUESTIONS:
            result = await run_question(client, spec)
            fails = check_acceptance(result, spec)
            if fails:
                print("  FAIL:", flush=True)
                for f in fails:
                    print(f"    - {f}", flush=True)
            else:
                print("  PASS", flush=True)
            all_fails.extend(fails)
            await asyncio.sleep(2.0)

    print("\n" + "=" * 70, flush=True)
    if all_fails:
        print(f"VERIFICATION FAILED — {len(all_fails)} issues:", flush=True)
        for f in all_fails:
            print(f"  {f}", flush=True)
        sys.exit(1)
    else:
        print("ALL 4 ACCEPTANCE QUESTIONS PASSED", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
