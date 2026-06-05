/**
 * E2E Playwright spec for the JobApprovalCard component — real API + real Ollama.
 *
 * The approval card appears when the agent calls the job_dispatch HITL tool.
 * With the trigger message below the agent reliably calls job_dispatch because the
 * prompt explicitly requests a simulation job that matches the tool's description.
 *
 * Requires: make dev-up  (web on WEB_PORT, api on API_PORT, Ollama on 11434)
 *
 * Component data-testid inventory:
 *   data-testid="job-approval-card"  — the card container
 *   data-testid="approve-btn"        — Approve button
 *   data-testid="reject-btn"         — Reject button
 *
 * NOTE (T-045 finding): The outcome state paragraphs ("Approved" / "Rejected")
 * in apps/web/components/JobApprovalCard.tsx do NOT carry a data-testid attribute.
 * The tests below use text matching as a workaround.  App Builder should add
 * data-testid="approval-status" to the outcome <p> elements.
 */

import { testWithCleanup as test, expect } from "./fixtures";
import type { Page } from "@playwright/test";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Message that reliably triggers the job_dispatch HITL tool in the agent. */
const TRIGGER_MESSAGE =
  "Run an inventory optimization simulation for SKU-P99 with a 30-day planning horizon.";

/**
 * Maximum time (ms) to wait for the approval card to appear after sending a message.
 * Real Ollama (qwen2.5-coder:7b) may take up to 90s to classify, route, and call
 * the job_dispatch tool.
 */
const CARD_TIMEOUT_MS = 90_000;

/** Maximum time (ms) to wait for the card status to change after clicking a decision button. */
const DECISION_TIMEOUT_MS = 15_000;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Create a session via the API and navigate to its chat page.
 * Pushes the created session_id into `createdSessionIds` for cleanup.
 * Returns the session_id.
 */
async function createSessionAndNavigate(
  page: Page,
  createdSessionIds: string[],
): Promise<string> {
  const res = await page.request.post(`${API_BASE}/api/v1/sessions`, {
    data: { goal: "Playwright job approval spec" },
    headers: { "X-Dev-User": "dev-user" },
  });
  expect(res.ok()).toBeTruthy();
  const session = (await res.json()) as { session_id: string };
  expect(session.session_id).toMatch(/^[0-9a-f]{8}-/);
  createdSessionIds.push(session.session_id);
  await page.goto(`/chat/${session.session_id}`);
  return session.session_id;
}

/**
 * Type a message in the chat textarea and click Send.
 */
async function sendMessage(page: Page, message: string): Promise<void> {
  await expect(page.locator("textarea")).toBeVisible();
  await page.locator("textarea").fill(message);
  await page.getByRole("button", { name: /send/i }).click();
}

// ---------------------------------------------------------------------------
// Test suite
// ---------------------------------------------------------------------------

test.describe("Job Approval Card", () => {
  test("awaiting_approval event shows job approval card with action buttons", async ({
    page,
    createdSessionIds,
  }) => {
    test.setTimeout(120_000);

    await createSessionAndNavigate(page, createdSessionIds);
    await sendMessage(page, TRIGGER_MESSAGE);

    // The approval card must appear when the agent emits awaiting_approval SSE event.
    const card = page.locator('[data-testid="job-approval-card"]').first();
    await expect(card).toBeVisible({ timeout: CARD_TIMEOUT_MS });

    // Both action buttons must be present and visible before any decision is made.
    const approveBtn = card.locator('[data-testid="approve-btn"]');
    const rejectBtn = card.locator('[data-testid="reject-btn"]');
    await expect(approveBtn).toBeVisible();
    await expect(rejectBtn).toBeVisible();
  });

  test("approve flow renders card and transitions to approved state", async ({
    page,
    createdSessionIds,
  }) => {
    test.setTimeout(120_000);

    // 1. Create a session and navigate to the chat page.
    await createSessionAndNavigate(page, createdSessionIds);

    // 2. Send a message that will cause the agent to call job_dispatch.
    await sendMessage(page, TRIGGER_MESSAGE);

    // 3. Wait for the JobApprovalCard to appear in the chat thread.
    const card = page.locator('[data-testid="job-approval-card"]').first();
    await expect(card).toBeVisible({ timeout: CARD_TIMEOUT_MS });

    // 4. Both action buttons should be visible before a decision is made.
    const approveBtn = card.locator('[data-testid="approve-btn"]');
    const rejectBtn = card.locator('[data-testid="reject-btn"]');
    await expect(approveBtn).toBeVisible();
    await expect(rejectBtn).toBeVisible();

    // 5. Click Approve.
    await approveBtn.click();

    // 6. After approval the action buttons must disappear.
    await expect(approveBtn).not.toBeVisible({ timeout: DECISION_TIMEOUT_MS });
    await expect(rejectBtn).not.toBeVisible({ timeout: DECISION_TIMEOUT_MS });

    // 7. The outcome text "Approved" must appear inside the card.
    //    (No data-testid="approval-status" yet — see file-level NOTE)
    await expect(card.getByText("Approved")).toBeVisible({
      timeout: DECISION_TIMEOUT_MS,
    });
  });

  test("reject flow transitions card to rejected state", async ({
    page,
    createdSessionIds,
  }) => {
    test.setTimeout(120_000);

    // 1. Create a separate session to avoid cross-test state.
    await createSessionAndNavigate(page, createdSessionIds);

    // 2. Trigger the job_dispatch HITL tool.
    await sendMessage(page, TRIGGER_MESSAGE);

    // 3. Wait for the approval card.
    const card = page.locator('[data-testid="job-approval-card"]').first();
    await expect(card).toBeVisible({ timeout: CARD_TIMEOUT_MS });

    const rejectBtn = card.locator('[data-testid="reject-btn"]');
    await expect(rejectBtn).toBeVisible();

    // 4. Click Reject.
    await rejectBtn.click();

    // 5. Action buttons must disappear after the decision.
    await expect(rejectBtn).not.toBeVisible({ timeout: DECISION_TIMEOUT_MS });

    // 6. The outcome text "Rejected" must appear inside the card.
    //    (No data-testid="approval-status" yet — see file-level NOTE)
    await expect(card.getByText("Rejected")).toBeVisible({
      timeout: DECISION_TIMEOUT_MS,
    });
  });
});
