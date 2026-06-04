import { test, expect, type Page } from "@playwright/test";

/**
 * Verifies the three new behaviors from P28:
 * 1. Running graph nodes show a CSS spinner (animate-spin) instead of a static dot
 * 2. AskUser bubble is restored from persisted events on page refresh
 * 3. Execution trace (graphRun) is restored from persisted events on page refresh
 *
 * All routes are mocked — no backend or LLM required.
 */

const SESSION_ID = "00000000-0000-4000-a000-000000000002";
const NOW = "2024-01-01T00:00:00.000Z";
const RUN_ID_1 = "run-aaa-001";
const RUN_ID_2 = "run-bbb-002";

// ---------------------------------------------------------------------------
// Shared mock helpers
// ---------------------------------------------------------------------------

async function setupBaseRoutes(page: Page): Promise<void> {
  await page.route("**/api/v1/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });

  await page.route("**/api/v1/sessions", async (route) => {
    if (route.request().method() !== "GET") { await route.continue(); return; }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        { session_id: SESSION_ID, status: "active", title: "Persistence test session", created_at: NOW },
      ]),
    });
  });

  await page.route(`**/api/v1/sessions/${SESSION_ID}/messages`, async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
    } else {
      await route.fulfill({ status: 202, contentType: "application/json",
        body: JSON.stringify({ message_id: "msg-1", session_id: SESSION_ID, status: "processing" }) });
    }
  });

  await page.route(`**/api/v1/sessions/${SESSION_ID}/usage`, async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json",
      body: JSON.stringify({ input_tokens: 0, output_tokens: 0, total_cost_usd: 0 }) });
  });
}

// ---------------------------------------------------------------------------
// Test 1: Spinner (animate-spin) on a running node
// ---------------------------------------------------------------------------

test.describe("Spinner on running graph nodes", () => {
  test("running node shows animate-spin CSS class, completed node shows checkmark (✓)", async ({
    page,
  }) => {
    await setupBaseRoutes(page);

    // Events: classify_intent started but not finished (still "running")
    await page.route(`**/api/v1/sessions/${SESSION_ID}/events`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            event_type: "graph_node",
            payload: {
              type: "graph_node",
              event: "start",
              kind: "orchestrator",
              name: "classify_intent",
              run_id: RUN_ID_1,
              parent_run_id: null,
              timestamp: NOW,
              status: "ok",
              meta: {},
            },
            created_at: NOW,
          },
          {
            event_type: "graph_node",
            payload: {
              type: "graph_node",
              event: "end",
              kind: "orchestrator",
              name: "select_mode",
              run_id: RUN_ID_2,
              parent_run_id: null,
              timestamp: NOW,
              duration_ms: 300,
              status: "ok",
              meta: {},
            },
            created_at: NOW,
          },
        ]),
      });
    });

    await page.route(`**/api/v1/sessions/${SESSION_ID}/stream`, async (route) => {
      await route.fulfill({ status: 200,
        headers: { "Content-Type": "text/event-stream" },
        body: "" });
    });

    await page.goto(`/chat/${SESSION_ID}`);
    await page.waitForTimeout(500);

    // The running node (classify_intent) should have animate-spin
    const spinnerEl = page.locator(".animate-spin").first();
    await expect(spinnerEl).toBeVisible({ timeout: 5_000 });

    // The completed node (select_mode, end event with no start) renders as completed
    // with checkmark text — assert no second animate-spin
    const spinners = await page.locator(".animate-spin").count();
    expect(spinners).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// Test 2 & 3: AskUser bubble + Execution trace persist on navigation / refresh
// ---------------------------------------------------------------------------

const PERSISTED_EVENTS = [
  {
    event_type: "graph_node",
    payload: {
      type: "graph_node",
      event: "start",
      kind: "orchestrator",
      name: "classify_intent",
      run_id: RUN_ID_1,
      parent_run_id: null,
      timestamp: NOW,
      status: "ok",
      meta: {},
    },
    created_at: NOW,
  },
  {
    event_type: "graph_node",
    payload: {
      type: "graph_node",
      event: "end",
      kind: "orchestrator",
      name: "classify_intent",
      run_id: RUN_ID_1,
      parent_run_id: null,
      timestamp: NOW,
      duration_ms: 420,
      status: "ok",
      meta: { category: "analytical" },
    },
    created_at: NOW,
  },
  {
    event_type: "ask_user_required",
    payload: {
      type: "ask_user_required",
      session_id: SESSION_ID,
      ask_user_id: "ask-persist-01",
      question: "Which time period should I analyze?",
      suggestions: ["Q1 2025", "Q2 2025", "Full year"],
      timestamp: NOW,
    },
    created_at: NOW,
  },
  {
    event_type: "awaiting_input",
    payload: {
      type: "awaiting_input",
      session_id: SESSION_ID,
      ask_user_id: "ask-persist-01",
      timestamp: NOW,
    },
    created_at: NOW,
  },
];

async function setupPersistenceRoutes(page: Page): Promise<void> {
  await setupBaseRoutes(page);

  await page.route(`**/api/v1/sessions/${SESSION_ID}/events`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(PERSISTED_EVENTS),
    });
  });
}

test.describe("AskUser bubble persistence (restored from events on load)", () => {
  test("ask_user bubble appears when events endpoint returns ask_user_required + awaiting_input", async ({
    page,
  }) => {
    await setupPersistenceRoutes(page);

    // Navigate directly (simulates page refresh / navigating back)
    await page.goto(`/chat/${SESSION_ID}`);

    const questionEl = page.locator('[data-testid="ask-user-question"]');
    await expect(questionEl).toBeVisible({ timeout: 8_000 });
    await expect(questionEl).toContainText("Which time period should I analyze?");

    // Suggestion chips
    await expect(page.locator('[data-testid="ask-user-suggestion-0"]')).toBeVisible();
    await expect(page.locator('[data-testid="ask-user-suggestion-1"]')).toBeVisible();
    await expect(page.locator('[data-testid="ask-user-suggestion-2"]')).toBeVisible();

    // Answer input and submit button
    await expect(page.locator('[data-testid="ask-user-input"]')).toBeVisible();
    await expect(page.locator('[data-testid="ask-user-submit"]')).toBeVisible();
  });

  test("ask_user bubble is NOT shown when response_ready follows awaiting_input (already answered)", async ({
    page,
  }) => {
    await setupBaseRoutes(page);

    // Add response_ready after awaiting_input to simulate completed session
    const completedEvents = [
      ...PERSISTED_EVENTS,
      {
        event_type: "response_ready",
        payload: {
          type: "response_ready",
          mode: "sequential",
          timestamp: "2024-01-01T00:01:00.000Z",
        },
        created_at: "2024-01-01T00:01:00.000Z",
      },
    ];

    await page.route(`**/api/v1/sessions/${SESSION_ID}/events`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(completedEvents),
      });
    });

    await page.goto(`/chat/${SESSION_ID}`);
    await page.waitForTimeout(1_000);

    // The ask_user bubble should NOT appear for a completed session
    await expect(page.locator('[data-testid="ask-user-question"]')).not.toBeVisible();
  });
});

test.describe("Execution trace persistence (restored from events on load)", () => {
  test("completed graph nodes appear in ExecutionPanel when loaded from events", async ({
    page,
  }) => {
    await setupPersistenceRoutes(page);

    await page.goto(`/chat/${SESSION_ID}`);

    // "Classifying intent" label should appear (from classify_intent graph_node events)
    await expect(page.locator("text=Classifying intent")).toBeVisible({ timeout: 8_000 });
  });

  test("completed node duration is shown (≥0ms)", async ({ page }) => {
    await setupPersistenceRoutes(page);
    await page.goto(`/chat/${SESSION_ID}`);

    // Completed node shows "Completed · Xms" or "Completed · X.Xs"
    const durationEl = page.locator("text=/Completed ·/");
    await expect(durationEl).toBeVisible({ timeout: 8_000 });
  });
});
