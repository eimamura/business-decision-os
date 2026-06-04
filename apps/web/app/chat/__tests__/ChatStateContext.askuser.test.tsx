/**
 * Unit tests for ChatStateContext AskUser flow.
 *
 * Scenarios:
 * 1. sendMessage: ask_user_required SSE event adds a role="ask_user" message with
 *    question text and suggestion list to the session state.
 * 2. sendAskUserAnswer: postAskUserAnswer is called with the correct (sessionId, answer)
 *    payload.
 * 3. sendAskUserAnswer: isSending is false after the done event completes the stream.
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
  postAskUserAnswer: vi.fn().mockResolvedValue(undefined),
  fetchMessages: vi.fn().mockResolvedValue([]),
  fetchSessionEvents: vi.fn().mockResolvedValue([]),
  fetchSessionUsage: vi.fn().mockResolvedValue({ inputTokens: 0, outputTokens: 0, costUsd: 0 }),
  updateSessionTitle: vi.fn().mockResolvedValue(undefined),
  setFeedback: vi.fn().mockResolvedValue(true),
}));

const { ChatStateProvider, useChatStateContext } = await import(
  "@/app/chat/ChatStateContext"
);
const { streamSession, postAskUserAnswer } = await import("@/lib/api");

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function* makeStream(events: SseEvent[]): AsyncGenerator<SseEvent> {
  for (const evt of events) {
    yield evt;
  }
}

const NOW = "2024-01-01T00:00:00.000Z";

function makeAskUserRequired(sessionId: string): SseEvent {
  return {
    type: "ask_user_required",
    session_id: sessionId,
    ask_user_id: "ask-001",
    question: "Which inventory scope?",
    suggestions: ["All inventory", "Low stock only", "Overstock only"],
    timestamp: NOW,
  };
}

function makeAwaitingInput(sessionId: string): SseEvent {
  return {
    type: "awaiting_input",
    session_id: sessionId,
    ask_user_id: "ask-001",
    timestamp: NOW,
  };
}

function makeDone(sessionId: string, reply?: string): SseEvent {
  return {
    type: "done",
    session_id: sessionId,
    reply: reply ?? undefined,
    timestamp: NOW,
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
// Spy components
// ---------------------------------------------------------------------------

function SendMessageSpy({ sessionId }: { sessionId: string }): React.ReactElement {
  const { sendMessage, getSessionState } = useChatStateContext();
  const sentRef = useRef(false);

  useEffect(() => {
    if (sentRef.current) return;
    sentRef.current = true;
    void sendMessage(sessionId, "Analyze inventory");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const state = getSessionState(sessionId);
  const askUserMsg = state.messages.find((m) => m.role === "ask_user");

  return (
    <div>
      <span data-testid="has-ask-user">{String(!!askUserMsg)}</span>
      <span data-testid="ask-user-question">{askUserMsg?.askUserQuestion ?? ""}</span>
      <span data-testid="ask-user-suggestions">
        {(askUserMsg?.askUserSuggestions ?? []).join(",")}
      </span>
      <span data-testid="sending">{String(state.isSending)}</span>
    </div>
  );
}

function SendAnswerSpy({
  sessionId,
  answer,
}: {
  sessionId: string;
  answer: string;
}): React.ReactElement {
  const { sendAskUserAnswer, getSessionState } = useChatStateContext();
  const sentRef = useRef(false);

  useEffect(() => {
    if (sentRef.current) return;
    sentRef.current = true;
    void sendAskUserAnswer(sessionId, answer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const state = getSessionState(sessionId);

  return (
    <div>
      <span data-testid="sending">{String(state.isSending)}</span>
    </div>
  );
}

function renderWithProvider(node: React.ReactNode): ReturnType<typeof render> {
  const queryClient = makeQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <ChatStateProvider>{node}</ChatStateProvider>
    </QueryClientProvider>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ChatStateProvider AskUser flow", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("ask_user_required SSE event adds a role='ask_user' message to the session", async () => {
    vi.mocked(streamSession).mockResolvedValue(
      makeStream([makeAskUserRequired("s1"), makeAwaitingInput("s1")]),
    );

    const { getByTestId } = renderWithProvider(<SendMessageSpy sessionId="s1" />);

    await waitFor(
      () => {
        expect(getByTestId("has-ask-user").textContent).toBe("true");
      },
      { timeout: 3000 },
    );

    expect(getByTestId("ask-user-question").textContent).toBe("Which inventory scope?");
    expect(getByTestId("ask-user-suggestions").textContent).toBe(
      "All inventory,Low stock only,Overstock only",
    );
  });

  it("sendAskUserAnswer calls postAskUserAnswer with the correct payload", async () => {
    vi.mocked(streamSession).mockResolvedValue(
      makeStream([makeDone("s2", "Analyzing low stock...")]),
    );

    renderWithProvider(<SendAnswerSpy sessionId="s2" answer="Low stock only" />);

    await waitFor(
      () => {
        expect(vi.mocked(postAskUserAnswer)).toHaveBeenCalledWith("s2", "Low stock only");
      },
      { timeout: 3000 },
    );
  });

  it("sendAskUserAnswer sets isSending=false after the done event", async () => {
    vi.mocked(streamSession).mockResolvedValue(makeStream([makeDone("s3", "Done")]));

    const { getByTestId } = renderWithProvider(
      <SendAnswerSpy sessionId="s3" answer="answer" />,
    );

    await waitFor(
      () => {
        expect(vi.mocked(postAskUserAnswer)).toHaveBeenCalled();
        expect(getByTestId("sending").textContent).toBe("false");
      },
      { timeout: 3000 },
    );
  });
});
