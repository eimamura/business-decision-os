/**
 * E2E Playwright spec for the JobApprovalCard component (T-045).
 *
 * These tests require a fully running system: API server on port 8000, Next.js
 * app on port 3000, and an active agent that will call the job_dispatch HITL
 * tool in response to the trigger message below.
 *
 * Guard: set RUN_E2E=1 in the environment to run these tests.
 * Without the guard they are skipped so they do not break CI.
 *
 * Component data-testid inventory (as of T-045):
 *   data-testid="job-approval-card"  — the card container
 *   data-testid="approve-btn"        — Approve button
 *   data-testid="reject-btn"         — Reject button
 *
 * NOTE (T-045 finding): The outcome state paragraphs ("Approved" / "Rejected")
 * in apps/web/components/JobApprovalCard.tsx do NOT carry a data-testid
 * attribute.  The tests below use text matching as a workaround.  App Builder
 * should add data-testid="approval-status" to the outcome <p> elements so
 * Playwright can locate them unambiguously.
 */

import { test, expect } from "@playwright/test";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Message that should trigger the job_dispatch HITL tool in the agent. */
const TRIGGER_MESSAGE =
  "Run an inventory optimization simulation for SKU-P99 with a 30-day planning horizon.";

/** Maximum time to wait for the approval card to appear after sending a message. */
const CARD_TIMEOUT_MS = 60_000;

/** Maximum time to wait for the card status to change after clicking a decision button. */
const DECISION_TIMEOUT_MS = 15_000;

// ---------------------------------------------------------------------------
// Skip guard — set RUN_E2E=1 to run these tests
// ---------------------------------------------------------------------------

test.beforeEach(() => {
  if (!process.env["RUN_E2E"]) {
    test.skip(true, "Set RUN_E2E=1 to run full job approval E2E tests");
  }
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Create a session via the API and navigate to its chat page.
 * Returns the session_id.
 */
async function createSessionAndNavigate(
  page: Parameters<Parameters<typeof test>[1]>[0],
): Promise<string> {
  const res = await page.request.post(`${API_BASE}/api/v1/sessions`, {
    data: { goal: "Playwright job approval spec" },
    headers: { "X-Dev-User": "dev-user" },
  });
  const session = (await res.json()) as { session_id: string };
  expect(session.session_id).toMatch(/^[0-9a-f]{8}-/);
  await page.goto(`/chat/${session.session_id}`);
  return session.session_id;
}

/**
 * Type a message in the chat textarea and click Send.
 */
async function sendMessage(
  page: Parameters<Parameters<typeof test>[1]>[0],
  message: string,
): Promise<void> {
  await page.locator("textarea").fill(message);
  await page.getByRole("button", { name: /send/i }).click();
}

// ---------------------------------------------------------------------------
// Test suite
// ---------------------------------------------------------------------------

test.describe("Job Approval Card", () => {
  test("approve flow renders card and transitions to approved state", async ({ page }) => {
    // 1. Create a session and navigate to the chat page
    await createSessionAndNavigate(page);

    // 2. Send a message that will cause the agent to call job_dispatch
    await sendMessage(page, TRIGGER_MESSAGE);

    // 3. Wait for the JobApprovalCard to appear in the chat thread
    const card = page.locator('[data-testid="job-approval-card"]').first();
    await expect(card).toBeVisible({ timeout: CARD_TIMEOUT_MS });

    // 4. Both action buttons should be visible before a decision is made
    const approveBtn = card.locator('[data-testid="approve-btn"]');
    const rejectBtn = card.locator('[data-testid="reject-btn"]');
    await expect(approveBtn).toBeVisible();
    await expect(rejectBtn).toBeVisible();

    // 5. Click Approve
    await approveBtn.click();

    // 6. After approval the action buttons must disappear
    await expect(approveBtn).not.toBeVisible({ timeout: DECISION_TIMEOUT_MS });
    await expect(rejectBtn).not.toBeVisible({ timeout: DECISION_TIMEOUT_MS });

    // 7. The outcome text "Approved" must appear inside the card
    //    (No data-testid="approval-status" yet — see file-level NOTE)
    await expect(card.getByText("Approved")).toBeVisible({
      timeout: DECISION_TIMEOUT_MS,
    });
  });

  test("reject flow transitions card to rejected state", async ({ page }) => {
    // 1. Create a separate session to avoid cross-test state
    await createSessionAndNavigate(page);

    // 2. Trigger the job_dispatch HITL tool
    await sendMessage(page, TRIGGER_MESSAGE);

    // 3. Wait for the approval card
    const card = page.locator('[data-testid="job-approval-card"]').first();
    await expect(card).toBeVisible({ timeout: CARD_TIMEOUT_MS });

    const rejectBtn = card.locator('[data-testid="reject-btn"]');
    await expect(rejectBtn).toBeVisible();

    // 4. Click Reject
    await rejectBtn.click();

    // 5. Action buttons must disappear after the decision
    await expect(rejectBtn).not.toBeVisible({ timeout: DECISION_TIMEOUT_MS });

    // 6. The outcome text "Rejected" must appear inside the card
    //    (No data-testid="approval-status" yet — see file-level NOTE)
    await expect(card.getByText("Rejected")).toBeVisible({
      timeout: DECISION_TIMEOUT_MS,
    });
  });
});
