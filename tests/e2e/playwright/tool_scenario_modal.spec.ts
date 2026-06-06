/**
 * T-264: ToolScenarioModal Playwright tests — real API backend.
 *
 * Tests 1–3 and 5 are pure UI tests that exercise modal state without
 * sending a message to the LLM. Test 4 clicks a scenario card, which
 * calls sendMessage() directly and waits for an Ollama response.
 *
 * Run with:
 *   make dev-up   (starts web + api + Ollama)
 *   make test-playwright
 */

import { testWithCleanup as test, expect } from "./fixtures";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
// gpt-oss:20b is slower than qwen2.5-coder:7b; allow up to 180s.
const OLLAMA_TIMEOUT = 180_000;

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
    await expect(dialog.getByText("Job Dispatch (HITL)")).toBeVisible();

    // Supply Planning, Finance & Cost, and S&OP were removed in P38-B-02
    await expect(dialog.getByText("Supply Planning")).not.toBeVisible();
    await expect(dialog.getByText("Finance & Cost")).not.toBeVisible();
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

    // Use .first() — "Demand Forecast" also appears in "Train Forecast Model"'s description text
    await expect(dialog.getByText("Demand Forecast").first()).toBeVisible({ timeout: 5_000 });
  });

  test("clicking a scenario card closes the modal and sends the prompt as a message", async ({
    page,
    request,
    createdSessionIds,
  }) => {
    test.setTimeout(OLLAMA_TIMEOUT + 30_000);
    const sessionId = await createSession(request, "Modal card click test");
    createdSessionIds.push(sessionId);

    await page.goto(`/chat/${sessionId}`);
    await expect(page.locator("textarea")).toBeVisible();
    await page.getByTitle("Browse all tool scenarios").click();
    await expect(page.getByRole("dialog")).toBeVisible({ timeout: 5_000 });

    // "SQL Direct Query" is under the default "Data Query" tab — visible immediately.
    // Clicking a scenario card calls handleScenarioApply() which sends the message
    // directly (does NOT fill the textarea — it calls sendMessage() directly).
    const dialog = page.getByRole("dialog");
    await dialog.getByText("SQL Direct Query").click();

    // Modal must be gone after clicking
    await expect(page.getByRole("dialog")).not.toBeVisible({ timeout: 3_000 });

    // A user message bubble should appear with the SQL prompt text
    await expect(
      page.locator(".rounded-2xl.bg-indigo-600").filter({ hasText: /在庫テーブル/ }),
    ).toBeVisible({ timeout: 8_000 });

    // An assistant bubble must appear with a response from Ollama.
    // Match /total/ to resolve on the footer "Completed {ts} · {n}s total", not
    // on per-node "Completed · Xs" labels that appear before the session is done.
    await expect(page.locator("text=/total/").first()).toBeVisible({
      timeout: OLLAMA_TIMEOUT,
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
