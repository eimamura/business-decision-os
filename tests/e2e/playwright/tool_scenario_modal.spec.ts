/**
 * T-264: ToolScenarioModal Playwright tests — real API backend.
 *
 * Tests 1–3 and 5 are pure UI tests that exercise modal state without
 * sending a message to the LLM.  Test 4 clicks a scenario card (which calls
 * sendMessage() directly) and verifies the assistant bubble appears; the SSE
 * stream is intercepted by page.route() so this test completes in under 30 s
 * instead of waiting up to 180 s for Ollama.
 *
 * Run with:
 *   make dev-up   (starts web + api)
 *   make test-playwright
 */

import { testWithCleanup as test, expect } from "./fixtures";
import { mockCompletedStream } from "./sse-mock";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
/** Maximum time (ms) to wait for the mocked "Completed · total" footer. */
const MOCK_TIMEOUT = 15_000;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function createSession(
  request: Parameters<typeof test>[1]["request"],
  goal: string,
): Promise<string> {
  const res = await request.post(`${API_BASE}/api/v1/sessions`, {
    data: { goal },
    headers: { "X-Dev-User": "dev-user" },
  });
  expect(res.ok()).toBeTruthy();
  const body = (await res.json()) as { session_id: string };
  return body.session_id;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe("ToolScenarioModal (real API backend)", () => {
  test("modal opens when grid button is clicked", async ({
    page,
    request,
    createdSessionIds,
  }) => {
    const sessionId = await createSession(request, "Modal open test");
    createdSessionIds.push(sessionId);

    await page.goto(`/chat/${sessionId}`);
    await expect(page.locator("textarea")).toBeVisible();

    await page.getByTitle("Browse all tool scenarios").click();

    await expect(page.getByRole("dialog")).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("Tool Scenarios")).toBeVisible();
  });

  test("all 5 category tabs are visible in the open modal", async ({
    page,
    request,
    createdSessionIds,
  }) => {
    const sessionId = await createSession(request, "Modal tabs test");
    createdSessionIds.push(sessionId);

    await page.goto(`/chat/${sessionId}`);
    await expect(page.locator("textarea")).toBeVisible();
    await page.getByTitle("Browse all tool scenarios").click();
    await expect(page.getByRole("dialog")).toBeVisible({ timeout: 5_000 });

    const dialog = page.getByRole("dialog");
    await expect(dialog.getByText("Data Query")).toBeVisible();
    await expect(dialog.getByText("Forecasting")).toBeVisible();
    await expect(dialog.getByText("Simulation & Optimization")).toBeVisible();
    await expect(dialog.getByText("Ask User (HITL)")).toBeVisible();
    await expect(dialog.getByText("Supply Chain")).toBeVisible();

    // Supply Planning, Finance & Cost, and S&OP were removed in P38-B-02
    await expect(dialog.getByText("Supply Planning")).not.toBeVisible();
    await expect(dialog.getByText("Finance & Cost")).not.toBeVisible();
  });

  test("Supply Chain tab shows Daily Exception Review scenario (P86)", async ({
    page,
    request,
    createdSessionIds,
  }) => {
    const sessionId = await createSession(request, "Supply Chain scenarios test");
    createdSessionIds.push(sessionId);

    await page.goto(`/chat/${sessionId}`);
    await expect(page.locator("textarea")).toBeVisible();
    await page.getByTitle("Browse all tool scenarios").click();
    await expect(page.getByRole("dialog")).toBeVisible({ timeout: 5_000 });

    const dialog = page.getByRole("dialog");
    await dialog.getByRole("button", { name: "Supply Chain" }).click();

    await expect(dialog.getByText("Daily Exception Review").first()).toBeVisible({
      timeout: 5_000,
    });
  });

  test("Supply Chain tab shows Biggest Constraint Impact scenario (P90)", async ({
    page,
    request,
    createdSessionIds,
  }) => {
    const sessionId = await createSession(request, "Biggest Constraint Impact test");
    createdSessionIds.push(sessionId);

    await page.goto(`/chat/${sessionId}`);
    await expect(page.locator("textarea")).toBeVisible();
    await page.getByTitle("Browse all tool scenarios").click();
    await expect(page.getByRole("dialog")).toBeVisible({ timeout: 5_000 });

    const dialog = page.getByRole("dialog");
    await dialog.getByRole("button", { name: "Supply Chain" }).click();

    await expect(dialog.getByText("Biggest Constraint Impact").first()).toBeVisible({
      timeout: 5_000,
    });
  });

  test("Supply Chain tab shows Production Plan Adjustments scenario (P91)", async ({
    page,
    request,
    createdSessionIds,
  }) => {
    const sessionId = await createSession(request, "Production Plan Adjustments test");
    createdSessionIds.push(sessionId);

    await page.goto(`/chat/${sessionId}`);
    await expect(page.locator("textarea")).toBeVisible();
    await page.getByTitle("Browse all tool scenarios").click();
    await expect(page.getByRole("dialog")).toBeVisible({ timeout: 5_000 });

    const dialog = page.getByRole("dialog");
    await dialog.getByRole("button", { name: "Supply Chain" }).click();

    await expect(dialog.getByText("Production Plan Adjustments").first()).toBeVisible({
      timeout: 5_000,
    });
  });

  test("Supply Chain tab shows Customer & Region Demand Shifts scenario (P91)", async ({
    page,
    request,
    createdSessionIds,
  }) => {
    const sessionId = await createSession(request, "Customer & Region Demand Shifts test");
    createdSessionIds.push(sessionId);

    await page.goto(`/chat/${sessionId}`);
    await expect(page.locator("textarea")).toBeVisible();
    await page.getByTitle("Browse all tool scenarios").click();
    await expect(page.getByRole("dialog")).toBeVisible({ timeout: 5_000 });

    const dialog = page.getByRole("dialog");
    await dialog.getByRole("button", { name: "Supply Chain" }).click();

    await expect(dialog.getByText("Customer & Region Demand Shifts").first()).toBeVisible({
      timeout: 5_000,
    });
  });

  test("clicking Forecasting tab shows its scenario cards", async ({
    page,
    request,
    createdSessionIds,
  }) => {
    const sessionId = await createSession(request, "Modal Forecasting tab test");
    createdSessionIds.push(sessionId);

    await page.goto(`/chat/${sessionId}`);
    await expect(page.locator("textarea")).toBeVisible();
    await page.getByTitle("Browse all tool scenarios").click();
    await expect(page.getByRole("dialog")).toBeVisible({ timeout: 5_000 });

    const dialog = page.getByRole("dialog");
    await dialog.getByRole("button", { name: "Forecasting" }).click();

    // Use .first() — "Demand Forecast" may appear in description text of other cards
    await expect(dialog.getByText("Demand Forecast").first()).toBeVisible({ timeout: 5_000 });
  });

  test("clicking a scenario card closes the modal and sends the prompt as a message", async ({
    page,
    request,
    createdSessionIds,
  }) => {
    test.setTimeout(30_000);
    const sessionId = await createSession(request, "Modal card click test");
    createdSessionIds.push(sessionId);

    // Register the mock BEFORE goto so the route is active when the page loads.
    // The scenario card calls sendMessage() directly (not via textarea), so the
    // SSE stream subscription fires immediately after the card is clicked.
    await mockCompletedStream(page, sessionId);

    await page.goto(`/chat/${sessionId}`);
    await expect(page.locator("textarea")).toBeVisible();
    await page.getByTitle("Browse all tool scenarios").click();
    await expect(page.getByRole("dialog")).toBeVisible({ timeout: 5_000 });

    // "Natural Language Query" is under the default "Data Query" tab — visible immediately.
    // Clicking a scenario card calls handleScenarioApply() which sends the message
    // directly (does NOT fill the textarea — it calls sendMessage() directly).
    // Use .first() because "Natural Language Query" also appears in the prompt text
    // of the same card (as a truncated monospace preview).
    const dialog = page.getByRole("dialog");
    await dialog.getByText("Natural Language Query").first().click();

    // Modal must be gone after clicking.
    await expect(page.getByRole("dialog")).not.toBeVisible({ timeout: 3_000 });

    // A user message bubble should appear with the natural language query prompt text.
    await expect(
      page.locator(".rounded-2xl.bg-indigo-600").filter({ hasText: /Show me the current inventory/ }),
    ).toBeVisible({ timeout: 8_000 });

    // The ExecutionPanel "Completed · total" footer must appear (mock resolves fast).
    await expect(page.locator("text=/total/").first()).toBeVisible({
      timeout: MOCK_TIMEOUT,
    });
    const assistantBubble = page.locator(".rounded-2xl.bg-\\[\\#1a1a2a\\]").first();
    await expect(assistantBubble).toBeVisible({ timeout: 5_000 });
    await expect(assistantBubble).not.toBeEmpty();
    expect(await assistantBubble.getAttribute("class")).not.toContain("text-red-400");
  });

  test("clicking a quick chip in ToolScenarioBar fills textarea without opening the modal", async ({
    page,
    request,
    createdSessionIds,
  }) => {
    const sessionId = await createSession(request, "Chip fill test");
    createdSessionIds.push(sessionId);

    await page.goto(`/chat/${sessionId}`);
    await expect(page.locator("textarea")).toBeVisible();

    // Click the "SQL Query" chip directly in the bar
    await page.getByText("SQL Query").click();

    // Modal must NOT have opened
    await expect(page.getByRole("dialog")).not.toBeVisible();

    // Textarea must contain the SQL prompt
    await expect(page.locator("textarea")).toHaveValue(/在庫テーブル/);
  });
});
