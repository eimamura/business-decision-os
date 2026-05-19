import { test, expect } from "@playwright/test";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

test.describe("Chat flow", () => {
  test("session list page loads with New Session button", async ({ page }) => {
    await page.goto("/chat");
    await expect(page.getByRole("button", { name: /new session/i })).toBeVisible();
    await expect(page.getByRole("heading", { name: /business decision os/i })).toBeVisible();
  });

  test("new session navigates to valid UUID url", async ({ page }) => {
    await page.goto("/chat");
    await page.getByRole("button", { name: /new session/i }).click();

    await page.waitForURL(/\/chat\/[0-9a-f-]{36}$/, { timeout: 10_000 });
    const url = page.url();
    expect(url).toMatch(/\/chat\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/);
    expect(url).not.toContain("undefined");
  });

  test("chat page renders message input and send button", async ({ page }) => {
    // create session via API so we have a valid session_id
    const res = await page.request.post(`${API_BASE}/api/v1/sessions`, {
      data: { goal: "Playwright smoke test" },
      headers: { "X-Dev-User": "dev-user" },
    });
    const session = await res.json() as { session_id: string };
    expect(session.session_id).toMatch(/^[0-9a-f]{8}-/);

    await page.goto(`/chat/${session.session_id}`);
    await expect(page.locator("textarea")).toBeVisible();
    await expect(page.getByRole("button", { name: /send/i })).toBeVisible();
  });

  test("send button is disabled when input is empty", async ({ page }) => {
    const res = await page.request.post(`${API_BASE}/api/v1/sessions`, {
      data: { goal: "Playwright smoke test" },
      headers: { "X-Dev-User": "dev-user" },
    });
    const session = await res.json() as { session_id: string };

    await page.goto(`/chat/${session.session_id}`);
    const sendButton = page.getByRole("button", { name: /send/i });
    await expect(sendButton).toBeDisabled();
  });

  test("typing a message enables the send button", async ({ page }) => {
    const res = await page.request.post(`${API_BASE}/api/v1/sessions`, {
      data: { goal: "Playwright smoke test" },
      headers: { "X-Dev-User": "dev-user" },
    });
    const session = await res.json() as { session_id: string };

    await page.goto(`/chat/${session.session_id}`);
    await page.locator("textarea").fill("What is the current inventory status?");
    const sendButton = page.getByRole("button", { name: /send/i });
    await expect(sendButton).toBeEnabled();
  });

  test("session sidebar shows no undefined links", async ({ page }) => {
    const res = await page.request.post(`${API_BASE}/api/v1/sessions`, {
      data: { goal: "Sidebar check" },
      headers: { "X-Dev-User": "dev-user" },
    });
    const session = await res.json() as { session_id: string };

    await page.goto(`/chat/${session.session_id}`);
    const links = await page.locator("a[href*='/chat/']").all();
    for (const link of links) {
      const href = await link.getAttribute("href");
      expect(href).not.toContain("undefined");
    }
  });
});
