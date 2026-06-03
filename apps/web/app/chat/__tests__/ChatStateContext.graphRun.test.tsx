/**
 * Unit tests for ChatStateContext graphRun / sessionStartedAt / sessionEndedAt
 * state management using graph_node SSE events.
 *
 * Scenarios:
 * 1. sendMessage path: stream emits graph_node(start+end) for classify_intent
 *    and select_mode → graphRun has 2 completed nodes.
 * 2. sessionStartedAt: set from the first graph_node start event timestamp.
 * 3. sessionEndedAt: set when response_ready is emitted.
 * 4. Reset on new send: graphRun is [] and sessionStartedAt/sessionEndedAt
 *    are null at the start of the second sendMessage call.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, waitFor } from "@testing-library/react";
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
  fetchSessionEvents: vi.fn().mockResolvedValue([]),
  updateSessionTitle: vi.fn().mockResolvedValue(undefined),
  setFeedback: vi.fn().mockResolvedValue(true),
}));

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

function makeDone(): SseEvent {
  return {
    type: "done",
    session_id: "sess-test",
    reply: undefined,
    timestamp: "2024-01-01T00:00:10.000Z",
  };
}

function makeGraphNodeStart(name: string, runId: string, ts: string): SseEvent {
  return {
    type: "graph_node",
    event: "start",
    kind: "orchestrator",
    name,
    run_id: runId,
    parent_run_id: null,
    timestamp: ts,
    input_summary: null,
    duration_ms: null,
    status: "ok",
    meta: {},
    output: null,
    token_cost: null,
    error: null,
  };
}

function makeGraphNodeEnd(name: string, runId: string, ts: string): SseEvent {
  return {
    type: "graph_node",
    event: "end",
    kind: "orchestrator",
    name,
    run_id: runId,
    parent_run_id: null,
    timestamp: ts,
    input_summary: null,
    duration_ms: 100,
    status: "ok",
    meta: {},
    output: null,
    token_cost: null,
    error: null,
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
// Spy component
// ---------------------------------------------------------------------------

interface SpyProps {
  sessionId: string;
  text: string;
}

function GraphRunSpyComponent({ sessionId, text }: SpyProps): React.ReactElement {
  const { sendMessage, getSessionState } = useChatStateContext();
  const sentRef = useRef(false);

  useEffect(() => {
    if (sentRef.current) return;
    sentRef.current = true;
    void sendMessage(sessionId, text);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const state = getSessionState(sessionId);

  return (
    <div>
      <span data-testid="graph-run-count">{state.graphRun.length}</span>
      <span data-testid="graph-run-statuses">
        {state.graphRun.map((n) => n.status).join(",")}
      </span>
      <span data-testid="graph-run-names">
        {state.graphRun.map((n) => n.name).join(",")}
      </span>
      <span data-testid="session-started-at">{state.sessionStartedAt ?? "null"}</span>
      <span data-testid="session-ended-at">{state.sessionEndedAt ?? "null"}</span>
      <span data-testid="is-sending">{String(state.isSending)}</span>
    </div>
  );
}

interface TwoSendSpyProps {
  sessionId: string;
  triggerSecondSendRef: React.MutableRefObject<(() => Promise<void>) | null>;
}

function TwoSendSpyComponent({
  sessionId,
  triggerSecondSendRef,
}: TwoSendSpyProps): React.ReactElement {
  const { sendMessage, getSessionState } = useChatStateContext();
  const sentRef = useRef(false);

  useEffect(() => {
    if (sentRef.current) return;
    sentRef.current = true;
    triggerSecondSendRef.current = () => sendMessage(sessionId, "second message");
    void sendMessage(sessionId, "first message");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const state = getSessionState(sessionId);

  return (
    <div>
      <span data-testid="graph-run-count">{state.graphRun.length}</span>
      <span data-testid="session-started-at">{state.sessionStartedAt ?? "null"}</span>
      <span data-testid="session-ended-at">{state.sessionEndedAt ?? "null"}</span>
      <span data-testid="is-sending">{String(state.isSending)}</span>
    </div>
  );
}

async function renderScenario(
  sessionId: string,
  events: SseEvent[],
): Promise<ReturnType<typeof render>> {
  vi.mocked(streamSession).mockResolvedValue(makeStream(events));

  const queryClient = makeQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <ChatStateProvider>
        <GraphRunSpyComponent sessionId={sessionId} text="hello" />
      </ChatStateProvider>
    </QueryClientProvider>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ChatStateProvider graphRun", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("populates graphRun with 2 completed nodes after classify_intent + select_mode", async () => {
    const events: SseEvent[] = [
      makeGraphNodeStart("classify_intent", "run-1", "2024-01-01T00:00:01.000Z"),
      makeGraphNodeEnd("classify_intent", "run-1", "2024-01-01T00:00:01.100Z"),
      makeGraphNodeStart("select_mode", "run-2", "2024-01-01T00:00:02.000Z"),
      makeGraphNodeEnd("select_mode", "run-2", "2024-01-01T00:00:02.200Z"),
      {
        type: "response_ready",
        mode: "sequential",
        timestamp: "2024-01-01T00:00:03.000Z",
      },
      makeDone(),
    ];

    const { getByTestId } = await renderScenario("sess-graphrun-1", events);

    await waitFor(
      () => {
        expect(getByTestId("is-sending").textContent).toBe("false");
      },
      { timeout: 3000 },
    );

    expect(getByTestId("graph-run-count").textContent).toBe("2");
    const statuses = getByTestId("graph-run-statuses").textContent ?? "";
    expect(statuses.split(",").every((s) => s === "completed")).toBe(true);
    expect(getByTestId("graph-run-names").textContent).toBe(
      "classify_intent,select_mode",
    );
  });

  it("sets sessionStartedAt from the first graph_node start event timestamp", async () => {
    const START_TIME = "2024-06-01T10:00:00.000Z";
    const events: SseEvent[] = [
      makeGraphNodeStart("classify_intent", "run-1", START_TIME),
      makeGraphNodeEnd("classify_intent", "run-1", "2024-06-01T10:00:00.100Z"),
      makeDone(),
    ];

    const { getByTestId } = await renderScenario("sess-graphrun-2", events);

    await waitFor(
      () => {
        expect(getByTestId("is-sending").textContent).toBe("false");
      },
      { timeout: 3000 },
    );

    expect(getByTestId("session-started-at").textContent).toBe(START_TIME);
  });

  it("sets sessionEndedAt (non-null) after response_ready is processed", async () => {
    const events: SseEvent[] = [
      {
        type: "response_ready",
        mode: "sequential",
        timestamp: "2024-06-01T10:00:05.000Z",
      },
      makeDone(),
    ];

    const { getByTestId } = await renderScenario("sess-graphrun-3", events);

    await waitFor(
      () => {
        expect(getByTestId("is-sending").textContent).toBe("false");
      },
      { timeout: 3000 },
    );

    expect(getByTestId("session-ended-at").textContent).not.toBe("null");
  });

  it("resets graphRun and session timestamps at the start of the second sendMessage", async () => {
    const START_TIME = "2024-06-01T10:00:00.000Z";

    const firstEvents: SseEvent[] = [
      makeGraphNodeStart("classify_intent", "run-1", START_TIME),
      makeGraphNodeEnd("classify_intent", "run-1", "2024-06-01T10:00:00.100Z"),
      {
        type: "response_ready",
        mode: "sequential",
        timestamp: "2024-06-01T10:00:05.000Z",
      },
      makeDone(),
    ];

    const secondEvents: SseEvent[] = [makeDone()];

    vi.mocked(streamSession)
      .mockResolvedValueOnce(makeStream(firstEvents))
      .mockResolvedValueOnce(makeStream(secondEvents));

    const triggerSecondSendRef = React.createRef<
      (() => Promise<void>) | null
    >() as React.MutableRefObject<(() => Promise<void>) | null>;
    triggerSecondSendRef.current = null;

    const queryClient = makeQueryClient();
    const { getByTestId } = render(
      <QueryClientProvider client={queryClient}>
        <ChatStateProvider>
          <TwoSendSpyComponent
            sessionId="sess-graphrun-4"
            triggerSecondSendRef={triggerSecondSendRef}
          />
        </ChatStateProvider>
      </QueryClientProvider>,
    );

    await waitFor(
      () => {
        expect(getByTestId("is-sending").textContent).toBe("false");
      },
      { timeout: 3000 },
    );

    expect(Number(getByTestId("graph-run-count").textContent)).toBeGreaterThan(0);
    expect(getByTestId("session-started-at").textContent).toBe(START_TIME);

    expect(triggerSecondSendRef.current).not.toBeNull();
    void triggerSecondSendRef.current!();

    await waitFor(
      () => {
        expect(getByTestId("is-sending").textContent).toBe("false");
      },
      { timeout: 3000 },
    );

    expect(getByTestId("session-started-at").textContent).toBe("null");
    expect(getByTestId("graph-run-count").textContent).toBe("0");
  });
});
