/**
 * T-313: Ask-user inline answer input flow — mock SSE interceptors.
 *
 * The AskUser flow is triggered when the SSE stream emits an ask_user_required
 * event.  Previously these tests waited up to 240 s for real Ollama to produce
 * that event; now page.route() intercepts the stream and delivers a synthetic
 * ask_user_required sequence in under 1 s.
 *
 * Tests 1–4 use mockAskUserStream.  Test 4 (answer + reply) also mocks the
 * second SSE subscription (after the user submits an answer) with a stateful
 * callCount closure — first call returns ask_user, second call returns
 * completed.  Test 5 uses mockCompletedStream only (fully-specified prompt,
 * no ask_user).
 *
 * Real sessions are created via the API so we have a genuine session_id for
 * the route patterns.
 *
 * Run with:
 *   make dev-up   (starts web + api)
 *   make test-playwright
 */

import { testWithCleanup as test, expect } from "./fixtures";
import { mockAskUserStream, mockCompletedStream } from "./sse-mock";
import type { Page } from "@playwright/test";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Maximum time (ms) to wait for the ask_user question bubble to appear. */
const ASK_USER_TIMEOUT = 10_000;
/** Maximum time (ms) to wait for the assistant reply after submitting an answer. */
const REPLY_TIMEOUT = 10_000;

// ---------------------------------------------------------------------------
// SSE response headers (shared with sse-mock.ts)
// ---------------------------------------------------------------------------

const SSE_HEADERS: Record<string, string> = {
  "Content-Type": "text/event-stream",
  "Cache-Control": "no-cache",
  "X-Accel-Buffering": "no",
};

// ---------------------------------------------------------------------------
// Helper: create a session via API, set up the mock, then navigate.
// Callers pass the mock-setup callback so the route is registered BEFORE goto.
// ---------------------------------------------------------------------------

async function createSessionMockAndNavigate(
  page: Page,
  createdSessionIds: string[],
  goal: string,
  setupMock: (sessionId: string) => Promise<void>,
): Promise<string> {
  const res = await page.request.post(`${API_BASE}/api/v1/sessions`, {
    data: { goal },
    headers: { "X-Dev-User": "dev-user" },
  });
  expect(res.ok()).toBeTruthy();
  const session = (await res.json()) as { session_id: string };
  expect(session.session_id).toMatch(/^[0-9a-f]{8}-/);
  createdSessionIds.push(session.session_id);

  // Register the mock route BEFORE navigation so the route is active when
  // the page establishes its SSE connection.
  await setupMock(session.session_id);

  await page.goto(`/chat/${session.session_id}`);
  await expect(page.locator("textarea")).toBeVisible();
  return session.session_id;
}

// ---------------------------------------------------------------------------
// Test suite
// ---------------------------------------------------------------------------

test.describe("AskUser inline answer input (mock SSE)", () => {
  test("ask_user_required SSE event renders inline question with chips and answer input", async ({
    page,
    createdSessionIds,
  }) => {
    test.setTimeout(30_000);

    await createSessionMockAndNavigate(
      page,
      createdSessionIds,
      "Ask-user E2E test — question bubble",
      (sessionId) => mockAskUserStream(page, sessionId),
    );

    await page.locator("textarea").fill("Analyze inventory");
    await page.getByRole("button", { name: /send/i }).click();

    // The ask_user_required SSE event causes the AskUserInput component to mount.
    const questionEl = page.locator('[data-testid="ask-user-question"]');
    await expect(questionEl).toBeVisible({ timeout: ASK_USER_TIMEOUT });

    // At least the first suggestion chip should be rendered.
    const firstChip = page.locator('[data-testid="ask-user-suggestion-0"]');
    await expect(firstChip).toBeVisible();

    // Answer input and submit button must be present.
    const answerInput = page.locator('[data-testid="ask-user-input"]');
    const submitBtn = page.locator('[data-testid="ask-user-submit"]');
    await expect(answerInput).toBeVisible();
    await expect(submitBtn).toBeVisible();
  });

  test("clicking a suggestion chip pre-populates the answer input", async ({
    page,
    createdSessionIds,
  }) => {
    test.setTimeout(30_000);

    await createSessionMockAndNavigate(
      page,
      createdSessionIds,
      "Ask-user E2E test — chip pre-populate",
      (sessionId) => mockAskUserStream(page, sessionId),
    );

    await page.locator("textarea").fill("Analyze inventory");
    await page.getByRole("button", { name: /send/i }).click();

    const firstChip = page.locator('[data-testid="ask-user-suggestion-0"]');
    await expect(firstChip).toBeVisible({ timeout: ASK_USER_TIMEOUT });

    const chipLabel = await firstChip.textContent();
    await firstChip.click();

    const answerInput = page.locator('[data-testid="ask-user-input"]');
    // After clicking the chip the input must be pre-populated with the chip text.
    await expect(answerInput).toHaveValue(chipLabel ?? "");
  });

  test("submit button is disabled before selection and enabled after clicking a chip", async ({
    page,
    createdSessionIds,
  }) => {
    test.setTimeout(30_000);

    await createSessionMockAndNavigate(
      page,
      createdSessionIds,
      "Ask-user E2E test — submit disabled state",
      (sessionId) => mockAskUserStream(page, sessionId),
    );

    await page.locator("textarea").fill("Analyze inventory");
    await page.getByRole("button", { name: /send/i }).click();

    const firstChip = page.locator('[data-testid="ask-user-suggestion-0"]');
    await expect(firstChip).toBeVisible({ timeout: ASK_USER_TIMEOUT });

    const submitBtn = page.locator('[data-testid="ask-user-submit"]');

    // Before any input or chip click the submit button must be disabled
    // (AskUserInput: disabled={isSubmitting || !inputValue.trim()}).
    await expect(submitBtn).toBeDisabled();

    // Clicking a chip pre-fills the input — submit must become enabled.
    await firstChip.click();
    await expect(submitBtn).toBeEnabled();
  });

  test("submitting an answer shows answered state and then assistant reply bubble", async ({
    page,
    createdSessionIds,
  }) => {
    test.setTimeout(30_000);

    // This test needs a stateful mock: first SSE subscription → ask_user;
    // second subscription (after answer submitted) → completed.
    // We register the route manually instead of using the helpers so we can
    // use a callCount closure to change behaviour between calls.
    const res = await page.request.post(`${API_BASE}/api/v1/sessions`, {
      data: { goal: "Ask-user E2E test — answer submission" },
      headers: { "X-Dev-User": "dev-user" },
    });
    expect(res.ok()).toBeTruthy();
    const session = (await res.json()) as { session_id: string };
    expect(session.session_id).toMatch(/^[0-9a-f]{8}-/);
    createdSessionIds.push(session.session_id);
    const sessionId = session.session_id;

    const askUserId = "mock-ask-answer-1";
    const question = "Which SKU and time period should I analyze?";
    const suggestions = [
      "SKU-001, last 30 days",
      "All SKUs, last 7 days",
      "SKU-002, last 14 days",
    ];
    const assistantText = "Mock response: test passed";
    const now = new Date().toISOString();

    let callCount = 0;

    await page.route(
      `**/api/v1/sessions/${sessionId}/stream`,
      async (route) => {
        callCount += 1;

        let events: unknown[];
        if (callCount === 1) {
          // First call: return ask_user_required + awaiting_input.
          events = [
            {
              type: "graph_node",
              event: "start",
              kind: "orchestrator",
              name: "classify_intent",
              run_id: "mock-run-1",
              status: "ok",
              meta: { model_name: "mock" },
              timestamp: now,
            },
            {
              type: "graph_node",
              event: "end",
              kind: "orchestrator",
              name: "classify_intent",
              run_id: "mock-run-1",
              status: "ok",
              meta: {
                model_name: "mock",
                category: "domain_analysis",
                confidence: 0.9,
              },
              timestamp: now,
              duration_ms: 50,
            },
            {
              type: "ask_user_required",
              session_id: sessionId,
              ask_user_id: askUserId,
              question,
              suggestions,
            },
            {
              type: "awaiting_input",
              session_id: sessionId,
              ask_user_id: askUserId,
              timestamp: now,
            },
          ];
        } else {
          // Second call (after answer submitted): return completed response.
          events = [
            {
              type: "text_delta",
              delta: assistantText,
            },
            {
              type: "response_ready",
              session_id: sessionId,
            },
            {
              type: "done",
            },
          ];
        }

        const body = events
          .map((e) => `data: ${JSON.stringify(e)}\n\n`)
          .join("");
        await route.fulfill({
          status: 200,
          headers: SSE_HEADERS,
          body,
        });
      },
    );

    // Also mock GET /messages so the assistant bubble has content to display.
    await page.route(
      `**/api/v1/sessions/${sessionId}/messages`,
      async (route) => {
        const messages = [
          {
            message_id: "mock-msg-user-1",
            session_id: sessionId,
            role: "user",
            content: "Analyze inventory",
            created_at: now,
          },
          {
            message_id: "mock-msg-asst-1",
            session_id: sessionId,
            role: "assistant",
            content: assistantText,
            created_at: now,
          },
        ];
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(messages),
        });
      },
    );

    await page.goto(`/chat/${sessionId}`);
    await expect(page.locator("textarea")).toBeVisible();

    await page.locator("textarea").fill("Analyze inventory");
    await page.getByRole("button", { name: /send/i }).click();

    const firstChip = page.locator('[data-testid="ask-user-suggestion-0"]');
    await expect(firstChip).toBeVisible({ timeout: ASK_USER_TIMEOUT });

    // Read the chip label before clicking (used for assertion below).
    const chipLabel = (await firstChip.textContent()) ?? "answer";
    await firstChip.click();

    const submitBtn = page.locator('[data-testid="ask-user-submit"]');
    await expect(submitBtn).toBeEnabled();
    await submitBtn.click();

    // Component transitions to submitted state: answered paragraph appears.
    const answeredEl = page.locator('[data-testid="ask-user-answered"]');
    await expect(answeredEl).toBeVisible({ timeout: 5_000 });
    await expect(answeredEl).toContainText(chipLabel);

    // After the answer is submitted, the orchestrator resumes and the agent
    // produces a final reply.  An assistant message bubble must eventually appear.
    const assistantBubbles = page.locator(".rounded-2xl.bg-\\[\\#1a1a2a\\]");
    await expect(assistantBubbles.first()).toBeVisible({ timeout: REPLY_TIMEOUT });
  });

  test("fully-specified prompt skips AskUser and shows assistant bubble directly", async ({
    page,
    createdSessionIds,
  }) => {
    test.setTimeout(30_000);

    await createSessionMockAndNavigate(
      page,
      createdSessionIds,
      "Ask-user E2E test — fully specified, no question",
      (sessionId) => mockCompletedStream(page, sessionId),
    );

    // All critical parameters are present: SKU, location, time range, and a
    // comparison baseline.  With the mock stream the completed response fires
    // immediately — no ask_user event is emitted.
    const fullySpecifiedPrompt =
      "Analyze inventory for SKU-001 at DC West for the past 30 days and compare with the previous month";

    await page.locator("textarea").fill(fullySpecifiedPrompt);
    await page.getByRole("button", { name: /send/i }).click();

    // The ask_user question element must NOT appear.
    const questionEl = page.locator('[data-testid="ask-user-question"]');
    await expect(questionEl).not.toBeVisible({ timeout: 5_000 });

    // An assistant reply bubble must appear (direct execution path).
    const assistantBubbles = page.locator(".rounded-2xl.bg-\\[\\#1a1a2a\\]");
    await expect(assistantBubbles.first()).toBeVisible({ timeout: REPLY_TIMEOUT });
  });
});
