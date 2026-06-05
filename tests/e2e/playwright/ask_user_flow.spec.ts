/**
 * Ask-user inline answer input flow — real API + real Ollama backend.
 *
 * The AskUser flow is triggered when:
 *   1. The intent classifier returns an analytical intent
 *      (domain_analysis, cross_domain_analysis, or decision_support), AND
 *   2. The information-gathering LLM call returns needs_input=true.
 *
 * Maximally underspecified prompts ("Analyze inventory", "Run a demand forecast")
 * reliably trigger the ask_user path with qwen2.5-coder:7b because the model
 * follows the ASK_USER_SYSTEM prompt instruction: "Only ask when a CRITICAL
 * parameter is absent (e.g., date range, specific SKU, warehouse location)."
 *
 * Requires: make dev-up  (web on WEB_PORT, api on API_PORT, Ollama on 11434)
 */

import { testWithCleanup as test, expect } from "./fixtures";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Maximum time (ms) to wait for the ask_user question bubble to appear.
 * Real Ollama (qwen2.5-coder:7b) completes intent + ask_user LLM calls in ~10-30s.
 */
const ASK_USER_TIMEOUT = 30_000;

/** Maximum time (ms) to wait for the assistant reply after submitting an answer. */
const REPLY_TIMEOUT = 30_000;

// ---------------------------------------------------------------------------
// Helper: create a session via API and navigate to its chat page.
// ---------------------------------------------------------------------------

async function createSessionAndNavigate(
  page: import("@playwright/test").Page,
  createdSessionIds: string[],
  goal: string,
): Promise<string> {
  const res = await page.request.post(`${API_BASE}/api/v1/sessions`, {
    data: { goal },
    headers: { "X-Dev-User": "dev-user" },
  });
  expect(res.ok()).toBeTruthy();
  const session = (await res.json()) as { session_id: string };
  expect(session.session_id).toMatch(/^[0-9a-f]{8}-/);
  createdSessionIds.push(session.session_id);
  await page.goto(`/chat/${session.session_id}`);
  await expect(page.locator("textarea")).toBeVisible();
  return session.session_id;
}

// ---------------------------------------------------------------------------
// Test suite
// ---------------------------------------------------------------------------

test.describe("AskUser inline answer input (real Ollama)", () => {
  test("ask_user_required SSE event renders inline question with chips and answer input", async ({
    page,
    createdSessionIds,
  }) => {
    test.setTimeout(90_000);

    await createSessionAndNavigate(
      page,
      createdSessionIds,
      "Ask-user E2E test — question bubble",
    );

    // "Analyze inventory" is maximally underspecified — SKU, period, and
    // location are all absent.  qwen2.5-coder:7b follows the ASK_USER_SYSTEM
    // rules and emits needs_input=true for this class of vague analytical prompt.
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
    test.setTimeout(90_000);

    await createSessionAndNavigate(
      page,
      createdSessionIds,
      "Ask-user E2E test — chip pre-populate",
    );

    // "Run a demand forecast" has no product, horizon, or location — triggers ask_user.
    await page.locator("textarea").fill("Run a demand forecast");
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
    test.setTimeout(90_000);

    await createSessionAndNavigate(
      page,
      createdSessionIds,
      "Ask-user E2E test — submit disabled state",
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
    test.setTimeout(120_000);

    await createSessionAndNavigate(
      page,
      createdSessionIds,
      "Ask-user E2E test — answer submission",
    );

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
    // The bubble uses the className from MessageBubble.tsx: rounded-2xl bg-[#1a1a2a]
    const assistantBubbles = page.locator(".rounded-2xl.bg-\\[\\#1a1a2a\\]");
    await expect(assistantBubbles.first()).toBeVisible({ timeout: REPLY_TIMEOUT });
  });

  test("fully-specified prompt skips AskUser and shows assistant bubble directly", async ({
    page,
    createdSessionIds,
  }) => {
    test.setTimeout(90_000);

    await createSessionAndNavigate(
      page,
      createdSessionIds,
      "Ask-user E2E test — fully specified, no question",
    );

    // All critical parameters are present: SKU, location, time range, and a
    // comparison baseline.  The information-gathering LLM should return
    // needs_input=false and the agent should proceed directly to execution.
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
