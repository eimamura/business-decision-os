/**
 * T-314: Live execution trace — mixed mock/real backend.
 *
 * Tests 1–3 use mock SSE interceptors (complete in under 30 s each).
 * Test 4 (trace persistence across page reload) intentionally keeps real
 * Ollama: it must verify that graph_node events were written to the database
 * and are correctly restored on reload, which the mock cannot simulate because
 * page.route() responses are never stored in the DB.
 *
 * Completion signal: "Completed" footer in the ExecutionPanel (appears when
 * sessionEndedAt is set from the response_ready SSE event).
 *
 * Requires: make dev-up  (web on WEB_PORT, api on API_PORT)
 * LLM (test 4 only): qwen2.5-coder:7b via Ollama ("Reply with the single
 * word: hello" completes in ~2–5 s on qwen2.5-coder:7b, up to 60 s on
 * slower models)
 */

import { testWithCleanup as test, expect } from "./fixtures";
import { mockCompletedStream } from "./sse-mock";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const SIMPLE_QUERY = "Reply with the single word: hello";

/** Timeout (ms) for mocked tests — the mock resolves in under 1 s. */
const MOCK_TIMEOUT = 15_000;
/** Timeout (ms) for the real-Ollama persistence test. */
const REAL_TIMEOUT = 90_000;

async function createSession(
  request: Parameters<typeof test>[1]["request"],
): Promise<string> {
  const res = await request.post(`${API_BASE}/api/v1/sessions`, {
    data: { goal: "Live trace verification" },
    headers: { "X-Dev-User": "dev-user" },
  });
  expect(res.ok()).toBeTruthy();
  const body = (await res.json()) as { session_id: string };
  return body.session_id;
}

/**
 * Send a message and wait until the ExecutionPanel shows a "Completed" footer.
 * Works for both mock (fast) and real Ollama (slow) runs.
 */
async function sendAndWaitForCompleted(
  page: import("@playwright/test").Page,
  query: string,
  timeout: number,
): Promise<void> {
  await expect(page.locator("textarea")).toBeVisible();
  await page.locator("textarea").fill(query);
  await page.getByRole("button", { name: /send/i }).click();
  await expect(page.locator("text=Completed").first()).toBeVisible({ timeout });
}

// ---------------------------------------------------------------------------

test.describe("Live execution trace", () => {
  test("Execution Trace panel shows nodes after a mocked run", async ({
    page,
    request,
    createdSessionIds,
  }) => {
    test.setTimeout(30_000);
    const sessionId = await createSession(request);
    createdSessionIds.push(sessionId);
    // Register the mock BEFORE goto so the route is active when the page loads.
    await mockCompletedStream(page, sessionId);

    await page.goto(`/chat/${sessionId}`);
    await sendAndWaitForCompleted(page, SIMPLE_QUERY, MOCK_TIMEOUT);

    // Every query starts with classify_intent.
    await expect(page.locator("text=Classifying intent")).toBeVisible({
      timeout: 3_000,
    });
    await page.screenshot({
      path: "test-results/live-nodes.png",
      fullPage: false,
    });
  });

  test("After completion: all nodes show checkmarks, no animate-spin remains", async ({
    page,
    request,
    createdSessionIds,
  }) => {
    test.setTimeout(30_000);
    const sessionId = await createSession(request);
    createdSessionIds.push(sessionId);
    await mockCompletedStream(page, sessionId);

    await page.goto(`/chat/${sessionId}`);
    await sendAndWaitForCompleted(page, SIMPLE_QUERY, MOCK_TIMEOUT);

    // All graph nodes should be completed after sessionEndedAt is set.
    const spinnerCount = await page.locator(".animate-spin").count();
    expect(spinnerCount).toBe(0);

    // At least one checkmark should be visible.
    await expect(page.locator("text=✓").first()).toBeVisible({ timeout: 3_000 });
    await page.screenshot({
      path: "test-results/live-checkmarks.png",
      fullPage: false,
    });
  });

  test("Send button becomes disabled while a message is in-flight", async ({
    page,
    request,
    createdSessionIds,
  }) => {
    // NOTE: The original test checked for ".animate-bounce" (streaming dots in
    // the assistant bubble).  With a near-instant mock SSE response the browser
    // may never paint the loading state.  Checking the send button's disabled
    // state is reliable because the UI disables it synchronously on click
    // (isSending=true) — the button is disabled before the mock response can
    // resolve.
    test.setTimeout(30_000);
    const sessionId = await createSession(request);
    createdSessionIds.push(sessionId);
    await mockCompletedStream(page, sessionId);

    await page.goto(`/chat/${sessionId}`);
    await expect(page.locator("textarea")).toBeVisible();

    await page.locator("textarea").fill(SIMPLE_QUERY);

    const sendBtn = page.getByRole("button", { name: /send/i });
    await sendBtn.click();

    // The send button must be disabled immediately after the click while the
    // response is in-flight (disabled={isSending || !input.trim()}).
    await expect(sendBtn).toBeDisabled({ timeout: 2_000 });

    await page.screenshot({
      path: "test-results/live-badge.png",
      fullPage: false,
    });
  });

  // -------------------------------------------------------------------------
  // Test 4: intentionally uses real Ollama so that graph_node events are
  // written to the database and can be verified after a page reload.
  // page.route() mocks are not stored in the DB, so this test cannot use them.
  // -------------------------------------------------------------------------

  test("Execution trace persists after page reload (real Ollama)", async ({
    page,
    request,
    createdSessionIds,
  }) => {
    test.setTimeout(REAL_TIMEOUT + 30_000);
    const sessionId = await createSession(request);
    createdSessionIds.push(sessionId);

    await page.goto(`/chat/${sessionId}`);
    await sendAndWaitForCompleted(page, SIMPLE_QUERY, REAL_TIMEOUT);

    // Count completed nodes before reload.
    const beforeCount = await page.locator("text=✓").count();
    expect(beforeCount).toBeGreaterThan(0);

    // Reload (simulates browser refresh / navigate-away-and-back).
    await page.reload();
    await expect(page.locator("textarea")).toBeVisible({ timeout: 10_000 });

    // Nodes must still appear after reload (loaded from persisted events in DB).
    await expect(page.locator("text=Classifying intent")).toBeVisible({
      timeout: 8_000,
    });
    const afterCount = await page.locator("text=✓").count();
    expect(afterCount).toBeGreaterThanOrEqual(beforeCount);

    await page.screenshot({
      path: "test-results/live-after-reload.png",
      fullPage: false,
    });
  });
});
