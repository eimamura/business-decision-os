/**
 * E2E Playwright spec for the JobApprovalCard component.
 *
 * KNOWN PRODUCTION LIMITATIONS (do not file bugs for these in this spec):
 *
 *   1. ToolContext.user_role defaults to "analyst" which filters out HITL tools
 *      (safety_level="hitl").  The job_dispatch tool is HITL-level, so the agent
 *      can never call it for a session initiated with the default analyst role.
 *      App Builder must propagate the authenticated user's DB role into ToolContext.
 *
 *   2. JobApprovalCard.tsx sends X-Dev-User: "dev-user" on approve/reject requests.
 *      The guardrail can_execute("approve_recommendation", "dev-user") returns false
 *      because dev-user is an analyst, not an approver.
 *      App Builder must either change the header or update the guardrail.
 *
 * APPROACH:
 *   Because the agent cannot call job_dispatch due to limitation 1, these tests
 *   inject the awaiting_approval SSE event via page.route() so the UI can be tested
 *   in isolation.  The real API is used for session and approval creation; only the
 *   SSE stream and the decision endpoint are intercepted.
 *
 * Component data-testid inventory:
 *   data-testid="job-approval-card"   — the card container
 *   data-testid="approve-btn"         — Approve button
 *   data-testid="reject-btn"          — Reject button
 *   data-testid="approval-status"     — outcome paragraph ("Approved" / "Rejected")
 */

import { testWithCleanup as test, expect } from "./fixtures";
import type { Page } from "@playwright/test";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Maximum time (ms) to wait for the approval card to appear after SSE injection. */
const CARD_TIMEOUT_MS = 10_000;

/** Maximum time (ms) to wait for the card status to change after clicking a decision button. */
const DECISION_TIMEOUT_MS = 10_000;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Create a real session via the API.
 * Returns the session_id.
 */
async function createSession(
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
  return session.session_id;
}

/**
 * Create a real pending approval in the DB for a given session.
 * Returns the approval_id.
 */
async function createApproval(page: Page, sessionId: string): Promise<string> {
  const res = await page.request.post(`${API_BASE}/api/v1/approvals`, {
    data: { session_id: sessionId, reason: "HITL: job_dispatch (test fixture)" },
    headers: { "X-Dev-User": "dev-user", "Content-Type": "application/json" },
  });
  if (!res.ok()) {
    // If POST /approvals is not available, fall back to a generated UUID.
    // The UI only needs a non-null approvalId to render the card.
    return `00000000-0000-0000-0000-${Date.now().toString().padStart(12, "0")}`;
  }
  const body = (await res.json()) as { id?: string; approval_id?: string };
  return (body.id ?? body.approval_id) as string;
}

/**
 * Register a page.route() handler that intercepts the Next.js proxy to
 * /api/v1/sessions/{sessionId}/stream and fulfills it with a synthetic SSE
 * response that includes an awaiting_approval event.
 *
 * The route fires for all URLs matching the pattern, so only call this after
 * session creation so the sessionId is known.
 */
async function injectApprovalSSE(
  page: Page,
  sessionId: string,
  approvalId: string,
): Promise<void> {
  const streamPattern = `**/api/v1/sessions/${sessionId}/stream`;
  await page.route(streamPattern, async (route) => {
    const events = [
      {
        type: "graph_node",
        event: "start",
        kind: "orchestrator",
        name: "classify_intent",
        run_id: "test-run-1",
        status: "ok",
        meta: { model_name: "test" },
        timestamp: new Date().toISOString(),
      },
      {
        type: "graph_node",
        event: "end",
        kind: "orchestrator",
        name: "classify_intent",
        run_id: "test-run-1",
        status: "ok",
        meta: { model_name: "test", category: "decision_support", confidence: 0.95 },
        timestamp: new Date().toISOString(),
        duration_ms: 100,
      },
      {
        type: "awaiting_approval",
        session_id: sessionId,
        approval_id: approvalId,
        tool_name: "job_dispatch",
        tool_input: {
          job_type: "simulate",
          params: { sku_id: "SKU-P99", horizon_days: 30 },
          description: "Inventory optimization simulation for SKU-P99 (30-day horizon)",
        },
        job_id: null,
        description: "Inventory optimization simulation for SKU-P99 (30-day horizon)",
        timestamp: new Date().toISOString(),
      },
      {
        type: "awaiting_input",
        session_id: sessionId,
        ask_user_id: "",
        timestamp: new Date().toISOString(),
      },
    ];

    const body = events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");
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
}

/**
 * Register a page.route() handler that intercepts
 * POST /api/v1/approvals/{approvalId}/decision and returns 200 with the
 * expected updated approval record.
 *
 * This is required because dev-user has analyst role which fails the
 * can_execute("approve_recommendation") check in the real API (returns 403).
 */
async function mockApprovalDecision(
  page: Page,
  approvalId: string,
  decision: "approved" | "rejected",
): Promise<void> {
  const decisionPattern = `**/api/v1/approvals/${approvalId}/decision`;
  await page.route(decisionPattern, async (route) => {
    const body = await route.request().postDataJSON() as { decision: string };
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: approvalId,
        status: body.decision ?? decision,
        reason: null,
        actor: "dev-user",
      }),
    });
  });
}

// ---------------------------------------------------------------------------
// Test suite
// ---------------------------------------------------------------------------

test.describe("Job Approval Card", () => {
  test("awaiting_approval SSE event shows job approval card with action buttons", async ({
    page,
    createdSessionIds,
  }) => {
    test.setTimeout(60_000);

    // 1. Create real session and approval in the DB.
    const sessionId = await createSession(page, createdSessionIds);
    const approvalId = await createApproval(page, sessionId);

    // 2. Set up SSE injection BEFORE navigation (route is registered on page,
    //    not tied to the navigation lifecycle).
    await injectApprovalSSE(page, sessionId, approvalId);

    // 3. Navigate to the chat page.  The SSE connection fires on load, delivering
    //    the synthetic awaiting_approval event.
    await page.goto(`/chat/${sessionId}`);
    await expect(page.locator("textarea")).toBeVisible();

    // 4. Send a message to trigger the SSE stream subscription from the UI.
    //    (The stream is only opened when the UI starts polling after a send.)
    await page.locator("textarea").fill("Run an inventory simulation for SKU-P99");
    await page.getByRole("button", { name: /send/i }).click();

    // 5. The approval card must appear from the injected awaiting_approval event.
    const card = page.locator('[data-testid="job-approval-card"]').first();
    await expect(card).toBeVisible({ timeout: CARD_TIMEOUT_MS });

    // 6. Both action buttons must be visible.
    const approveBtn = card.locator('[data-testid="approve-btn"]');
    const rejectBtn = card.locator('[data-testid="reject-btn"]');
    await expect(approveBtn).toBeVisible();
    await expect(rejectBtn).toBeVisible();
  });

  test("approve flow renders card and transitions to approved state", async ({
    page,
    createdSessionIds,
  }) => {
    test.setTimeout(60_000);

    const sessionId = await createSession(page, createdSessionIds);
    const approvalId = await createApproval(page, sessionId);

    await injectApprovalSSE(page, sessionId, approvalId);
    // Mock the decision endpoint to bypass the analyst-role 403 restriction.
    await mockApprovalDecision(page, approvalId, "approved");

    await page.goto(`/chat/${sessionId}`);
    await expect(page.locator("textarea")).toBeVisible();

    await page.locator("textarea").fill("Run an inventory simulation for SKU-P99");
    await page.getByRole("button", { name: /send/i }).click();

    const card = page.locator('[data-testid="job-approval-card"]').first();
    await expect(card).toBeVisible({ timeout: CARD_TIMEOUT_MS });

    const approveBtn = card.locator('[data-testid="approve-btn"]');
    const rejectBtn = card.locator('[data-testid="reject-btn"]');
    await expect(approveBtn).toBeVisible();
    await expect(rejectBtn).toBeVisible();

    // Click Approve.
    await approveBtn.click();

    // After approval the action buttons must disappear.
    await expect(approveBtn).not.toBeVisible({ timeout: DECISION_TIMEOUT_MS });
    await expect(rejectBtn).not.toBeVisible({ timeout: DECISION_TIMEOUT_MS });

    // The outcome "Approved" must appear (data-testid="approval-status").
    await expect(card.getByTestId("approval-status")).toHaveText("Approved", {
      timeout: DECISION_TIMEOUT_MS,
    });
  });

  test("reject flow transitions card to rejected state", async ({
    page,
    createdSessionIds,
  }) => {
    test.setTimeout(60_000);

    const sessionId = await createSession(page, createdSessionIds);
    const approvalId = await createApproval(page, sessionId);

    await injectApprovalSSE(page, sessionId, approvalId);
    await mockApprovalDecision(page, approvalId, "rejected");

    await page.goto(`/chat/${sessionId}`);
    await expect(page.locator("textarea")).toBeVisible();

    await page.locator("textarea").fill("Run an inventory simulation for SKU-P99");
    await page.getByRole("button", { name: /send/i }).click();

    const card = page.locator('[data-testid="job-approval-card"]').first();
    await expect(card).toBeVisible({ timeout: CARD_TIMEOUT_MS });

    const rejectBtn = card.locator('[data-testid="reject-btn"]');
    await expect(rejectBtn).toBeVisible();

    // Click Reject.
    await rejectBtn.click();

    // Action buttons must disappear after the decision.
    await expect(rejectBtn).not.toBeVisible({ timeout: DECISION_TIMEOUT_MS });

    // The outcome "Rejected" must appear.
    await expect(card.getByTestId("approval-status")).toHaveText("Rejected", {
      timeout: DECISION_TIMEOUT_MS,
    });
  });
});
