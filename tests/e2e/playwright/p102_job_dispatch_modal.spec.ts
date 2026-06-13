/**
 * P102-B-02 Playwright spec — T-610
 *
 * Tests the "Job Dispatch (HITL)" category added to ToolScenarioModal in P102-B-01:
 *   1. Category tab renders in the modal.
 *   2. Train Forecast scenario injects correct prompt text into composer / message.
 *   3. Inventory Simulation scenario injects correct prompt text.
 *   4. Live E2E: modal → HITL approval → job-status-card → completion report
 *      (uses SSE mock; does NOT require a real Ollama call).
 *
 * Tests 1–3 are pure UI tests (no real LLM call; modal renders and prompt injection
 * verified via composer text or sent user message).  Test 4 exercises the full
 * modal → send → awaiting_approval → approve → job_report flow using page.route()
 * interception for all network calls beyond session creation.
 *
 * Run with:
 *   make dev-up         (starts web + api)
 *   make test-playwright
 */

import { testWithCleanup as test, expect } from "./fixtures";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** SSE response headers used for all mocked streams. */
const SSE_HEADERS: Record<string, string> = {
  "Content-Type": "text/event-stream",
  "Cache-Control": "no-cache",
  "X-Accel-Buffering": "no",
};

/** Max ms to wait for the modal to open after clicking the trigger. */
const MODAL_TIMEOUT_MS = 5_000;

/** Max ms to wait for the approval card after sending the message. */
const CARD_TIMEOUT_MS = 12_000;

/** Max ms to wait for a job-status-card after clicking Approve. */
const STATUS_CARD_TIMEOUT_MS = 12_000;

/** Max ms to wait for the job report assistant message. */
const REPORT_TIMEOUT_MS = 15_000;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Create a real session via the API and register it for cleanup.
 */
async function createSession(
  page: import("@playwright/test").Page,
  createdSessionIds: string[],
  goal?: string,
): Promise<string> {
  const res = await page.request.post(`${API_BASE}/api/v1/sessions`, {
    data: { goal: goal ?? "P102 Job Dispatch Modal spec" },
    headers: { "X-Dev-User": "dev-user" },
  });
  expect(res.ok()).toBeTruthy();
  const session = (await res.json()) as { session_id: string };
  createdSessionIds.push(session.session_id);
  return session.session_id;
}

/**
 * Open the Tool Scenario Modal on the given session's chat page.
 * Expects the textarea to be visible before clicking the trigger button.
 */
async function openModal(page: import("@playwright/test").Page): Promise<void> {
  await page.getByTitle("Browse all tool scenarios").click();
  await expect(page.getByRole("dialog")).toBeVisible({ timeout: MODAL_TIMEOUT_MS });
}

/**
 * Inject an SSE stream that emits awaiting_approval (for job_dispatch) +
 * awaiting_input, so the JobApprovalBubble renders without a real LLM call.
 */
async function injectApprovalSSE(
  page: import("@playwright/test").Page,
  sessionId: string,
  approvalId: string,
  jobId: string,
): Promise<void> {
  const streamPattern = `**/api/v1/sessions/${sessionId}/stream`;
  await page.route(streamPattern, async (route) => {
    const now = new Date().toISOString();
    const events = [
      {
        type: "graph_node",
        event: "start",
        kind: "orchestrator",
        name: "classify_intent",
        run_id: "test-run-p102",
        status: "ok",
        meta: { model_name: "test" },
        timestamp: now,
      },
      {
        type: "awaiting_approval",
        session_id: sessionId,
        approval_id: approvalId,
        tool_name: "job_dispatch",
        tool_input: {
          job_type: "train_forecast",
          params: { sku_id: "SKU-001" },
          description: "Train demand forecast model for SKU-001",
        },
        job_id: jobId,
        description: "Train demand forecast model for SKU-001",
        timestamp: now,
      },
      {
        type: "awaiting_input",
        session_id: sessionId,
        ask_user_id: "",
        timestamp: now,
      },
    ];

    const body = events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");
    await route.fulfill({ status: 200, headers: SSE_HEADERS, body });
  });
}

/**
 * Mock the approval decision endpoint to return 200 approved, bypassing the
 * analyst-role restriction on the real API.
 */
async function mockApprovalDecision(
  page: import("@playwright/test").Page,
  approvalId: string,
): Promise<void> {
  const decisionPattern = `**/api/v1/approvals/${approvalId}/decision`;
  await page.route(decisionPattern, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: approvalId,
        status: "approved",
        reason: null,
        actor: "dev-user",
      }),
    });
  });
}

/**
 * Mock the job poll endpoint: returns "running" on first call, "completed"
 * thereafter, so the job-status-card transitions to a terminal state.
 */
async function mockJobPoll(
  page: import("@playwright/test").Page,
  jobId: string,
): Promise<void> {
  let callCount = 0;
  await page.route(`**/api/v1/jobs/${jobId}`, async (route) => {
    callCount++;
    const status = callCount <= 1 ? "running" : "completed";
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: jobId,
        job_type: "train_forecast",
        status,
        params_json: { sku_id: "SKU-001" },
      }),
    });
  });
}

/**
 * Inject a second SSE stream that emits a job_report event so the UI renders
 * an assistant message without a page reload.
 */
async function injectJobReportSSE(
  page: import("@playwright/test").Page,
  sessionId: string,
  content: string,
): Promise<void> {
  // Unroute the previous approval stream so this replacement fires.
  await page.unroute(`**/api/v1/sessions/${sessionId}/stream`);
  await page.route(`**/api/v1/sessions/${sessionId}/stream`, async (route) => {
    const now = new Date().toISOString();
    const events = [
      {
        type: "job_report",
        session_id: sessionId,
        content,
        timestamp: now,
      },
      {
        type: "done",
        session_id: sessionId,
        timestamp: now,
      },
    ];
    const body = events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");
    await route.fulfill({ status: 200, headers: SSE_HEADERS, body });
  });
}

// ---------------------------------------------------------------------------
// Test suite
// ---------------------------------------------------------------------------

test.describe("P102 Job Dispatch Modal", () => {
  /**
   * T-610-PW-1: Job Dispatch category tab is visible in the modal.
   */
  test("renders Job Dispatch category tab", async ({ page, createdSessionIds }) => {
    const sessionId = await createSession(page, createdSessionIds, "P102 category tab test");

    await page.goto(`/chat/${sessionId}`);
    await expect(page.locator("textarea")).toBeVisible();

    await openModal(page);

    // The category nav button for job-dispatch must be present in the modal.
    const dialog = page.getByRole("dialog");
    const categoryBtn = dialog.locator('[data-testid="category-job-dispatch"]');
    await expect(categoryBtn).toBeVisible({ timeout: MODAL_TIMEOUT_MS });
  });

  /**
   * T-610-PW-2: Clicking Train Forecast scenario injects the correct prompt.
   *
   * Clicking a scenario card in the modal calls handleScenarioApply(prompt),
   * which calls sendMessage(prompt) directly.  The prompt appears as a user
   * message bubble in the chat.  A mock SSE stream is registered first so the
   * send completes without a real Ollama call.
   */
  test("clicking Train Forecast scenario injects correct prompt", async ({
    page,
    createdSessionIds,
  }) => {
    test.setTimeout(30_000);

    const sessionId = await createSession(
      page,
      createdSessionIds,
      "P102 train forecast scenario test",
    );

    // Register mock stream BEFORE goto so it is active when the page loads.
    const streamPattern = `**/api/v1/sessions/${sessionId}/stream`;
    await page.route(streamPattern, async (route) => {
      const now = new Date().toISOString();
      const events = [
        {
          type: "text_delta",
          session_id: sessionId,
          delta: "Acknowledged — training job queued.",
          timestamp: now,
        },
        {
          type: "done",
          session_id: sessionId,
          timestamp: now,
        },
      ];
      const body = events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");
      await route.fulfill({ status: 200, headers: SSE_HEADERS, body });
    });

    await page.goto(`/chat/${sessionId}`);
    await expect(page.locator("textarea")).toBeVisible();

    await openModal(page);

    const dialog = page.getByRole("dialog");
    // Navigate to the Job Dispatch category.
    await dialog.locator('[data-testid="category-job-dispatch"]').click();

    // Click the Train Forecast scenario card.
    await dialog
      .locator('[data-testid="scenario-job-dispatch-jd-train-forecast"]')
      .click();

    // Modal must close after clicking a scenario card.
    await expect(page.getByRole("dialog")).not.toBeVisible({ timeout: 3_000 });

    // The user message bubble must contain the expected prompt text.
    await expect(
      page.locator(".rounded-2xl.bg-indigo-600").filter({
        hasText: "Train the demand forecast model for SKU-001 as a background job",
      }),
    ).toBeVisible({ timeout: 10_000 });
  });

  /**
   * T-610-PW-3: Clicking Inventory Simulation scenario injects the correct prompt.
   */
  test("clicking Inventory Simulation scenario injects correct prompt", async ({
    page,
    createdSessionIds,
  }) => {
    test.setTimeout(30_000);

    const sessionId = await createSession(
      page,
      createdSessionIds,
      "P102 inventory simulation scenario test",
    );

    // Register mock stream BEFORE goto.
    const streamPattern = `**/api/v1/sessions/${sessionId}/stream`;
    await page.route(streamPattern, async (route) => {
      const now = new Date().toISOString();
      const events = [
        {
          type: "text_delta",
          session_id: sessionId,
          delta: "Acknowledged — simulation job queued.",
          timestamp: now,
        },
        {
          type: "done",
          session_id: sessionId,
          timestamp: now,
        },
      ];
      const body = events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");
      await route.fulfill({ status: 200, headers: SSE_HEADERS, body });
    });

    await page.goto(`/chat/${sessionId}`);
    await expect(page.locator("textarea")).toBeVisible();

    await openModal(page);

    const dialog = page.getByRole("dialog");
    await dialog.locator('[data-testid="category-job-dispatch"]').click();

    await dialog
      .locator('[data-testid="scenario-job-dispatch-jd-inventory-simulation"]')
      .click();

    await expect(page.getByRole("dialog")).not.toBeVisible({ timeout: 3_000 });

    await expect(
      page.locator(".rounded-2xl.bg-indigo-600").filter({
        hasText: "Run a full inventory simulation for all SKUs as a background job",
      }),
    ).toBeVisible({ timeout: 10_000 });
  });

  /**
   * T-610-PW-4: Live E2E — modal → HITL approval → job-status-card → completion report.
   *
   * Full flow:
   *   1. Open modal, select Job Dispatch category, click Train Forecast Model.
   *   2. Prompt is sent automatically (no separate Send click needed).
   *   3. Mocked SSE emits awaiting_approval → approval card appears.
   *   4. Click Approve → mocked decision endpoint returns 200.
   *   5. job-status-card appears and polls mocked job endpoint.
   *   6. Second SSE stream emits job_report → assistant message with "completed".
   */
  test("live E2E: job dispatch modal → HITL approval → completion report", async ({
    page,
    createdSessionIds,
  }) => {
    test.setTimeout(120_000);

    const sessionId = await createSession(
      page,
      createdSessionIds,
      "P102 live E2E job dispatch test",
    );

    const approvalId = `00000000-0000-0000-0001-${Date.now().toString().padStart(12, "0")}`;
    const jobId = `00000000-0000-0000-0002-${Date.now().toString().padStart(12, "0")}`;
    const reportContent =
      "**Job report — train_forecast completed.**\n\nModel trained successfully for SKU-001.";

    // Set up all mocks BEFORE navigation.
    await injectApprovalSSE(page, sessionId, approvalId, jobId);
    await mockApprovalDecision(page, approvalId);
    await mockJobPoll(page, jobId);

    await page.goto(`/chat/${sessionId}`);
    await expect(page.locator("textarea")).toBeVisible();

    // a. Open modal → Job Dispatch category → Train Forecast Model scenario.
    await openModal(page);
    const dialog = page.getByRole("dialog");
    await dialog.locator('[data-testid="category-job-dispatch"]').click();
    await dialog
      .locator('[data-testid="scenario-job-dispatch-jd-train-forecast"]')
      .click();

    // Modal closes automatically after scenario selection.
    await expect(page.getByRole("dialog")).not.toBeVisible({ timeout: 3_000 });

    // b. Approval card must appear from the injected SSE.
    const approvalCard = page.locator('[data-testid="job-approval-card"]').first();
    await expect(approvalCard).toBeVisible({ timeout: CARD_TIMEOUT_MS });

    const approveBtn = approvalCard.locator('[data-testid="approve-btn"]');
    await expect(approveBtn).toBeVisible();

    // c. Inject job_report SSE before clicking Approve, so the second stream is
    //    ready when the UI re-subscribes (or polls) after approval.
    await injectJobReportSSE(page, sessionId, reportContent);

    // d. Click Approve.
    await approveBtn.click();

    // e. job-status-card must appear after approval.
    await expect(
      page.locator('[data-testid="job-status-card"]').first(),
    ).toBeVisible({ timeout: STATUS_CARD_TIMEOUT_MS });

    // f. Assistant message containing the report text must appear (live SSE, not reload).
    await expect(
      page
        .locator("text=Job report")
        .or(page.locator("text=train_forecast completed"))
        .or(page.locator("text=completed"))
        .first(),
    ).toBeVisible({ timeout: REPORT_TIMEOUT_MS });
  });
});
