/**
 * Shared Playwright SSE mock helpers for Business Decision OS.
 *
 * These helpers replace real Ollama backend calls (90–240 s per test) with
 * synthetic SSE event sequences that complete in under 1 second, keeping the
 * `make test-playwright` quality gate fast.
 *
 * Usage:
 *   import { mockCompletedStream, mockAskUserStream } from "./sse-mock";
 *
 *   // In a test, before page.goto():
 *   await mockCompletedStream(page, sessionId);
 *   await mockAskUserStream(page, sessionId, { question: "Which SKU?" });
 */

import type { Page } from "@playwright/test";

// ---------------------------------------------------------------------------
// Shared SSE response headers
// ---------------------------------------------------------------------------

const SSE_HEADERS: Record<string, string> = {
  "Content-Type": "text/event-stream",
  "Cache-Control": "no-cache",
  "X-Accel-Buffering": "no",
};

// ---------------------------------------------------------------------------
// mockCompletedStream
// ---------------------------------------------------------------------------

/**
 * Mock a successful, completed LLM stream for `sessionId`.
 *
 * Intercepts:
 *   - GET ..../api/v1/sessions/{sessionId}/stream   → synthetic SSE sequence
 *   - GET ..../api/v1/sessions/{sessionId}/messages → two-message JSON list
 *
 * The SSE sequence emits:
 *   1. graph_node start  (classify_intent)
 *   2. graph_node end    (classify_intent, category:"lookup")
 *   3. text_delta        (assistantText)
 *   4. response_ready
 *   5. done
 *
 * @param page          Playwright Page instance.
 * @param sessionId     UUID of the session to intercept.
 * @param assistantText Optional assistant reply text (default: "Mock response: test passed").
 */
export async function mockCompletedStream(
  page: Page,
  sessionId: string,
  assistantText?: string,
): Promise<void> {
  const text = assistantText ?? "Mock response: test passed";
  const now = new Date().toISOString();

  // --- SSE stream ---
  const streamPattern = `**/api/v1/sessions/${sessionId}/stream`;
  await page.route(streamPattern, async (route) => {
    const events = [
      {
        type: "graph_node",
        event: "start",
        kind: "orchestrator",
        name: "classify_intent",
        run_id: "mock-run-1",
        status: "ok",
        meta: { model_name: "mock" },
        timestamp: new Date().toISOString(),
      },
      {
        type: "graph_node",
        event: "end",
        kind: "orchestrator",
        name: "classify_intent",
        run_id: "mock-run-1",
        status: "ok",
        meta: { model_name: "mock", category: "lookup", confidence: 0.9 },
        timestamp: new Date().toISOString(),
        duration_ms: 50,
      },
      {
        type: "text_delta",
        delta: text,
      },
      {
        type: "response_ready",
        session_id: sessionId,
      },
      {
        type: "done",
      },
    ];

    const body = events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");
    await route.fulfill({
      status: 200,
      headers: SSE_HEADERS,
      body,
    });
  });

  // --- Messages list ---
  const messagesPattern = `**/api/v1/sessions/${sessionId}/messages`;
  await page.route(messagesPattern, async (route) => {
    const messages = [
      {
        message_id: "mock-msg-user-1",
        session_id: sessionId,
        role: "user",
        content: "mock user message",
        created_at: now,
      },
      {
        message_id: "mock-msg-asst-1",
        session_id: sessionId,
        role: "assistant",
        content: text,
        created_at: now,
      },
    ];

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(messages),
    });
  });
}

// ---------------------------------------------------------------------------
// mockAskUserStream
// ---------------------------------------------------------------------------

/**
 * Options for {@link mockAskUserStream}.
 */
export interface AskUserOpts {
  /** The clarifying question surfaced to the user. */
  question?: string;
  /** Quick-reply suggestion chips shown beneath the question. */
  suggestions?: string[];
  /** Identifier sent with ask_user_required / awaiting_input events. */
  askUserId?: string;
}

/**
 * Mock an LLM stream that pauses to ask the user a clarifying question.
 *
 * Intercepts:
 *   - GET ..../api/v1/sessions/{sessionId}/stream  → synthetic SSE sequence
 *
 * The SSE sequence emits:
 *   1. graph_node start  (classify_intent)
 *   2. graph_node end    (classify_intent, category:"domain_analysis")
 *   3. ask_user_required
 *   4. awaiting_input
 *
 * @param page      Playwright Page instance.
 * @param sessionId UUID of the session to intercept.
 * @param opts      Optional overrides for question, suggestions, and askUserId.
 */
export async function mockAskUserStream(
  page: Page,
  sessionId: string,
  opts?: AskUserOpts,
): Promise<void> {
  const askUserId = opts?.askUserId ?? "mock-ask-1";
  const question =
    opts?.question ?? "Which SKU and time period should I analyze?";
  const suggestions = opts?.suggestions ?? [
    "SKU-001, last 30 days",
    "All SKUs, last 7 days",
    "SKU-002, last 14 days",
  ];

  const streamPattern = `**/api/v1/sessions/${sessionId}/stream`;
  await page.route(streamPattern, async (route) => {
    const events = [
      {
        type: "graph_node",
        event: "start",
        kind: "orchestrator",
        name: "classify_intent",
        run_id: "mock-run-1",
        status: "ok",
        meta: { model_name: "mock" },
        timestamp: new Date().toISOString(),
      },
      {
        type: "graph_node",
        event: "end",
        kind: "orchestrator",
        name: "classify_intent",
        run_id: "mock-run-1",
        status: "ok",
        meta: { model_name: "mock", category: "domain_analysis", confidence: 0.9 },
        timestamp: new Date().toISOString(),
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
        timestamp: new Date().toISOString(),
      },
    ];

    const body = events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");
    await route.fulfill({
      status: 200,
      headers: SSE_HEADERS,
      body,
    });
  });
}
