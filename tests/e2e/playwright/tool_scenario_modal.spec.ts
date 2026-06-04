/**
 * T-155: ToolScenarioModal Playwright tests using mocked API routes.
 *
 * No backend, LLM, or Docker required — only the Next.js dev server.
 *
 * Run with:
 *   cd apps/web && npm run dev   (separate terminal)
 *   npx playwright test tool_scenario_modal --config apps/web/playwright.config.ts
 */

import { testWithCleanup as test, expect } from "./fixtures";
import type { Page } from "@playwright/test";

const SESSION_ID = "mock-tool-modal-session";
const NOW = "2024-01-01T00:00:00.000Z";

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
        { session_id: SESSION_ID, status: "active", title: "Test", created_at: NOW },
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
        title: "Test",
        created_at: NOW,
      }),
    });
  });

  // Messages history
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

  // SSE stream (returns a minimal done event)
  await page.route(`**/api/v1/sessions/${SESSION_ID}/stream`, async (route) => {
    const body = [
      { type: "done", session_id: SESSION_ID, reply: "Analysis complete.", timestamp: NOW },
    ]
      .map((e) => `data: ${JSON.stringify(e)}\n\n`)
      .join("");
    await route.fulfill({
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
      },
      body,
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
// Helper: navigate to the chat page
// ---------------------------------------------------------------------------

async function navigateToChat(page: Page): Promise<void> {
  await page.goto(`/chat/${SESSION_ID}`);
  await expect(page.locator("textarea")).toBeVisible();
}

// ---------------------------------------------------------------------------
// Helper: open the modal
// ---------------------------------------------------------------------------

async function openModal(page: Page): Promise<void> {
  await page.getByTitle("Browse all tool scenarios").click();
  await expect(page.getByRole("dialog")).toBeVisible({ timeout: 5_000 });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe("ToolScenarioModal (mocked routes — no backend required)", () => {
  test("modal opens when grid button is clicked", async ({ page }) => {
    await setupMockRoutes(page);
    await navigateToChat(page);

    await page.getByTitle("Browse all tool scenarios").click();

    await expect(page.getByRole("dialog")).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("Tool Scenarios")).toBeVisible();
  });

  test("all 5 category tabs are visible in the open modal", async ({ page }) => {
    await setupMockRoutes(page);
    await navigateToChat(page);
    await openModal(page);

    const dialog = page.getByRole("dialog");
    await expect(dialog.getByText("Data Query")).toBeVisible();
    await expect(dialog.getByText("Forecasting")).toBeVisible();
    await expect(dialog.getByText("Simulation & Optimization")).toBeVisible();
    await expect(dialog.getByText("Ask User (HITL)")).toBeVisible();
    await expect(dialog.getByText("Job Dispatch (HITL)")).toBeVisible();
  });

  test("clicking Forecasting tab shows its scenario cards", async ({ page }) => {
    await setupMockRoutes(page);
    await navigateToChat(page);
    await openModal(page);

    const dialog = page.getByRole("dialog");
    // Use role=button to avoid matching text inside scenario cards
    await dialog.getByRole("button", { name: "Forecasting" }).click();

    // Use .first() — "Demand Forecast" also appears in "Train Forecast Model"'s description text
    await expect(dialog.getByText("Demand Forecast").first()).toBeVisible({ timeout: 5_000 });
  });

  test("clicking a scenario card closes the modal and sends the prompt as a message", async ({ page }) => {
    await setupMockRoutes(page);
    await navigateToChat(page);
    await openModal(page);

    // "SQL Direct Query" is under the default "Data Query" tab — visible immediately.
    // Clicking a scenario card calls handleScenarioApply() which sends the message
    // immediately (does NOT fill the textarea — it calls sendMessage() directly).
    const dialog = page.getByRole("dialog");
    await dialog.getByText("SQL Direct Query").click();

    // Modal must be gone after clicking
    await expect(page.getByRole("dialog")).not.toBeVisible({ timeout: 3_000 });

    // A user message bubble should appear with the SQL prompt text
    await expect(page.locator(".rounded-2xl").filter({ hasText: /在庫テーブル/ })).toBeVisible({
      timeout: 8_000,
    });
  });

  test("clicking a quick chip in ToolScenarioBar fills textarea without opening the modal", async ({
    page,
  }) => {
    await setupMockRoutes(page);
    await navigateToChat(page);

    // Click the "SQL Query" chip directly in the bar
    await page.getByText("SQL Query").click();

    // Modal must NOT have opened
    await expect(page.getByRole("dialog")).not.toBeVisible();

    // Textarea must contain the SQL prompt
    await expect(page.locator("textarea")).toHaveValue(/在庫テーブル/);
  });
});
