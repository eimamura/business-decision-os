import { testWithCleanup as test, expect } from "./fixtures";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

test.describe("Chat flow", () => {
  test("chat sidebar shows New Session button", async ({ page, createdSessionIds }) => {
    // /chat auto-redirects; navigate to an actual session page to see the sidebar
    const res = await page.request.post(`${API_BASE}/api/v1/sessions`, {
      data: { goal: "Playwright smoke test" },
      headers: { "X-Dev-User": "dev-user" },
    });
    const session = await res.json() as { session_id: string };
    createdSessionIds.push(session.session_id);

    await page.goto(`/chat/${session.session_id}`);
    await expect(page.getByTitle("New Session")).toBeVisible();
  });

  test("new session navigates to valid UUID url", async ({ page, createdSessionIds }) => {
    const res = await page.request.post(`${API_BASE}/api/v1/sessions`, {
      data: { goal: "Playwright smoke test" },
      headers: { "X-Dev-User": "dev-user" },
    });
    const session = await res.json() as { session_id: string };
    createdSessionIds.push(session.session_id);

    await page.goto(`/chat/${session.session_id}`);
    await page.getByTitle("New Session").click();

    await page.waitForURL(/\/chat\/[0-9a-f-]{36}$/, { timeout: 10_000 });
    const url = page.url();
    const newId = url.split("/chat/")[1];
    if (newId && newId !== session.session_id) createdSessionIds.push(newId);

    expect(url).toMatch(/\/chat\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/);
    expect(url).not.toContain("undefined");
  });

  test("chat page renders message input and send button", async ({ page, createdSessionIds }) => {
    // create session via API so we have a valid session_id
    const res = await page.request.post(`${API_BASE}/api/v1/sessions`, {
      data: { goal: "Playwright smoke test" },
      headers: { "X-Dev-User": "dev-user" },
    });
    const session = await res.json() as { session_id: string };
    expect(session.session_id).toMatch(/^[0-9a-f]{8}-/);
    createdSessionIds.push(session.session_id);

    await page.goto(`/chat/${session.session_id}`);
    await expect(page.locator("textarea")).toBeVisible();
    await expect(page.getByRole("button", { name: /send/i })).toBeVisible();
  });

  test("send button is disabled when input is empty", async ({ page, createdSessionIds }) => {
    const res = await page.request.post(`${API_BASE}/api/v1/sessions`, {
      data: { goal: "Playwright smoke test" },
      headers: { "X-Dev-User": "dev-user" },
    });
    const session = await res.json() as { session_id: string };
    createdSessionIds.push(session.session_id);

    await page.goto(`/chat/${session.session_id}`);
    const sendButton = page.getByRole("button", { name: /send/i });
    await expect(sendButton).toBeDisabled();
  });

  test("typing a message enables the send button", async ({ page, createdSessionIds }) => {
    const res = await page.request.post(`${API_BASE}/api/v1/sessions`, {
      data: { goal: "Playwright smoke test" },
      headers: { "X-Dev-User": "dev-user" },
    });
    const session = await res.json() as { session_id: string };
    createdSessionIds.push(session.session_id);

    await page.goto(`/chat/${session.session_id}`);
    await page.locator("textarea").fill("What is the current inventory status?");
    const sendButton = page.getByRole("button", { name: /send/i });
    await expect(sendButton).toBeEnabled();
  });

  test("session sidebar shows no undefined links", async ({ page, createdSessionIds }) => {
    const res = await page.request.post(`${API_BASE}/api/v1/sessions`, {
      data: { goal: "Sidebar check" },
      headers: { "X-Dev-User": "dev-user" },
    });
    const session = await res.json() as { session_id: string };
    createdSessionIds.push(session.session_id);

    await page.goto(`/chat/${session.session_id}`);
    const links = await page.locator("a[href*='/chat/']").all();
    for (const link of links) {
      const href = await link.getAttribute("href");
      expect(href).not.toContain("undefined");
    }
  });

  test("clear all sessions requires confirmation and calls DELETE /api/v1/admin/sessions", async ({
    page,
    createdSessionIds,
  }) => {
    // Create two sessions so the sidebar shows the "Clear all" button
    const [r1, r2] = await Promise.all([
      page.request.post(`${API_BASE}/api/v1/sessions`, {
        data: { goal: "Clear-all test A" },
        headers: { "X-Dev-User": "dev-user" },
      }),
      page.request.post(`${API_BASE}/api/v1/sessions`, {
        data: { goal: "Clear-all test B" },
        headers: { "X-Dev-User": "dev-user" },
      }),
    ]);
    const s1 = await r1.json() as { session_id: string };
    const s2 = await r2.json() as { session_id: string };
    // Pushed as fallback; cleared below if the delete-all succeeds
    createdSessionIds.push(s1.session_id, s2.session_id);

    await page.goto(`/chat/${s1.session_id}`);
    await expect(page.locator("textarea")).toBeVisible();

    // "Clear all" button should be visible in the sidebar
    await expect(page.getByTitle("Clear all sessions")).toBeVisible();

    // First click: shows "Sure?" confirmation — does NOT delete yet
    await page.getByTitle("Clear all sessions").click();
    await expect(page.getByText("Sure?")).toBeVisible();

    // Verify the sessions still exist (no premature deletion)
    const checkRes = await page.request.get(`${API_BASE}/api/v1/sessions`, {
      headers: { "X-Dev-User": "dev-user" },
    });
    const sessionsBefore = await checkRes.json() as { session_id: string }[];
    expect(sessionsBefore.some((s) => s.session_id === s1.session_id)).toBe(true);

    // Second click: "Sure?" triggers the actual DELETE
    // deleteAllSessions() calls DELETE /api/v1/sessions (no /admin prefix)
    const deleteResponsePromise = page.waitForResponse(
      (res) =>
        /\/api\/v1\/sessions$/.test(res.url()) && res.request().method() === "DELETE",
    );
    await page.getByText("Sure?").click();

    const deleteResponse = await deleteResponsePromise;
    expect(deleteResponse.status()).toBe(204);

    // After delete-all succeeds, layout calls router.push("/chat") which navigates
    // away from the current /chat/{uuid} page. Wait for a URL that no longer contains
    // s1's session ID (the current /chat/{uuid} pattern would resolve immediately).
    await page.waitForURL((url) => !url.href.includes(s1.session_id), { timeout: 10_000 });

    // Sessions were deleted — clear the cleanup list to suppress 404 warnings
    createdSessionIds.splice(0, createdSessionIds.length);

    // Verify the deleted sessions no longer appear in the sidebar
    const deletedId = s1.session_id;
    await expect(page.locator(`a[href*="${deletedId}"]`)).not.toBeVisible({ timeout: 5_000 });
  });
});
