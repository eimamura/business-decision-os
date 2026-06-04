import { test, expect, type Page } from "@playwright/test";

/**
 * AskUser bubble UI tests using mocked API responses.
 *
 * No backend, LLM, LangGraph, or Docker required — only the Next.js dev server.
 *
 * Run with:
 *   cd apps/web && npm run dev   (separate terminal)
 *   npx playwright test ask_user_bubble_mock --config apps/web/playwright.config.ts
 */

const SESSION_ID = "mock-ask-user-session";
const NOW = "2024-01-01T00:00:00.000Z";

// ---------------------------------------------------------------------------
// Mock SSE event bodies
// ---------------------------------------------------------------------------

const FIRST_STREAM_BODY = [
  {
    type: "ask_user_required",
    session_id: SESSION_ID,
    ask_user_id: "ask-001",
    question: "Which inventory scope do you want to analyze?",
    suggestions: ["All inventory", "Low stock only", "Overstock only"],
    timestamp: NOW,
  },
  {
    type: "awaiting_input",
    session_id: SESSION_ID,
    ask_user_id: "ask-001",
    timestamp: NOW,
  },
]
  .map((e) => `data: ${JSON.stringify(e)}\n\n`)
  .join("");

const SECOND_STREAM_BODY = [
  {
    type: "done",
    session_id: SESSION_ID,
    reply: "Analyzing low stock inventory for the selected period.",
    timestamp: NOW,
  },
]
  .map((e) => `data: ${JSON.stringify(e)}\n\n`)
  .join("");

// ---------------------------------------------------------------------------
// Route mock setup
// ---------------------------------------------------------------------------

async function setupMockRoutes(page: Page): Promise<void> {
  // Catch-all for any unhandled /api/v1/* route (registered first = lowest priority)
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

  // Messages history
  await page.route(`**/api/v1/sessions/${SESSION_ID}/messages`, async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
    } else {
      // POST — acknowledge message submission
      await route.fulfill({
        status: 202,
        contentType: "application/json",
        body: JSON.stringify({ message_id: "msg-1", session_id: SESSION_ID, status: "processing" }),
      });
    }
  });

  // Session events (Execution Trace history on load)
  await page.route(`**/api/v1/sessions/${SESSION_ID}/events`, async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });

  // SSE stream — first call triggers AskUser, second call completes with done
  let streamCallCount = 0;
  await page.route(`**/api/v1/sessions/${SESSION_ID}/stream`, async (route) => {
    streamCallCount += 1;
    const body = streamCallCount === 1 ? FIRST_STREAM_BODY : SECOND_STREAM_BODY;
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

  // Submit answer
  await page.route(`**/api/v1/sessions/${SESSION_ID}/answer`, async (route) => {
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({ status: "processing", session_id: SESSION_ID }),
    });
  });

  // Usage (fetched after done event)
  await page.route(`**/api/v1/sessions/${SESSION_ID}/usage`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ input_tokens: 0, output_tokens: 0, total_cost_usd: 0 }),
    });
  });
}

// ---------------------------------------------------------------------------
// Helper: navigate to chat and send the trigger message
// ---------------------------------------------------------------------------

async function sendTriggerMessage(page: Page): Promise<void> {
  await page.goto(`/chat/${SESSION_ID}`);
  const textarea = page.locator("textarea");
  await expect(textarea).toBeVisible();
  await textarea.fill("Analyze inventory levels");
  await page.getByRole("button", { name: /send/i }).click();
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe("AskUser bubble (mocked SSE — no backend required)", () => {
  test("renders question text, suggestion chips, input, and submit button", async ({
    page,
  }) => {
    await setupMockRoutes(page);
    await sendTriggerMessage(page);

    const questionEl = page.locator('[data-testid="ask-user-question"]');
    await expect(questionEl).toBeVisible({ timeout: 10_000 });
    await expect(questionEl).toContainText("Which inventory scope");

    await expect(page.locator('[data-testid="ask-user-suggestion-0"]')).toBeVisible();
    await expect(page.locator('[data-testid="ask-user-suggestion-1"]')).toBeVisible();
    await expect(page.locator('[data-testid="ask-user-suggestion-2"]')).toBeVisible();

    await expect(page.locator('[data-testid="ask-user-input"]')).toBeVisible();
    await expect(page.locator('[data-testid="ask-user-submit"]')).toBeVisible();
  });

  test("submit is disabled before selection and enabled after clicking a chip", async ({
    page,
  }) => {
    await setupMockRoutes(page);
    await sendTriggerMessage(page);

    await expect(page.locator('[data-testid="ask-user-question"]')).toBeVisible({
      timeout: 10_000,
    });

    // No option selected — submit must be disabled
    await expect(page.locator('[data-testid="ask-user-submit"]')).toBeDisabled();

    // Click the second chip ("Low stock only")
    await page.locator('[data-testid="ask-user-suggestion-1"]').click();

    // Input populated and submit enabled
    await expect(page.locator('[data-testid="ask-user-input"]')).toHaveValue("Low stock only");
    await expect(page.locator('[data-testid="ask-user-submit"]')).toBeEnabled();
  });

  test("submits selected answer with correct payload and renders assistant response", async ({
    page,
  }) => {
    await setupMockRoutes(page);
    await sendTriggerMessage(page);

    await expect(page.locator('[data-testid="ask-user-question"]')).toBeVisible({
      timeout: 10_000,
    });

    // Capture POST /answer before clicking submit
    const answerRequestPromise = page.waitForRequest(
      (req) => req.url().includes("/answer") && req.method() === "POST",
    );

    await page.locator('[data-testid="ask-user-suggestion-1"]').click();
    await page.locator('[data-testid="ask-user-submit"]').click();

    // Bubble switches to answered state immediately (optimistic)
    const answeredEl = page.locator('[data-testid="ask-user-answered"]');
    await expect(answeredEl).toBeVisible({ timeout: 5_000 });
    await expect(answeredEl).toContainText("Low stock only");

    // Verify the POST /answer payload
    const answerRequest = await answerRequestPromise;
    expect(JSON.parse(answerRequest.postData() ?? "{}")).toEqual({
      answer: "Low stock only",
    });
  });
});
