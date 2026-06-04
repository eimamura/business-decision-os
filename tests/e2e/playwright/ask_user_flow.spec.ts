import { testWithCleanup as test, expect } from "./fixtures";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Ask-user inline answer input flow.
 *
 * Requires the API server running with:
 *   MOCK_LLM=true MOCK_ASK_USER=true
 *
 * These env vars make ScenarioStubClaudeClient return needs_input=true,
 * which causes the graph to pause at wait_for_answer and emit ask_user_required.
 */
test.describe("AskUser inline answer input", () => {
  test("ask_user_required SSE event renders inline question with chips and answer input", async ({
    page,
    createdSessionIds,
  }) => {
    // Create a session via API
    const createRes = await page.request.post(`${API_BASE}/api/v1/sessions`, {
      data: { goal: "Ask user E2E test" },
      headers: { "X-Dev-User": "dev-user" },
    });
    expect(createRes.ok()).toBeTruthy();
    const session = (await createRes.json()) as { session_id: string };
    const sessionId = session.session_id;
    createdSessionIds.push(sessionId);

    // Navigate to the chat page
    await page.goto(`/chat/${sessionId}`);
    await expect(page.locator("textarea")).toBeVisible();

    // Send an analytical query — with MOCK_ASK_USER=true the backend should pause
    // and emit ask_user_required instead of completing the analysis
    await page.locator("textarea").fill("Analyze inventory levels for Q1");
    await page.getByRole("button", { name: /send/i }).click();

    // Wait for the ask_user question to appear
    const questionEl = page.locator('[data-testid="ask-user-question"]');
    await expect(questionEl).toBeVisible({ timeout: 15_000 });

    // First suggestion chip should be visible (T-099)
    const firstChip = page.locator('[data-testid="ask-user-suggestion-0"]');
    await expect(firstChip).toBeVisible();

    // Answer input and submit button should be present
    const answerInput = page.locator('[data-testid="ask-user-input"]');
    const submitBtn = page.locator('[data-testid="ask-user-submit"]');
    await expect(answerInput).toBeVisible();
    await expect(submitBtn).toBeVisible();

    // Type an answer and submit
    await answerInput.fill("Q1 2025");
    await submitBtn.click();

    // Component switches to non-interactive display
    const answeredEl = page.locator('[data-testid="ask-user-answered"]');
    await expect(answeredEl).toBeVisible({ timeout: 15_000 });
    await expect(answeredEl).toContainText("Q1 2025");

    // An assistant message should appear with the analysis result
    // (rendered from the HTTP response body returned by POST /sessions/{id}/answer)
    const assistantMsgs = page.locator(
      ".rounded-2xl.bg-\\[\\#1a1a2a\\]",
    );
    await expect(assistantMsgs.first()).toBeVisible({ timeout: 15_000 });
  });

  test("clicking a suggestion chip pre-populates the answer input", async ({
    page,
    createdSessionIds,
  }) => {
    const createRes = await page.request.post(`${API_BASE}/api/v1/sessions`, {
      data: { goal: "Chip pre-populate test" },
      headers: { "X-Dev-User": "dev-user" },
    });
    const session = (await createRes.json()) as { session_id: string };
    createdSessionIds.push(session.session_id);
    await page.goto(`/chat/${session.session_id}`);
    await expect(page.locator("textarea")).toBeVisible();

    await page.locator("textarea").fill("Analyze demand forecast");
    await page.getByRole("button", { name: /send/i }).click();

    const firstChip = page.locator('[data-testid="ask-user-suggestion-0"]');
    await expect(firstChip).toBeVisible({ timeout: 15_000 });

    const chipLabel = await firstChip.textContent();
    await firstChip.click();

    const answerInput = page.locator('[data-testid="ask-user-input"]');
    await expect(answerInput).toHaveValue(chipLabel ?? "");
  });
});
