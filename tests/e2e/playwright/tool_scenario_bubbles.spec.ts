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
const OLLAMA_TIMEOUT = 90_000;

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
  await expect(page.locator("text=Completed").first()).toBeVisible({
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
    test.setTimeout(OLLAMA_TIMEOUT + 10_000);
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
    test.setTimeout(OLLAMA_TIMEOUT + 10_000);
    const sessionId = await createSession(request, "Forecasting scenario test");
    createdSessionIds.push(sessionId);

    await sendPromptAndWaitForCompleted(
      page,
      sessionId,
      "来月のDC Westの需要予測をforecastツールで実行して数値を見せて",
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
    test.setTimeout(OLLAMA_TIMEOUT + 10_000);
    const sessionId = await createSession(request, "Simulation scenario test");
    createdSessionIds.push(sessionId);

    await sendPromptAndWaitForCompleted(
      page,
      sessionId,
      "現在の発注パラメータで在庫シミュレーションを実行して結果を見せて",
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
    test.setTimeout(OLLAMA_TIMEOUT + 10_000);
    const sessionId = await createSession(request, "Optimization scenario test");
    createdSessionIds.push(sessionId);

    await sendPromptAndWaitForCompleted(
      page,
      sessionId,
      "発注量の最適化を実行して推奨値を計算して",
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
    test.setTimeout(OLLAMA_TIMEOUT + 10_000);
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
