/**
 * T-312: Tool scenario assistant bubble tests — mock SSE interceptors.
 *
 * Verifies that sending each tool scenario prompt results in a non-empty,
 * non-error assistant bubble.  The SSE stream and GET /messages endpoint are
 * intercepted by page.route() so tests complete in under 15 s instead of up
 * to 180 s with real Ollama.
 *
 * Real sessions are created via the API (we need a genuine session_id for the
 * route patterns to match).  The POST /messages call fires to the real API and
 * may spawn an orphaned Ollama request in the background; that is harmless
 * because we never wait for it.
 *
 * Run with:
 *   make dev-up   (starts web + api)
 *   make test-playwright
 */

import { testWithCleanup as test, expect } from "./fixtures";
import { mockCompletedStream } from "./sse-mock";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
/** Maximum time (ms) to wait for the mocked "Completed · total" footer. */
const MOCK_TIMEOUT = 15_000;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function createSession(
  request: Parameters<typeof test>[1]["request"],
  goal: string,
): Promise<string> {
  const res = await request.post(`${API_BASE}/api/v1/sessions`, {
    data: { goal },
    headers: { "X-Dev-User": "dev-user" },
  });
  expect(res.ok()).toBeTruthy();
  const body = (await res.json()) as { session_id: string };
  return body.session_id;
}

/**
 * Navigate to the chat page, fill the textarea with the given prompt,
 * click Send, and wait until the "Completed · total" footer appears in the
 * ExecutionPanel (set when the response_ready SSE event fires).
 *
 * With the mock SSE interceptor in place this resolves in under 1 s.
 */
async function sendPromptAndWaitForCompleted(
  page: import("@playwright/test").Page,
  prompt: string,
): Promise<void> {
  await expect(page.locator("textarea")).toBeVisible();
  await page.locator("textarea").fill(prompt);
  await page.getByRole("button", { name: /send/i }).click();
  // The ExecutionPanel footer shows "Completed {timestamp} · {duration}s total"
  // when sessionEndedAt is set.  Match /total/ so we only resolve on the
  // footer, not on per-node "Completed · Xs" duration labels.
  await expect(page.locator("text=/total/").first()).toBeVisible({
    timeout: MOCK_TIMEOUT,
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe("Tool scenario assistant bubbles (mock SSE)", () => {
  test("Data Query scenario produces assistant bubble", async ({
    page,
    request,
    createdSessionIds,
  }) => {
    test.setTimeout(30_000);
    const sessionId = await createSession(request, "Data Query scenario test");
    createdSessionIds.push(sessionId);
    // Register the mock BEFORE goto so the route is active when the page loads.
    await mockCompletedStream(page, sessionId);

    await page.goto(`/chat/${sessionId}`);
    await sendPromptAndWaitForCompleted(
      page,
      "在庫テーブルから全SKUの現在庫数をSQLで直接取得して",
    );

    const bubble = page.locator(".rounded-2xl.bg-\\[\\#1a1a2a\\]").first();
    await expect(bubble).toBeVisible({ timeout: 5_000 });
    await expect(bubble).not.toBeEmpty();
    expect(await bubble.getAttribute("class")).not.toContain("text-red-400");
  });

  test("Forecasting scenario produces assistant bubble", async ({
    page,
    request,
    createdSessionIds,
  }) => {
    test.setTimeout(30_000);
    const sessionId = await createSession(request, "Forecasting scenario test");
    createdSessionIds.push(sessionId);
    await mockCompletedStream(page, sessionId);

    await page.goto(`/chat/${sessionId}`);
    await sendPromptAndWaitForCompleted(
      page,
      "Use the analyze_demand_trend tool to analyze the demand trend for SKU-001 for the last 30 days and show the results.",
    );

    const bubble = page.locator(".rounded-2xl.bg-\\[\\#1a1a2a\\]").first();
    await expect(bubble).toBeVisible({ timeout: 5_000 });
    await expect(bubble).not.toBeEmpty();
    expect(await bubble.getAttribute("class")).not.toContain("text-red-400");
  });

  test("Simulation scenario produces assistant bubble", async ({
    page,
    request,
    createdSessionIds,
  }) => {
    test.setTimeout(30_000);
    const sessionId = await createSession(request, "Simulation scenario test");
    createdSessionIds.push(sessionId);
    await mockCompletedStream(page, sessionId);

    await page.goto(`/chat/${sessionId}`);
    await sendPromptAndWaitForCompleted(
      page,
      "Use the calculate_supply_gap tool to check the supply gap for SKU-001 at DC West and show the result.",
    );

    const bubble = page.locator(".rounded-2xl.bg-\\[\\#1a1a2a\\]").first();
    await expect(bubble).toBeVisible({ timeout: 5_000 });
    await expect(bubble).not.toBeEmpty();
    expect(await bubble.getAttribute("class")).not.toContain("text-red-400");
  });

  test("Optimization scenario produces assistant bubble", async ({
    page,
    request,
    createdSessionIds,
  }) => {
    test.setTimeout(30_000);
    const sessionId = await createSession(request, "Optimization scenario test");
    createdSessionIds.push(sessionId);
    await mockCompletedStream(page, sessionId);

    await page.goto(`/chat/${sessionId}`);
    await sendPromptAndWaitForCompleted(
      page,
      "Use the calculate_days_of_inventory tool to calculate inventory days on hand for SKU-001 and show the result.",
    );

    const bubble = page.locator(".rounded-2xl.bg-\\[\\#1a1a2a\\]").first();
    await expect(bubble).toBeVisible({ timeout: 5_000 });
    await expect(bubble).not.toBeEmpty();
    expect(await bubble.getAttribute("class")).not.toContain("text-red-400");
  });

  test("Data Catalog scenario produces assistant bubble", async ({
    page,
    request,
    createdSessionIds,
  }) => {
    test.setTimeout(30_000);
    const sessionId = await createSession(request, "Data Catalog scenario test");
    createdSessionIds.push(sessionId);
    await mockCompletedStream(page, sessionId);

    await page.goto(`/chat/${sessionId}`);
    await sendPromptAndWaitForCompleted(
      page,
      "利用可能なデータテーブル一覧をカタログから検索して",
    );

    const bubble = page.locator(".rounded-2xl.bg-\\[\\#1a1a2a\\]").first();
    await expect(bubble).toBeVisible({ timeout: 5_000 });
    await expect(bubble).not.toBeEmpty();
    expect(await bubble.getAttribute("class")).not.toContain("text-red-400");
  });
});
