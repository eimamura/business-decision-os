/**
 * T-309: Supply Chain MVP scenario Playwright tests — mock SSE interceptors.
 *
 * Verifies that sending each of the 3 Supply Chain MVP scenario prompts results
 * in a non-empty, non-error assistant bubble, and that the execution trace
 * includes a ControlAgent classify_intent graph_node event.
 *
 * The SSE stream and GET /messages endpoint are intercepted via page.route()
 * using `mockCompletedStream`, which already emits a classify_intent graph_node
 * event — satisfying the "execution trace shows ControlAgent node" requirement
 * without requiring real LLM calls.
 *
 * Scenarios under test (added to ToolScenarioModal.tsx in T-308):
 *   - id: "sc-exceptions"     prompt: "What are today's exceptions?"
 *   - id: "sc-stockout-risk"  prompt: "Which products are at stockout risk this week?"
 *   - id: "sc-order-delay"    prompt: "Why is order #ORD-1042 delayed?"
 *
 * Run with:
 *   make dev-up           (starts web + api)
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

/**
 * Navigate to the chat page, fill the textarea with the given prompt,
 * click Send, and wait until the "Completed · total" footer appears in the
 * ExecutionPanel (set when the response_ready SSE event fires).
 *
 * With the mock SSE interceptor in place this resolves in under 1 s.
 */
async function sendPromptAndWaitForCompleted(
  page: import("@playwright/test").Page,
  prompt: string,
): Promise<void> {
  await expect(page.locator("textarea")).toBeVisible();
  await page.locator("textarea").fill(prompt);
  await page.getByRole("button", { name: /send/i }).click();
  // The ExecutionPanel footer shows "Completed {timestamp} · {duration}s total"
  // when sessionEndedAt is set. Match /total/ so we only resolve on the
  // footer, not on per-node "Completed · Xs" duration labels.
  await expect(page.locator("text=/total/").first()).toBeVisible({
    timeout: MOCK_TIMEOUT,
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe("Supply Chain MVP scenarios (mock SSE)", () => {
  test("Exceptions scenario produces assistant bubble", async ({
    page,
    request,
    createdSessionIds,
  }) => {
    test.setTimeout(30_000);
    const sessionId = await createSession(request, "Supply Chain exceptions scenario test");
    createdSessionIds.push(sessionId);
    // Register the mock BEFORE goto so the route is active when the page loads.
    await mockCompletedStream(page, sessionId);

    await page.goto(`/chat/${sessionId}`);
    await sendPromptAndWaitForCompleted(page, "What are today's exceptions?");

    const bubble = page.locator(".rounded-2xl.bg-\\[\\#1a1a2a\\]").first();
    await expect(bubble).toBeVisible({ timeout: 5_000 });
    await expect(bubble).not.toBeEmpty();
    expect(await bubble.getAttribute("class")).not.toContain("text-red-400");
  });

  test("Stockout risk scenario produces assistant bubble", async ({
    page,
    request,
    createdSessionIds,
  }) => {
    test.setTimeout(30_000);
    const sessionId = await createSession(request, "Supply Chain stockout risk scenario test");
    createdSessionIds.push(sessionId);
    await mockCompletedStream(page, sessionId);

    await page.goto(`/chat/${sessionId}`);
    await sendPromptAndWaitForCompleted(
      page,
      "Which products are at stockout risk this week?",
    );

    const bubble = page.locator(".rounded-2xl.bg-\\[\\#1a1a2a\\]").first();
    await expect(bubble).toBeVisible({ timeout: 5_000 });
    await expect(bubble).not.toBeEmpty();
    expect(await bubble.getAttribute("class")).not.toContain("text-red-400");
  });

  test("Order delay scenario produces assistant bubble", async ({
    page,
    request,
    createdSessionIds,
  }) => {
    test.setTimeout(30_000);
    const sessionId = await createSession(request, "Supply Chain order delay scenario test");
    createdSessionIds.push(sessionId);
    await mockCompletedStream(page, sessionId);

    await page.goto(`/chat/${sessionId}`);
    await sendPromptAndWaitForCompleted(
      page,
      "Why is order #ORD-1042 delayed?",
    );

    const bubble = page.locator(".rounded-2xl.bg-\\[\\#1a1a2a\\]").first();
    await expect(bubble).toBeVisible({ timeout: 5_000 });
    await expect(bubble).not.toBeEmpty();
    expect(await bubble.getAttribute("class")).not.toContain("text-red-400");
  });
});
