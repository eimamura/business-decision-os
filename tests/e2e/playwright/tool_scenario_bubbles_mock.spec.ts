/**
 * T-156: ToolScenario bubble appearance tests using mocked SSE.
 *
 * Verifies that sending each tool scenario prompt results in a non-empty,
 * non-error assistant bubble. No backend, LLM, or Docker required.
 *
 * Run with:
 *   cd apps/web && npm run dev   (separate terminal)
 *   npx playwright test tool_scenario_bubbles_mock --config apps/web/playwright.config.ts
 */

import { testWithCleanup as test, expect } from "./fixtures";
import type { Page } from "@playwright/test";

const SESSION_ID = "mock-tool-bubbles-session";
const NOW = "2024-01-01T00:00:00.000Z";

// ---------------------------------------------------------------------------
// Shared SSE done body
// ---------------------------------------------------------------------------

const DONE_STREAM_BODY = [
  {
    type: "done",
    session_id: SESSION_ID,
    reply: "Analysis complete. Here are the results.",
    timestamp: NOW,
  },
]
  .map((e) => `data: ${JSON.stringify(e)}\n\n`)
  .join("");

// ---------------------------------------------------------------------------
// Route mock setup
// ---------------------------------------------------------------------------

async function setupMockRoutes(page: Page): Promise<void> {
  // Catch-all for any unhandled /api/v1/* route (lowest priority)
  await page.route("**/api/v1/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });

  // Sessions list (sidebar)
  await page.route("**/api/v1/sessions", async (route) => {
    if (route.request().method() !== "GET") {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        { session_id: SESSION_ID, status: "active", title: "Mock session", created_at: NOW },
      ]),
    });
  });

  // Session detail
  await page.route(`**/api/v1/sessions/${SESSION_ID}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        session_id: SESSION_ID,
        status: "active",
        title: "Mock session",
        created_at: NOW,
      }),
    });
  });

  // Messages — GET returns empty history; POST acknowledges
  await page.route(`**/api/v1/sessions/${SESSION_ID}/messages`, async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
    } else {
      await route.fulfill({
        status: 202,
        contentType: "application/json",
        body: JSON.stringify({ message_id: "msg-1", session_id: SESSION_ID, status: "processing" }),
      });
    }
  });

  // Session events
  await page.route(`**/api/v1/sessions/${SESSION_ID}/events`, async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });

  // SSE stream — always returns done with non-empty reply
  await page.route(`**/api/v1/sessions/${SESSION_ID}/stream`, async (route) => {
    await route.fulfill({
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
      },
      body: DONE_STREAM_BODY,
    });
  });

  // Usage
  await page.route(`**/api/v1/sessions/${SESSION_ID}/usage`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ input_tokens: 0, output_tokens: 0, total_cost_usd: 0 }),
    });
  });
}

// ---------------------------------------------------------------------------
// Helper: send a prompt and wait for the assistant bubble
// ---------------------------------------------------------------------------

async function sendPromptAndWaitForBubble(page: Page, prompt: string): Promise<void> {
  await page.goto(`/chat/${SESSION_ID}`);
  await expect(page.locator("textarea")).toBeVisible();
  await page.locator("textarea").fill(prompt);
  await page.getByRole("button", { name: /send/i }).click();
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe("Tool scenario assistant bubbles (mocked SSE — no backend required)", () => {
  test("Data Query scenario produces assistant bubble", async ({ page }) => {
    await setupMockRoutes(page);
    // SQL Direct Query prompt
    await sendPromptAndWaitForBubble(
      page,
      "在庫テーブルから全SKUの現在庫数をSQLで直接取得して",
    );

    const bubble = page.locator(".rounded-2xl.bg-\\[\\#1a1a2a\\]").first();
    await expect(bubble).toBeVisible({ timeout: 10_000 });
    expect(await bubble.getAttribute("class")).not.toContain("text-red-400");
    await expect(bubble).not.toBeEmpty();
  });

  test("Forecasting scenario produces assistant bubble", async ({ page }) => {
    await setupMockRoutes(page);
    // Demand Forecast prompt
    await sendPromptAndWaitForBubble(
      page,
      "来月のDC Westの需要予測をforecastツールで実行して数値を見せて",
    );

    const bubble = page.locator(".rounded-2xl.bg-\\[\\#1a1a2a\\]").first();
    await expect(bubble).toBeVisible({ timeout: 10_000 });
    expect(await bubble.getAttribute("class")).not.toContain("text-red-400");
    await expect(bubble).not.toBeEmpty();
  });

  test("Simulation scenario produces assistant bubble", async ({ page }) => {
    await setupMockRoutes(page);
    // Inventory Simulation prompt
    await sendPromptAndWaitForBubble(
      page,
      "現在の発注パラメータで在庫シミュレーションを実行して結果を見せて",
    );

    const bubble = page.locator(".rounded-2xl.bg-\\[\\#1a1a2a\\]").first();
    await expect(bubble).toBeVisible({ timeout: 10_000 });
    expect(await bubble.getAttribute("class")).not.toContain("text-red-400");
    await expect(bubble).not.toBeEmpty();
  });

  test("Optimization scenario produces assistant bubble", async ({ page }) => {
    await setupMockRoutes(page);
    // Replenishment Optimization prompt
    await sendPromptAndWaitForBubble(
      page,
      "発注量の最適化を実行して推奨値を計算して",
    );

    const bubble = page.locator(".rounded-2xl.bg-\\[\\#1a1a2a\\]").first();
    await expect(bubble).toBeVisible({ timeout: 10_000 });
    expect(await bubble.getAttribute("class")).not.toContain("text-red-400");
    await expect(bubble).not.toBeEmpty();
  });

  test("Data Catalog scenario produces assistant bubble", async ({ page }) => {
    await setupMockRoutes(page);
    // Data Catalog Search prompt
    await sendPromptAndWaitForBubble(
      page,
      "利用可能なデータテーブル一覧をカタログから検索して",
    );

    const bubble = page.locator(".rounded-2xl.bg-\\[\\#1a1a2a\\]").first();
    await expect(bubble).toBeVisible({ timeout: 10_000 });
    expect(await bubble.getAttribute("class")).not.toContain("text-red-400");
    await expect(bubble).not.toBeEmpty();
  });
});
