"""SPEC 10-Question Judge Evaluation Campaign — P100 T-598.

Runs each of the 10 SPEC questions through the live dev stack sequentially,
capturing reply text, tool events, llm_usage token info, and error events.
Results are printed to stdout for collection by the bdos-judge agent.

Usage:
    uv run python scripts/spec10_judge_campaign.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

import httpx

API_BASE = "http://localhost:8002"
NUM_CTX = 16384
TOKEN_LIMIT_RATIO = 0.70
TOKEN_LIMIT = int(NUM_CTX * TOKEN_LIMIT_RATIO)  # 11469

# Exact question wording from docs/SPEC.md
SPEC_QUESTIONS = [
    {
        "id": "Q1",
        "text": "Which products are at risk of stockout?",
        "ask_user_answer": "All SKUs",
    },
    {
        "id": "Q2",
        "text": "Which products have excess inventory?",
        "ask_user_answer": "All SKUs",
    },
    {
        "id": "Q3",
        "text": "What exceptions require human judgment today?",
        "ask_user_answer": None,
    },
    {
        "id": "Q4",
        "text": "What is causing shipment delays or unshipped orders?",
        "ask_user_answer": None,
    },
    {
        "id": "Q5",
        "text": "Why is there a gap between demand forecast and actual demand?",
        "ask_user_answer": "All SKUs — analyze across the entire product catalog.",
    },
    {
        "id": "Q6",
        "text": "Which products may face supply shortages next week or next month?",
        "ask_user_answer": "All SKUs",
    },
    {
        "id": "Q7",
        "text": "Which products require production plan adjustments?",
        "ask_user_answer": None,
    },
    {
        "id": "Q8",
        "text": "Which materials or items should be purchased earlier or later?",
        "ask_user_answer": "All SKUs — analyze the entire supply order portfolio.",
    },
    {
        "id": "Q9",
        "text": "Are there demand changes by customer or region?",
        "ask_user_answer": None,
    },
    {
        "id": "Q10",
        "text": "Which constraint is having the biggest negative impact on sales or profit?",
        "ask_user_answer": None,
    },
]


async def create_session(client: httpx.AsyncClient) -> str:
    resp = await client.post(
        f"{API_BASE}/api/v1/sessions",
        json={"goal": "SPEC 10-question evaluation campaign P100 T-598"},
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
    timeout_s: float = 240.0,
) -> dict[str, Any]:
    """Run one question through a fresh session. Returns a result dict."""
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

    # Handle ask_user if triggered and we have an answer
    if ask_user_ids and ask_user_answer:
        print(f"  INFO — ask_user triggered: {ask_user_ids[0]}", flush=True)
        print(f"  INFO — answering: {ask_user_answer!r}", flush=True)
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

    # Extract tool calls
    tool_start_events = [
        e for e in all_events if e.get("kind") == "tool" and e.get("event") == "start"
    ]
    tool_error_events = [
        e for e in all_events if e.get("kind") == "tool" and e.get("event") == "error"
    ]
    tool_names = [e.get("name", "?") for e in tool_start_events]

    # Extract error events
    error_events = [e for e in all_events if e.get("type") == "error"]

    # Extract token usage from SSE
    token_events = [e for e in all_events if "input_tokens" in e]
    max_input_tokens: int | None = None
    token_calls: list[int] = []
    if token_events:
        token_calls = [e.get("input_tokens", 0) for e in token_events]
        max_input_tokens = max(token_calls)

    print(f"  Tools called: {tool_names}", flush=True)
    if max_input_tokens is not None:
        pct = max_input_tokens / NUM_CTX * 100
        flag = " [OVER 70%]" if max_input_tokens > TOKEN_LIMIT else ""
        print(f"  Max input_tokens: {max_input_tokens} ({pct:.1f}%){flag}", flush=True)
    else:
        print("  Max input_tokens: not in SSE events", flush=True)

    if error_events:
        print(f"  ERROR events: {error_events}", flush=True)
    else:
        print("  No error events", flush=True)

    reply_preview = final_reply[:800].replace("\n", " ")
    print(f"  Reply preview: {reply_preview}", flush=True)

    return {
        "id": qid,
        "text": qtext,
        "session_id": session_id,
        "final_reply": final_reply,
        "tool_names": tool_names,
        "tool_start_count": len(tool_start_events),
        "tool_error_count": len(tool_error_events),
        "error_events": error_events,
        "max_input_tokens": max_input_tokens,
        "token_calls": token_calls,
        "ask_user_triggered": bool(ask_user_ids),
        "all_events_count": len(all_events),
    }


async def main() -> None:
    print("SPEC 10-Question Judge Evaluation Campaign", flush=True)
    print(f"Token limit: {TOKEN_LIMIT} ({TOKEN_LIMIT_RATIO*100:.0f}% of {NUM_CTX})", flush=True)
    print("=" * 70, flush=True)

    async with httpx.AsyncClient(timeout=300.0) as client:
        # Health check
        try:
            health = await client.get(f"{API_BASE}/healthz", timeout=10.0)
            health.raise_for_status()
            print(f"API health: {health.json()}", flush=True)
        except Exception as exc:
            print(f"ERROR: API not reachable at {API_BASE}: {exc}", flush=True)
            sys.exit(1)

        results = []
        for question in SPEC_QUESTIONS:
            result = await run_question(client, question)
            results.append(result)
            # Small gap between questions to avoid session state collisions
            await asyncio.sleep(1.0)

    # Final summary
    print("\n" + "=" * 70, flush=True)
    print("CAMPAIGN COMPLETE — RESULTS SUMMARY", flush=True)
    print("=" * 70, flush=True)
    for r in results:
        tok_str = f"{r['max_input_tokens']}t" if r["max_input_tokens"] else "N/A"
        tok_pct = (
            f" ({r['max_input_tokens']/NUM_CTX*100:.0f}%)" if r["max_input_tokens"] else ""
        )
        over = " [OVER]" if r["max_input_tokens"] and r["max_input_tokens"] > TOKEN_LIMIT else ""
        err_str = f" ERRORS={len(r['error_events'])}" if r["error_events"] else ""
        print(
            f"  {r['id']}: tools={r['tool_names']} | "
            f"max_tokens={tok_str}{tok_pct}{over}{err_str} | "
            f"reply_len={len(r['final_reply'])}",
            flush=True,
        )

    # JSON dump for parsing
    print("\n===JSON_RESULTS_START===", flush=True)
    print(json.dumps(results, indent=2), flush=True)
    print("===JSON_RESULTS_END===", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
