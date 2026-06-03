/**
 * T-116: Unit tests for ChatStateContext text_delta SSE event handling.
 *
 * Tests that ChatStateProvider correctly:
 * 1. Appends text_delta event deltas to the assistant message content
 * 2. Falls back to done.reply when no text_delta events were received
 * 3. Ignores done.reply when at least one text_delta was already streamed
 *
 * Strategy: render the provider + a thin spy component, trigger sendMessage,
 * then use waitFor to observe the resulting DOM state once the stream settles.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, act, waitFor } from "@testing-library/react";
import React, { useEffect, useRef } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { SseEvent } from "@/types/chat";

// ---------------------------------------------------------------------------
// Module mocks
// ---------------------------------------------------------------------------

vi.mock("@/lib/api", () => ({
  streamSession: vi.fn(),
  postMessage: vi.fn().mockResolvedValue(undefined),
  fetchMessages: vi.fn().mockResolvedValue([]),
  fetchSessionUsage: vi.fn().mockResolvedValue({ inputTokens: 0, outputTokens: 0, costUsd: 0 }),
  updateSessionTitle: vi.fn().mockResolvedValue(undefined),
  setFeedback: vi.fn().mockResolvedValue(true),
}));

// Must import after mocks.
const { ChatStateProvider, useChatStateContext } = await import(
  "@/app/chat/ChatStateContext"
);
const { streamSession } = await import("@/lib/api");

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function* makeStream(events: SseEvent[]): AsyncGenerator<SseEvent> {
  for (const evt of events) {
    yield evt;
  }
}

function makeTextDelta(delta: string): SseEvent {
  return {
    type: "text_delta",
    session_id: "sess-test",
    delta,
    timestamp: new Date().toISOString(),
  };
}

function makeDone(reply?: string | null): SseEvent {
  return {
    type: "done",
    session_id: "sess-test",
    reply: reply ?? undefined,
    timestamp: new Date().toISOString(),
  };
}

function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

// ---------------------------------------------------------------------------
// Spy component — renders the assistant message state into data-testid attrs
// ---------------------------------------------------------------------------

interface SpyProps {
  sessionId: string;
  text: string;
}

function SpyComponent({ sessionId, text }: SpyProps): React.ReactElement {
  const { sendMessage, getSessionState } = useChatStateContext();
  const sentRef = useRef(false);

  useEffect(() => {
    if (sentRef.current) return;
    sentRef.current = true;
    void sendMessage(sessionId, text);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const state = getSessionState(sessionId);
  const assistant = state.messages.find((m) => m.role === "assistant");

  return (
    <div>
      <span data-testid="content">{assistant?.content ?? ""}</span>
      <span data-testid="streaming">{String(assistant?.isStreaming ?? false)}</span>
      <span data-testid="sending">{String(state.isSending)}</span>
    </div>
  );
}

async function renderScenario(
  sessionId: string,
  events: SseEvent[],
): Promise<ReturnType<typeof render>> {
  vi.mocked(streamSession).mockResolvedValue(makeStream(events));

  const queryClient = makeQueryClient();
  const result = render(
    <QueryClientProvider client={queryClient}>
      <ChatStateProvider>
        <SpyComponent sessionId={sessionId} text="hello" />
      </ChatStateProvider>
    </QueryClientProvider>,
  );
  return result;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ChatStateProvider text_delta handling", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // -------------------------------------------------------------------------
  // T-116 scenario 1: two text_delta then done(reply=null)
  // -------------------------------------------------------------------------

  it("after done, assistant content is the concatenation of all text_delta values", async () => {
    const events: SseEvent[] = [
      makeTextDelta("Hello"),
      makeTextDelta(" world"),
      makeDone(null),
    ];

    const { getByTestId } = await renderScenario("s1", events);

    await waitFor(
      () => {
        expect(getByTestId("sending").textContent).toBe("false");
      },
      { timeout: 3000 },
    );

    expect(getByTestId("content").textContent).toBe("Hello world");
  });

  it("after done, isStreaming is false when stream ends normally", async () => {
    const events: SseEvent[] = [
      makeTextDelta("Hello"),
      makeTextDelta(" world"),
      makeDone(null),
    ];

    const { getByTestId } = await renderScenario("s2", events);

    await waitFor(
      () => {
        expect(getByTestId("sending").textContent).toBe("false");
      },
      { timeout: 3000 },
    );

    expect(getByTestId("streaming").textContent).toBe("false");
  });

  // -------------------------------------------------------------------------
  // T-116 scenario 2: done(reply="fallback text") with no text_delta events
  // -------------------------------------------------------------------------

  it("when no text_delta events received, done.reply is used as content", async () => {
    const events: SseEvent[] = [makeDone("fallback text")];

    const { getByTestId } = await renderScenario("s3", events);

    await waitFor(
      () => {
        expect(getByTestId("sending").textContent).toBe("false");
      },
      { timeout: 3000 },
    );

    expect(getByTestId("content").textContent).toBe("fallback text");
  });

  it("when no text_delta received, isStreaming is false after done", async () => {
    const events: SseEvent[] = [makeDone("fallback text")];

    const { getByTestId } = await renderScenario("s4", events);

    await waitFor(
      () => {
        expect(getByTestId("sending").textContent).toBe("false");
      },
      { timeout: 3000 },
    );

    expect(getByTestId("streaming").textContent).toBe("false");
  });

  // -------------------------------------------------------------------------
  // T-116 scenario 3: text_delta("streamed") then done(reply="should be ignored")
  // -------------------------------------------------------------------------

  it("when text_delta was streamed, done.reply is ignored and streamed content is kept", async () => {
    const events: SseEvent[] = [
      makeTextDelta("streamed"),
      makeDone("should be ignored"),
    ];

    const { getByTestId } = await renderScenario("s5", events);

    await waitFor(
      () => {
        expect(getByTestId("sending").textContent).toBe("false");
      },
      { timeout: 3000 },
    );

    expect(getByTestId("content").textContent).toBe("streamed");
  });

  it("when text_delta was streamed, content is not overwritten by done.reply", async () => {
    const events: SseEvent[] = [
      makeTextDelta("streamed"),
      makeDone("should be ignored"),
    ];

    const { getByTestId } = await renderScenario("s6", events);

    await waitFor(
      () => {
        expect(getByTestId("sending").textContent).toBe("false");
      },
      { timeout: 3000 },
    );

    expect(getByTestId("content").textContent).not.toBe("should be ignored");
  });
});
