/**
 * T-263: Tool scenario assistant bubble tests — real Ollama backend.
 *
 * Verifies that sending each tool scenario prompt results in a non-empty,
 * non-error assistant bubble. Requires a running API server and Ollama.
 *
 * Run with:
 *   make dev-up   (starts web + api + Ollama)
 *   make test-playwright
 */

import { testWithCleanup as test, expect } from "./fixtures";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
// gpt-oss:20b is slower than qwen2.5-coder:7b; allow up to 180s.
const OLLAMA_TIMEOUT = 180_000;

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
 * click Send, and wait until the "Completed" footer appears in the
 * ExecutionPanel (set when the response_ready SSE event fires).
 */
async function sendPromptAndWaitForCompleted(
  page: import("@playwright/test").Page,
  sessionId: string,
  prompt: string,
): Promise<void> {
  await page.goto(`/chat/${sessionId}`);
  await expect(page.locator("textarea")).toBeVisible();
  await page.locator("textarea").fill(prompt);
  await page.getByRole("button", { name: /send/i }).click();
  // The ExecutionPanel footer shows "Completed {timestamp} · {duration}s total" when
  // sessionEndedAt is set.  Match /total/ so we only resolve on the footer, not on
  // per-node "Completed · Xs" duration labels that appear before the session is done.
  await expect(page.locator("text=/total/").first()).toBeVisible({
    timeout: OLLAMA_TIMEOUT,
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe("Tool scenario assistant bubbles (real Ollama backend)", () => {
  test("Data Query scenario produces assistant bubble", async ({
    page,
    request,
    createdSessionIds,
  }) => {
    test.setTimeout(OLLAMA_TIMEOUT + 30_000);
    const sessionId = await createSession(request, "Data Query scenario test");
    createdSessionIds.push(sessionId);

    await sendPromptAndWaitForCompleted(
      page,
      sessionId,
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
    test.setTimeout(OLLAMA_TIMEOUT + 30_000);
    const sessionId = await createSession(request, "Forecasting scenario test");
    createdSessionIds.push(sessionId);

    // Uses analyze_demand_trend (read_only, demand agent) for SKU-001.
    // The forecast tool is write-safety-level and filtered for the default analyst
    // user role; read_only tools are always available regardless of user role.
    // Date range is specified explicitly to avoid triggering the ask_user path.
    await sendPromptAndWaitForCompleted(
      page,
      sessionId,
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
    test.setTimeout(OLLAMA_TIMEOUT + 30_000);
    const sessionId = await createSession(request, "Simulation scenario test");
    createdSessionIds.push(sessionId);

    // Uses calculate_supply_gap (supply_planning agent) for SKU-001 at DC West.
    // Avoids simulation_optimizer to prevent the "No candidates" synthesis error
    // that occurs when simulate_inventory results lack the required "candidates" key.
    await sendPromptAndWaitForCompleted(
      page,
      sessionId,
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
    test.setTimeout(OLLAMA_TIMEOUT + 30_000);
    const sessionId = await createSession(request, "Optimization scenario test");
    createdSessionIds.push(sessionId);

    // Uses calculate_days_of_inventory (read_only, inventory agent) for SKU-001.
    // optimize_replenishment is write-safety-level and filtered for analyst role;
    // inventory DOI is read_only and always available.
    await sendPromptAndWaitForCompleted(
      page,
      sessionId,
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
    test.setTimeout(OLLAMA_TIMEOUT + 30_000);
    const sessionId = await createSession(request, "Data Catalog scenario test");
    createdSessionIds.push(sessionId);

    await sendPromptAndWaitForCompleted(
      page,
      sessionId,
      "利用可能なデータテーブル一覧をカタログから検索して",
    );

    const bubble = page.locator(".rounded-2xl.bg-\\[\\#1a1a2a\\]").first();
    await expect(bubble).toBeVisible({ timeout: 5_000 });
    await expect(bubble).not.toBeEmpty();
    expect(await bubble.getAttribute("class")).not.toContain("text-red-400");
  });
});
