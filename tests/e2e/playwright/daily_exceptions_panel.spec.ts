/**
 * T-575: DailyExceptionsPanel Playwright tests — mock-API tier.
 *
 * All GET /api/v1/screenings/today and POST /api/v1/screenings/run calls are
 * intercepted via page.route() so no real screening job is needed.
 *
 * Scenarios:
 *   1. Populated state — GET returns a completed run with severity counts;
 *      panel renders severity counts and Investigate button; clicking it
 *      injects the Q3 prompt into the chat textarea.
 *   2. Null-run state  — GET returns {"run": null}; panel renders empty
 *      state with data-testid="daily-exceptions-empty" and Run now button.
 *   3. Run now + refresh — POST /run succeeds; follow-up GET returns the
 *      new run; panel transitions from empty state to populated state.
 *
 * Run via:
 *   make dev-up
 *   make test-playwright
 *
 * Never run with `npx playwright test` directly — see docs/TESTING.md.
 */

import { testWithCleanup as test, expect } from "./fixtures";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ---------------------------------------------------------------------------
// Shared fixture data
// ---------------------------------------------------------------------------

const POPULATED_RUN = {
  id: "test-run-001",
  run_date: "2026-06-12",
  triggered_by: "schedule",
  status: "completed",
  exception_count: 3,
  severity_counts: { critical: 2, high: 1 },
  payload: {
    exceptions: [
      {
        domain: "stockout_risk",
        severity: "critical",
        sku_id: "SKU-001",
        order_ref: null,
        headline_metric: "stockout risk critical: -10 units projected",
        detail: "Projected ending stock -10 units; estimated stockout 2026-06-15",
      },
      {
        domain: "stockout_risk",
        severity: "critical",
        sku_id: "SKU-002",
        order_ref: null,
        headline_metric: "stockout risk critical: -5 units projected",
        detail: "Projected ending stock -5 units",
      },
      {
        domain: "supply_delays",
        severity: "high",
        sku_id: null,
        order_ref: "SO-123",
        headline_metric: "3 days overdue",
        detail: "Order SO-123 from supplier SUPP-01 expected 2026-06-09",
      },
    ],
    counts: { stockout_risk: 2, supply_delays: 1 },
    truncated: false,
    missing_data: [],
  },
  error: null,
  created_at: "2026-06-12T06:00:00.000Z",
};

const RUN_NOW_RESULT = {
  id: "test-run-002",
  run_date: "2026-06-12",
  triggered_by: "manual",
  status: "completed",
  exception_count: 1,
  severity_counts: { high: 1 },
  payload: {
    exceptions: [
      {
        domain: "supply_delays",
        severity: "high",
        sku_id: null,
        order_ref: "SO-456",
        headline_metric: "1 day overdue",
        detail: "Order SO-456 from supplier SUPP-02",
      },
    ],
    counts: { supply_delays: 1 },
    truncated: false,
    missing_data: [],
  },
  error: null,
  created_at: "2026-06-12T10:00:00.000Z",
};

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

test.describe("DailyExceptionsPanel — mock-API tier", () => {
  test("populated state renders severity counts and Investigate button", async ({
    page,
    request,
    createdSessionIds,
  }) => {
    const sessionId = await createSession(request, "Daily exceptions populated test");
    createdSessionIds.push(sessionId);

    // Mock GET /api/v1/screenings/today → populated run
    await page.route("**/api/v1/screenings/today", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ run: POPULATED_RUN }),
      });
    });

    await page.goto(`/chat/${sessionId}`);
    await expect(page.locator("textarea")).toBeVisible();

    // Panel must be present
    await expect(page.locator('[data-testid="daily-exceptions-panel"]')).toBeVisible({
      timeout: 8_000,
    });

    // Severity counts must be visible
    await expect(page.getByText(/2 critical/i)).toBeVisible();
    await expect(page.getByText(/1 high/i)).toBeVisible();

    // Investigate button must be visible
    await expect(page.locator('[data-testid="daily-exceptions-investigate"]')).toBeVisible();

    // Run now button must be visible
    await expect(page.locator('[data-testid="daily-exceptions-run-now"]')).toBeVisible();

    // Empty-state indicator must NOT be present
    await expect(page.locator('[data-testid="daily-exceptions-empty"]')).not.toBeVisible();
  });

  test("clicking Investigate injects the Q3 prompt into the chat textarea", async ({
    page,
    request,
    createdSessionIds,
  }) => {
    const sessionId = await createSession(request, "Daily exceptions investigate test");
    createdSessionIds.push(sessionId);

    await page.route("**/api/v1/screenings/today", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ run: POPULATED_RUN }),
      });
    });

    await page.goto(`/chat/${sessionId}`);
    await expect(page.locator("textarea")).toBeVisible();

    // Wait for the Investigate button to appear
    const investigateBtn = page.locator('[data-testid="daily-exceptions-investigate"]');
    await expect(investigateBtn).toBeVisible({ timeout: 8_000 });

    await investigateBtn.click();

    // Textarea must be filled with the Q3 prompt
    await expect(page.locator("textarea")).toHaveValue(
      "What exceptions require human judgment today?",
      { timeout: 3_000 },
    );
  });

  test("null-run state renders empty state with Run now button", async ({
    page,
    request,
    createdSessionIds,
  }) => {
    const sessionId = await createSession(request, "Daily exceptions empty state test");
    createdSessionIds.push(sessionId);

    await page.route("**/api/v1/screenings/today", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ run: null }),
      });
    });

    await page.goto(`/chat/${sessionId}`);
    await expect(page.locator("textarea")).toBeVisible();

    // Panel must be present
    await expect(page.locator('[data-testid="daily-exceptions-panel"]')).toBeVisible({
      timeout: 8_000,
    });

    // Empty state indicator must be present
    await expect(page.locator('[data-testid="daily-exceptions-empty"]')).toBeVisible();

    // Run now button must be visible
    await expect(page.locator('[data-testid="daily-exceptions-run-now"]')).toBeVisible();

    // Investigate button must NOT be present in empty state
    await expect(
      page.locator('[data-testid="daily-exceptions-investigate"]'),
    ).not.toBeVisible();
  });

  test("Run now POST + refresh transitions panel from empty to populated", async ({
    page,
    request,
    createdSessionIds,
  }) => {
    const sessionId = await createSession(request, "Daily exceptions run now test");
    createdSessionIds.push(sessionId);

    // First GET (on page load) returns null run — use once() semantics via abort/fulfill
    // routing: first match returns null; subsequent matches return the populated run.
    // page.route with handler replacement: register null-returning route first;
    // POST /run response updates state directly (component sets run from POST body),
    // so the route counter tracks only the initial GET.
    await page.route("**/api/v1/screenings/today", async (route) => {
      // Always return null for GET requests — the POST response drives the update.
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ run: null }),
      });
    });

    // POST /run returns the populated run; the component updates state from POST body.
    await page.route("**/api/v1/screenings/run", async (route) => {
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({ run: RUN_NOW_RESULT }),
      });
    });

    await page.goto(`/chat/${sessionId}`);
    await expect(page.locator("textarea")).toBeVisible();

    // Confirm empty state first
    await expect(page.locator('[data-testid="daily-exceptions-empty"]')).toBeVisible({
      timeout: 8_000,
    });

    // Click Run now — this fires POST /run; the component updates state from the POST response
    await page.locator('[data-testid="daily-exceptions-run-now"]').click();

    // Panel must transition to populated state (Investigate button appears)
    await expect(
      page.locator('[data-testid="daily-exceptions-investigate"]'),
    ).toBeVisible({ timeout: 8_000 });

    // Empty state indicator must be gone
    await expect(
      page.locator('[data-testid="daily-exceptions-empty"]'),
    ).not.toBeVisible();

    // Severity count from RUN_NOW_RESULT
    await expect(page.getByText(/1 high/i)).toBeVisible();
  });
});
