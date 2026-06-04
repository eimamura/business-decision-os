/**
 * T-157: HITL scenario bubble tests using mocked SSE.
 *
 * Covers:
 *   - Ask User: vague prompt triggers question bubble
 *   - Ask User: submitting answer shows answered state and result bubble
 *   - Ask User: fully specified prompt skips AskUser, goes straight to done
 *   - Job Dispatch: awaiting_approval event shows approval card
 *   - Job Dispatch: clicking Approve calls the approval API and shows "Approved"
 *   - Job Dispatch: clicking Reject shows "Rejected"
 *
 * No backend, LLM, or Docker required — only the Next.js dev server.
 *
 * Run with:
 *   cd apps/web && npm run dev   (separate terminal)
 *   npx playwright test hitl_scenario_bubbles_mock --config apps/web/playwright.config.ts
 */

import { testWithCleanup as test, expect } from "./fixtures";
import type { Page } from "@playwright/test";

const ASK_USER_SESSION = "mock-hitl-session";
const JOB_SESSION = "mock-job-session";
const NOW = "2024-01-01T00:00:00.000Z";

// ---------------------------------------------------------------------------
// SSE bodies — Ask User
// ---------------------------------------------------------------------------

const ASK_USER_FIRST_STREAM = [
  {
    type: "ask_user_required",
    session_id: ASK_USER_SESSION,
    ask_user_id: "ask-001",
    question: "What inventory should I analyze?",
    suggestions: ["All inventory", "Low stock only", "Overstock"],
    timestamp: NOW,
  },
  {
    type: "awaiting_input",
    session_id: ASK_USER_SESSION,
    ask_user_id: "ask-001",
    timestamp: NOW,
  },
]
  .map((e) => `data: ${JSON.stringify(e)}\n\n`)
  .join("");

const ASK_USER_SECOND_STREAM = [
  {
    type: "done",
    session_id: ASK_USER_SESSION,
    reply: "Analyzing all inventory...",
    timestamp: NOW,
  },
]
  .map((e) => `data: ${JSON.stringify(e)}\n\n`)
  .join("");

const ASK_USER_DONE_ONLY_STREAM = [
  {
    type: "done",
    session_id: ASK_USER_SESSION,
    reply: "Analyzing inventory for SKU-001 at DC West for the past 30 days.",
    timestamp: NOW,
  },
]
  .map((e) => `data: ${JSON.stringify(e)}\n\n`)
  .join("");

// ---------------------------------------------------------------------------
// SSE bodies — Job Dispatch
// ---------------------------------------------------------------------------

const JOB_APPROVAL_STREAM = [
  {
    type: "awaiting_approval",
    tool_name: "job_dispatch",
    approval_id: "approval-001",
    job_id: "job-001",
    description: "Run inventory simulation for Q3",
    tool_input: { job_type: "simulation", params: {} },
    timestamp: NOW,
  },
  {
    type: "awaiting_input",
    session_id: JOB_SESSION,
    ask_user_id: "",
    timestamp: NOW,
  },
]
  .map((e) => `data: ${JSON.stringify(e)}\n\n`)
  .join("");

// ---------------------------------------------------------------------------
// Route mock helpers
// ---------------------------------------------------------------------------

async function setupAskUserRoutes(page: Page, useFirstStreamOnly = false): Promise<void> {
  await page.route("**/api/v1/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });

  await page.route("**/api/v1/sessions", async (route) => {
    if (route.request().method() !== "GET") {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        { session_id: ASK_USER_SESSION, status: "active", title: "HITL Test", created_at: NOW },
      ]),
    });
  });

  await page.route(`**/api/v1/sessions/${ASK_USER_SESSION}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        session_id: ASK_USER_SESSION,
        status: "active",
        title: "HITL Test",
        created_at: NOW,
      }),
    });
  });

  await page.route(`**/api/v1/sessions/${ASK_USER_SESSION}/messages`, async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
    } else {
      await route.fulfill({
        status: 202,
        contentType: "application/json",
        body: JSON.stringify({
          message_id: "msg-1",
          session_id: ASK_USER_SESSION,
          status: "processing",
        }),
      });
    }
  });

  await page.route(`**/api/v1/sessions/${ASK_USER_SESSION}/events`, async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });

  let streamCallCount = 0;
  await page.route(`**/api/v1/sessions/${ASK_USER_SESSION}/stream`, async (route) => {
    streamCallCount += 1;
    const body =
      useFirstStreamOnly || streamCallCount === 1
        ? ASK_USER_FIRST_STREAM
        : ASK_USER_SECOND_STREAM;
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

  await page.route(`**/api/v1/sessions/${ASK_USER_SESSION}/answer`, async (route) => {
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({ status: "processing", session_id: ASK_USER_SESSION }),
    });
  });

  await page.route(`**/api/v1/sessions/${ASK_USER_SESSION}/usage`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ input_tokens: 0, output_tokens: 0, total_cost_usd: 0 }),
    });
  });
}

async function setupDoneOnlyAskUserRoutes(page: Page): Promise<void> {
  await page.route("**/api/v1/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });

  await page.route("**/api/v1/sessions", async (route) => {
    if (route.request().method() !== "GET") {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        { session_id: ASK_USER_SESSION, status: "active", title: "HITL Test", created_at: NOW },
      ]),
    });
  });

  await page.route(`**/api/v1/sessions/${ASK_USER_SESSION}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        session_id: ASK_USER_SESSION,
        status: "active",
        title: "HITL Test",
        created_at: NOW,
      }),
    });
  });

  await page.route(`**/api/v1/sessions/${ASK_USER_SESSION}/messages`, async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
    } else {
      await route.fulfill({
        status: 202,
        contentType: "application/json",
        body: JSON.stringify({
          message_id: "msg-1",
          session_id: ASK_USER_SESSION,
          status: "processing",
        }),
      });
    }
  });

  await page.route(`**/api/v1/sessions/${ASK_USER_SESSION}/events`, async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });

  await page.route(`**/api/v1/sessions/${ASK_USER_SESSION}/stream`, async (route) => {
    await route.fulfill({
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
      },
      body: ASK_USER_DONE_ONLY_STREAM,
    });
  });

  await page.route(`**/api/v1/sessions/${ASK_USER_SESSION}/usage`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ input_tokens: 0, output_tokens: 0, total_cost_usd: 0 }),
    });
  });
}

async function setupJobRoutes(page: Page): Promise<void> {
  await page.route("**/api/v1/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });

  await page.route("**/api/v1/sessions", async (route) => {
    if (route.request().method() !== "GET") {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        { session_id: JOB_SESSION, status: "active", title: "Job Test", created_at: NOW },
      ]),
    });
  });

  await page.route(`**/api/v1/sessions/${JOB_SESSION}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        session_id: JOB_SESSION,
        status: "active",
        title: "Job Test",
        created_at: NOW,
      }),
    });
  });

  await page.route(`**/api/v1/sessions/${JOB_SESSION}/messages`, async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
    } else {
      await route.fulfill({
        status: 202,
        contentType: "application/json",
        body: JSON.stringify({
          message_id: "msg-1",
          session_id: JOB_SESSION,
          status: "processing",
        }),
      });
    }
  });

  await page.route(`**/api/v1/sessions/${JOB_SESSION}/events`, async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });

  await page.route(`**/api/v1/sessions/${JOB_SESSION}/stream`, async (route) => {
    await route.fulfill({
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
      },
      body: JOB_APPROVAL_STREAM,
    });
  });

  await page.route(`**/api/v1/sessions/${JOB_SESSION}/usage`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ input_tokens: 0, output_tokens: 0, total_cost_usd: 0 }),
    });
  });

  await page.route("**/api/v1/approvals/approval-001/decision", async (route) => {
    const body = route.request().postDataJSON() as { decision: string } | null;
    const status = body?.decision === "reject" ? "rejected" : "approved";
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ approval_id: "approval-001", status }),
    });
  });
}

// ---------------------------------------------------------------------------
// Ask User tests
// ---------------------------------------------------------------------------

test.describe("Ask User HITL (mocked SSE — no backend required)", () => {
  test("vague prompt triggers question bubble with suggestions", async ({ page }) => {
    await setupAskUserRoutes(page, true);
    await page.goto(`/chat/${ASK_USER_SESSION}`);
    await expect(page.locator("textarea")).toBeVisible();

    await page.locator("textarea").fill("Analyze inventory");
    await page.getByRole("button", { name: /send/i }).click();

    const questionEl = page.locator('[data-testid="ask-user-question"]');
    await expect(questionEl).toBeVisible({ timeout: 10_000 });
    await expect(questionEl).toContainText("What inventory should I analyze?");

    await expect(page.locator('[data-testid="ask-user-suggestion-0"]')).toBeVisible();
    await expect(page.locator('[data-testid="ask-user-input"]')).toBeVisible();
    await expect(page.locator('[data-testid="ask-user-submit"]')).toBeVisible();
  });

  test("submitting answer shows answered state and result bubble", async ({ page }) => {
    await setupAskUserRoutes(page);
    await page.goto(`/chat/${ASK_USER_SESSION}`);
    await expect(page.locator("textarea")).toBeVisible();

    await page.locator("textarea").fill("Analyze inventory");
    await page.getByRole("button", { name: /send/i }).click();

    await expect(page.locator('[data-testid="ask-user-question"]')).toBeVisible({
      timeout: 10_000,
    });

    // Submit is disabled before selection
    await expect(page.locator('[data-testid="ask-user-submit"]')).toBeDisabled();

    // Click first suggestion chip and submit
    await page.locator('[data-testid="ask-user-suggestion-0"]').click();
    await page.locator('[data-testid="ask-user-submit"]').click();

    // Card transitions to answered state
    await expect(page.locator('[data-testid="ask-user-answered"]')).toBeVisible({
      timeout: 5_000,
    });

    // Result assistant bubble appears
    const bubble = page.locator(".rounded-2xl.bg-\\[\\#1a1a2a\\]").first();
    await expect(bubble).toBeVisible({ timeout: 10_000 });
    await expect(bubble).not.toBeEmpty();
  });

  test("fully specified prompt skips AskUser and shows assistant bubble directly", async ({
    page,
  }) => {
    await setupDoneOnlyAskUserRoutes(page);
    await page.goto(`/chat/${ASK_USER_SESSION}`);
    await expect(page.locator("textarea")).toBeVisible();

    await page.locator("textarea").fill(
      "Analyze inventory for SKU-001 at DC West for the past 30 days and compare with the previous month",
    );
    await page.getByRole("button", { name: /send/i }).click();

    const bubble = page.locator(".rounded-2xl.bg-\\[\\#1a1a2a\\]").first();
    await expect(bubble).toBeVisible({ timeout: 10_000 });

    // No ask-user card expected
    await expect(page.locator('[data-testid="ask-user-question"]')).not.toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// Job Dispatch tests
// ---------------------------------------------------------------------------

test.describe("Job Dispatch HITL (mocked SSE — no backend required)", () => {
  test("awaiting_approval event shows job approval card with action buttons", async ({ page }) => {
    await setupJobRoutes(page);
    await page.goto(`/chat/${JOB_SESSION}`);
    await expect(page.locator("textarea")).toBeVisible();

    await page.locator("textarea").fill("Run an inventory simulation for Q3");
    await page.getByRole("button", { name: /send/i }).click();

    const card = page.locator('[data-testid="job-approval-card"]');
    await expect(card).toBeVisible({ timeout: 10_000 });
    await expect(card.locator('[data-testid="approve-btn"]')).toBeVisible();
    await expect(card.locator('[data-testid="reject-btn"]')).toBeVisible();
  });

  test("clicking Approve calls the approval API and shows Approved status", async ({ page }) => {
    await setupJobRoutes(page);
    await page.goto(`/chat/${JOB_SESSION}`);
    await expect(page.locator("textarea")).toBeVisible();

    await page.locator("textarea").fill("Run an inventory simulation for Q3");
    await page.getByRole("button", { name: /send/i }).click();

    const card = page.locator('[data-testid="job-approval-card"]');
    await expect(card).toBeVisible({ timeout: 10_000 });

    await card.locator('[data-testid="approve-btn"]').click();

    await expect(card.locator('[data-testid="approval-status"]')).toBeVisible({ timeout: 5_000 });
    await expect(card.locator('[data-testid="approval-status"]')).toContainText("Approved");
    await expect(card.locator('[data-testid="approve-btn"]')).not.toBeVisible();
  });

  test("clicking Reject shows Rejected status", async ({ page }) => {
    await setupJobRoutes(page);
    await page.goto(`/chat/${JOB_SESSION}`);
    await expect(page.locator("textarea")).toBeVisible();

    await page.locator("textarea").fill("Run an inventory simulation for Q3");
    await page.getByRole("button", { name: /send/i }).click();

    const card = page.locator('[data-testid="job-approval-card"]');
    await expect(card).toBeVisible({ timeout: 10_000 });

    await card.locator('[data-testid="reject-btn"]').click();

    await expect(card.locator('[data-testid="approval-status"]')).toBeVisible({ timeout: 5_000 });
    await expect(card.locator('[data-testid="approval-status"]')).toContainText("Rejected");
    await expect(card.locator('[data-testid="reject-btn"]')).not.toBeVisible();
  });
});
