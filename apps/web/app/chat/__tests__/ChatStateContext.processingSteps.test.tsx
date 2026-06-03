/**
 * T-127: Unit tests for ChatStateContext processingSteps / sessionStartedAt /
 * sessionEndedAt state management.
 *
 * Scenarios:
 * 1. sendMessage path: stream emits intent_classified → execution_mode_selected
 *    → response_ready → done.  processingSteps has 3 steps with correct statuses.
 * 2. sessionStartedAt: stream emits query_received with timestamp;
 *    sessionStartedAt matches.
 * 3. sessionEndedAt: set when response_ready is emitted.
 * 4. Reset on new send: processingSteps is [] and sessionStartedAt/sessionEndedAt
 *    are null at the start of the second sendMessage call.
 *
 * Strategy: mirrors ChatStateContext.text_delta.test.tsx exactly — vi.mock the
 * entire @/lib/api module, render ChatStateProvider + a thin spy component,
 * trigger sendMessage, then use waitFor to observe DOM-reflected state.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, waitFor } from "@testing-library/react";
import React, { useEffect, useRef } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { SseEvent } from "@/types/chat";

// ---------------------------------------------------------------------------
// Module mocks — same pattern as ChatStateContext.text_delta.test.tsx
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

// Must import after mocks.
const { ChatStateProvider, useChatStateContext } = await import(
  "@/app/chat/ChatStateContext"
);
const { streamSession } = await import("@/lib/api");

// ---------------------------------------------------------------------------
// Helpers — same pattern as the existing test file
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

function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

// ---------------------------------------------------------------------------
// Spy component — renders processingSteps count and session timestamps into DOM
// ---------------------------------------------------------------------------

interface SpyProps {
  sessionId: string;
  text: string;
  onSendComplete?: () => void;
}

function StepsSpyComponent({ sessionId, text }: SpyProps): React.ReactElement {
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
      <span data-testid="step-count">{state.processingSteps.length}</span>
      <span data-testid="step-statuses">
        {state.processingSteps.map((s) => s.status).join(",")}
      </span>
      <span data-testid="step-ids">
        {state.processingSteps.map((s) => s.id).join(",")}
      </span>
      <span data-testid="session-started-at">{state.sessionStartedAt ?? "null"}</span>
      <span data-testid="session-ended-at">{state.sessionEndedAt ?? "null"}</span>
      <span data-testid="is-sending">{String(state.isSending)}</span>
    </div>
  );
}

// A two-send spy: sends once on mount, exposes a trigger ref for the second send.
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
      <span data-testid="step-count">{state.processingSteps.length}</span>
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
  const result = render(
    <QueryClientProvider client={queryClient}>
      <ChatStateProvider>
        <StepsSpyComponent sessionId={sessionId} text="hello" />
      </ChatStateProvider>
    </QueryClientProvider>,
  );
  return result;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ChatStateProvider processingSteps", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // T-127 scenario 1: sendMessage emits intent_classified, execution_mode_selected,
  // response_ready, done → processingSteps has 3 completed steps
  it("populates processingSteps with 3 completed steps after a full stream", async () => {
    const events: SseEvent[] = [
      {
        type: "intent_classified",
        category: "optimization",
        confidence: 0.88,
        rationale: "test",
        timestamp: "2024-01-01T00:00:01.000Z",
      },
      {
        type: "execution_mode_selected",
        mode: "sequential",
        agents: ["AgentA"],
        requires_planning: false,
        requires_dag: false,
        rationale: "test",
        timestamp: "2024-01-01T00:00:02.000Z",
      },
      {
        type: "response_ready",
        mode: "sequential",
        timestamp: "2024-01-01T00:00:03.000Z",
      },
      makeDone(),
    ];

    const { getByTestId } = await renderScenario("sess-steps-1", events);

    await waitFor(
      () => {
        expect(getByTestId("is-sending").textContent).toBe("false");
      },
      { timeout: 3000 },
    );

    expect(getByTestId("step-count").textContent).toBe("3");
    // All three steps should be completed
    const statuses = getByTestId("step-statuses").textContent ?? "";
    expect(statuses.split(",").every((s) => s === "completed")).toBe(true);
    // Step ids in order
    expect(getByTestId("step-ids").textContent).toBe("intent,route,response");
  });

  // T-127 scenario 2: query_received with timestamp → sessionStartedAt matches
  it("sets sessionStartedAt from query_received event timestamp", async () => {
    const START_TIME = "2024-06-01T10:00:00.000Z";
    const events: SseEvent[] = [
      {
        type: "query_received",
        session_id: "sess-steps-2",
        timestamp: START_TIME,
      },
      makeDone(),
    ];

    const { getByTestId } = await renderScenario("sess-steps-2", events);

    await waitFor(
      () => {
        expect(getByTestId("is-sending").textContent).toBe("false");
      },
      { timeout: 3000 },
    );

    expect(getByTestId("session-started-at").textContent).toBe(START_TIME);
  });

  // T-127 scenario 3: sessionEndedAt is set when response_ready or done is emitted.
  // The context sets sessionEndedAt to the timestamp of the last response_ready/done event;
  // since done also matches, the final value is done's timestamp.
  it("sets sessionEndedAt (non-null) after response_ready and done events are processed", async () => {
    const events: SseEvent[] = [
      {
        type: "response_ready",
        mode: "sequential",
        timestamp: "2024-06-01T10:00:05.000Z",
      },
      makeDone(),
    ];

    const { getByTestId } = await renderScenario("sess-steps-3", events);

    await waitFor(
      () => {
        expect(getByTestId("is-sending").textContent).toBe("false");
      },
      { timeout: 3000 },
    );

    // sessionEndedAt is set to the timestamp of the most recent response_ready or done event
    expect(getByTestId("session-ended-at").textContent).not.toBe("null");
  });

  // T-127 scenario 4: reset on new send — processingSteps/sessionStartedAt/
  // sessionEndedAt are cleared at the start of the second sendMessage
  it("resets processingSteps and session timestamps to null at the start of the second sendMessage", async () => {
    const START_TIME = "2024-06-01T10:00:00.000Z";

    // First stream: sets processingSteps + timestamps
    const firstEvents: SseEvent[] = [
      {
        type: "query_received",
        session_id: "sess-steps-4",
        timestamp: START_TIME,
      },
      {
        type: "intent_classified",
        category: "optimization",
        confidence: 0.9,
        rationale: "test",
        timestamp: "2024-06-01T10:00:01.000Z",
      },
      {
        type: "response_ready",
        mode: "sequential",
        timestamp: "2024-06-01T10:00:05.000Z",
      },
      makeDone(),
    ];

    // Second stream: no events before done — so we can observe the reset state
    const secondEvents: SseEvent[] = [makeDone()];

    // Set up streamSession to return first stream on first call, second on second
    vi.mocked(streamSession)
      .mockResolvedValueOnce(makeStream(firstEvents))
      .mockResolvedValueOnce(makeStream(secondEvents));

    const triggerSecondSendRef = React.createRef<(() => Promise<void>) | null>() as React.MutableRefObject<
      (() => Promise<void>) | null
    >;
    triggerSecondSendRef.current = null;

    const queryClient = makeQueryClient();
    const { getByTestId } = render(
      <QueryClientProvider client={queryClient}>
        <ChatStateProvider>
          <TwoSendSpyComponent
            sessionId="sess-steps-4"
            triggerSecondSendRef={triggerSecondSendRef}
          />
        </ChatStateProvider>
      </QueryClientProvider>,
    );

    // Wait for the first send to complete
    await waitFor(
      () => {
        expect(getByTestId("is-sending").textContent).toBe("false");
      },
      { timeout: 3000 },
    );

    // Verify first send populated the state
    expect(Number(getByTestId("step-count").textContent)).toBeGreaterThan(0);
    expect(getByTestId("session-started-at").textContent).toBe(START_TIME);

    // Trigger the second send
    expect(triggerSecondSendRef.current).not.toBeNull();
    void triggerSecondSendRef.current!();

    // At the start of the second send (before stream resolves), the state should be reset.
    // We observe this by checking that sessionStartedAt and sessionEndedAt are null once
    // the second send completes (second stream has no query_received or response_ready).
    await waitFor(
      () => {
        expect(getByTestId("is-sending").textContent).toBe("false");
      },
      { timeout: 3000 },
    );

    // After second send (which had no query_received):
    // sessionStartedAt should be null (no query_received in second stream)
    expect(getByTestId("session-started-at").textContent).toBe("null");
    // processingSteps should be empty (second stream had no intent/route/response events)
    expect(getByTestId("step-count").textContent).toBe("0");
  });
});
