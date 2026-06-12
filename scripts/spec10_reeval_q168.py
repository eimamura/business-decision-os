"""Re-evaluation of Q1, Q6, Q8 after D-012..D-015 fixes (P100 T-598 re-run).

Runs Q1, Q6, Q8 through the live dev stack with fresh sessions.
Captures: reply text, tool events, peak_input_tokens, error events, language purity.

Usage:
    uv run python scripts/spec10_reeval_q168.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

import httpx

API_BASE = "http://localhost:8002"
NUM_CTX = 16384

# Only the three previously-FAILed questions — EXACT SPEC wording
REEVAL_QUESTIONS = [
    {
        "id": "Q1",
        "text": "Which products are at risk of stockout?",
        "ask_user_answer": "All SKUs",
    },
    {
        "id": "Q6",
        "text": "Which products may face supply shortages next week or next month?",
        "ask_user_answer": "All SKUs",
    },
    {
        "id": "Q8",
        "text": "Which materials or items should be purchased earlier or later?",
        "ask_user_answer": "All SKUs — analyze the entire supply order portfolio.",
    },
]


async def create_session(client: httpx.AsyncClient) -> str:
    resp = await client.post(
        f"{API_BASE}/api/v1/sessions",
        json={"goal": "SPEC reeval Q1/Q6/Q8 after D-012..D-015"},
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
    text_reset_received = False
    phase1_done = asyncio.Event()

    async def sse_reader_phase1() -> None:
        nonlocal text_reset_received
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
                        if ev.get("type") == "text_reset":
                            text_reset_received = True
                            text_parts.clear()
                            reason = ev.get("reason")
                            print(f"  INFO — text_reset received (reason={reason})", flush=True)
                        elif ev.get("type") == "text_delta":
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
            nonlocal text_reset_received
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
                            if ev.get("type") == "text_reset":
                                text_reset_received = True
                                resume_text.clear()
                                reason = ev.get("reason")
                                print(
                                    f"  INFO — text_reset received in resume (reason={reason})",
                                    flush=True,
                                )
                            elif ev.get("type") == "text_delta":
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

    # Extract tool calls — try both event schema variants
    tool_start_events = [
        e for e in all_events
        if (e.get("kind") == "tool" and e.get("event") == "start")
        or e.get("type") == "tool_start"
    ]
    tool_error_events = [
        e for e in all_events
        if (e.get("kind") == "tool" and e.get("event") == "error")
        or e.get("type") == "tool_error"
    ]
    tool_names = [e.get("name", e.get("tool_name", "?")) for e in tool_start_events]

    # Extract error events
    error_events = [e for e in all_events if e.get("type") == "error"]

    # Extract peak_input_tokens from graph_node "end" events (D-012 authoritative signal)
    peak_input_tokens: int | None = None
    for ev in all_events:
        # token_cost payload in graph_node end event
        if ev.get("type") == "graph_node" and ev.get("event") == "end":
            payload = ev.get("payload") or {}
            tc = payload.get("token_cost") or {}
            pit = tc.get("peak_input_tokens")
            if pit:
                if peak_input_tokens is None or pit > peak_input_tokens:
                    peak_input_tokens = pit

    # Fallback: look for any event with peak_input_tokens or input_tokens
    if peak_input_tokens is None:
        for ev in all_events:
            pit = ev.get("peak_input_tokens")
            if pit and (peak_input_tokens is None or pit > peak_input_tokens):
                peak_input_tokens = pit
        if peak_input_tokens is None:
            token_events = [e for e in all_events if "input_tokens" in e]
            if token_events:
                token_vals = [e.get("input_tokens", 0) for e in token_events]
                peak_input_tokens = max(token_vals)

    print(f"  Tools called: {tool_names}", flush=True)
    if peak_input_tokens is not None:
        pct = peak_input_tokens / NUM_CTX * 100
        over_flag = " [OVER 100%]" if peak_input_tokens > NUM_CTX else (
            " [OVER 70%]" if peak_input_tokens > int(NUM_CTX * 0.70) else ""
        )
        print(f"  peak_input_tokens: {peak_input_tokens} ({pct:.1f}%){over_flag}", flush=True)
    else:
        print("  peak_input_tokens: not found in SSE events", flush=True)

    if text_reset_received:
        print("  text_reset: YES (degenerate-drop fired)", flush=True)
    else:
        print("  text_reset: NO", flush=True)

    if error_events:
        print(f"  ERROR events: {error_events}", flush=True)
    else:
        print("  No error events", flush=True)

    reply_preview = final_reply[:1000].replace("\n", " | ")
    print(f"  Reply preview: {reply_preview}", flush=True)
    print(f"  Reply length: {len(final_reply)} chars", flush=True)

    return {
        "id": qid,
        "text": qtext,
        "session_id": session_id,
        "final_reply": final_reply,
        "tool_names": tool_names,
        "tool_start_count": len(tool_start_events),
        "tool_error_count": len(tool_error_events),
        "error_events": error_events,
        "peak_input_tokens": peak_input_tokens,
        "text_reset_received": text_reset_received,
        "ask_user_triggered": bool(ask_user_ids),
        "all_events_count": len(all_events),
        "all_events": all_events,  # for post-hoc inspection
    }


async def main() -> None:
    print("SPEC Re-evaluation: Q1, Q6, Q8 after D-012..D-015", flush=True)
    print(f"API: {API_BASE}", flush=True)
    print(f"num_ctx: {NUM_CTX}", flush=True)
    print("=" * 70, flush=True)

    async with httpx.AsyncClient(timeout=360.0) as client:
        # Health check
        try:
            health = await client.get(f"{API_BASE}/healthz", timeout=10.0)
            health.raise_for_status()
            print(f"API health: {health.json()}", flush=True)
        except Exception as exc:
            print(f"ERROR: API not reachable at {API_BASE}: {exc}", flush=True)
            sys.exit(1)

        results = []
        for question in REEVAL_QUESTIONS:
            result = await run_question(client, question)
            results.append(result)
            await asyncio.sleep(2.0)

    # Final summary
    print("\n" + "=" * 70, flush=True)
    print("RE-EVALUATION COMPLETE", flush=True)
    print("=" * 70, flush=True)
    for r in results:
        tok_str = f"{r['peak_input_tokens']}t" if r["peak_input_tokens"] else "N/A"
        tok_pct = (
            f" ({r['peak_input_tokens']/NUM_CTX*100:.0f}%)"
            if r["peak_input_tokens"]
            else ""
        )
        over = (
            " [OVER 100%]"
            if r["peak_input_tokens"] and r["peak_input_tokens"] > NUM_CTX
            else ""
        )
        err_str = f" ERRORS={len(r['error_events'])}" if r["error_events"] else ""
        reset_str = " text_reset=YES" if r["text_reset_received"] else ""
        print(
            f"  {r['id']}: tools={r['tool_names']} | "
            f"peak={tok_str}{tok_pct}{over}{err_str}{reset_str} | "
            f"reply_len={len(r['final_reply'])}",
            flush=True,
        )

    # JSON dump for parsing
    # Strip all_events from JSON (too large) but keep key fields
    for r in results:
        r.pop("all_events", None)
    print("\n===JSON_RESULTS_START===", flush=True)
    print(json.dumps(results, indent=2), flush=True)
    print("===JSON_RESULTS_END===", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
