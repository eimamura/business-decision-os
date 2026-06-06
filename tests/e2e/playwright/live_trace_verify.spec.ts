/**
 * Live verification — no mocks, real Ollama backend.
 *
 * Completion signal: "Completed" footer in the ExecutionPanel (appears when
 * sessionEndedAt is set from the response_ready SSE event). This is more
 * reliable than checking the send button, which stays disabled whenever the
 * input is empty (disabled={isSending || !input.trim()}).
 *
 * Requires: make dev-up  (web on WEB_PORT, api on API_PORT)
 * LLM: qwen2.5-coder:7b via Ollama (simple queries complete in ~2–5s)
 */

import { testWithCleanup as test, expect } from "./fixtures";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const SIMPLE_QUERY = "Reply with the single word: hello";
// gpt-oss:20b is slower than qwen2.5-coder:7b; allow up to 150s.
const DONE_TIMEOUT = 150_000;

async function createSession(request: Parameters<typeof test>[1]["request"]): Promise<string> {
  const res = await request.post(`${API_BASE}/api/v1/sessions`, {
    data: { goal: "Live trace verification" },
    headers: { "X-Dev-User": "dev-user" },
  });
  expect(res.ok()).toBeTruthy();
  const body = (await res.json()) as { session_id: string };
  return body.session_id;
}

/**
 * Send a message and wait until the ExecutionPanel shows a "Completed" footer,
 * which is set from the response_ready SSE event (sessionEndedAt is set).
 */
async function sendAndWaitForCompleted(
  page: import("@playwright/test").Page,
  query: string,
): Promise<void> {
  await expect(page.locator("textarea")).toBeVisible();
  await page.locator("textarea").fill(query);
  await page.getByRole("button", { name: /send/i }).click();
  // "Completed" appears both in per-node "Completed · Xs" labels and in the
  // ExecutionPanel footer "Completed {timestamp} · {n}s total" when sessionEndedAt is set.
  // Matching on the first occurrence is sufficient for live_trace tests because these
  // use a simple prompt that does not trigger the ask_user path; the session completes
  // before the node-level "Completed" text is rendered.
  await expect(page.locator("text=Completed").first()).toBeVisible({ timeout: DONE_TIMEOUT });
}

// ---------------------------------------------------------------------------

test.describe("Live execution trace (real Ollama backend)", () => {
  test("Execution Trace panel shows nodes after a live run", async ({
    page,
    request,
    createdSessionIds,
  }) => {
    test.setTimeout(180_000);
    const sessionId = await createSession(request);
    createdSessionIds.push(sessionId);

    await page.goto(`/chat/${sessionId}`);
    await sendAndWaitForCompleted(page, SIMPLE_QUERY);

    // Every query starts with classify_intent.
    await expect(page.locator("text=Classifying intent")).toBeVisible({ timeout: 3_000 });
    await page.screenshot({ path: "test-results/live-nodes.png", fullPage: false });
  });

  test("After completion: all nodes show ✓, no animate-spin remains", async ({
    page,
    request,
    createdSessionIds,
  }) => {
    test.setTimeout(180_000);
    const sessionId = await createSession(request);
    createdSessionIds.push(sessionId);

    await page.goto(`/chat/${sessionId}`);
    await sendAndWaitForCompleted(page, SIMPLE_QUERY);

    // All graph nodes should be completed after sessionEndedAt is set.
    const spinnerCount = await page.locator(".animate-spin").count();
    expect(spinnerCount).toBe(0);

    // At least one checkmark should be visible.
    await expect(page.locator("text=✓").first()).toBeVisible({ timeout: 3_000 });
    await page.screenshot({ path: "test-results/live-checkmarks.png", fullPage: false });
  });

  test("Streaming dots (animate-bounce) appear in assistant bubble while sending", async ({
    page,
    request,
    createdSessionIds,
  }) => {
    test.setTimeout(180_000);
    const sessionId = await createSession(request);
    createdSessionIds.push(sessionId);

    await page.goto(`/chat/${sessionId}`);
    await expect(page.locator("textarea")).toBeVisible();

    // Wait for the streaming dots in the assistant bubble — appear when isSending=true.
    // (animate-bounce is unique to the assistant loading indicator)
    const livePromise = page
      .locator(".animate-bounce")
      .first()
      .waitFor({ state: "visible", timeout: 15_000 });

    await page.locator("textarea").fill(SIMPLE_QUERY);
    await page.getByRole("button", { name: /send/i }).click();

    // animate-bounce dots appear immediately when isSending becomes true.
    await livePromise;

    await page.screenshot({ path: "test-results/live-badge.png", fullPage: false });

    // Note: animate-spin per node is tested via mock in realtime_trace_persistence.spec.ts.
    // In a live environment, fast queries (~2s) deliver all SSE events in a single
    // buffered chunk via the Next.js rewrite proxy, so all nodes transition to
    // "completed" in one React render — the "running" state is never painted.
  });

  test("Execution trace persists after page reload", async ({
    page,
    request,
    createdSessionIds,
  }) => {
    test.setTimeout(240_000);
    const sessionId = await createSession(request);
    createdSessionIds.push(sessionId);

    await page.goto(`/chat/${sessionId}`);
    await sendAndWaitForCompleted(page, SIMPLE_QUERY);

    // Count completed nodes before reload.
    const beforeCount = await page.locator("text=✓").count();
    expect(beforeCount).toBeGreaterThan(0);

    // Reload (simulates browser refresh / navigate-away-and-back).
    await page.reload();
    await expect(page.locator("textarea")).toBeVisible({ timeout: 10_000 });

    // Nodes must still appear after reload (loaded from persisted events).
    await expect(page.locator("text=Classifying intent")).toBeVisible({ timeout: 8_000 });
    const afterCount = await page.locator("text=✓").count();
    expect(afterCount).toBeGreaterThanOrEqual(beforeCount);

    await page.screenshot({ path: "test-results/live-after-reload.png", fullPage: false });
  });
});
