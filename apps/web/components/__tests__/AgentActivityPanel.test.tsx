/**
 * T-127: Render tests for AgentActivityPanel component.
 *
 * AgentActivityPanel is now a pure display component that reads processingSteps,
 * sessionStartedAt, sessionEndedAt, isSending, and usage from ChatStateContext.
 * It has no EventSource of its own.
 *
 * Strategy: vi.mock useChatStateContext so we can inject a controlled
 * ChatStateContextValue without rendering ChatStateProvider (which needs
 * @tanstack/react-query and real API modules).
 *
 * Scenarios:
 * 1. 2 completed processingSteps → both step labels appear in the document
 * 2. Empty processingSteps → "No active analysis yet." is shown
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import type { AgentStep } from "@/types/workspace";
import type { SessionUsage } from "@/types/chat";

// ---------------------------------------------------------------------------
// Mock useChatStateContext — must be set up before any component import
// ---------------------------------------------------------------------------

const mockGetSessionState = vi.fn();

vi.mock("@/app/chat/ChatStateContext", () => ({
  useChatStateContext: () => ({
    getSessionState: mockGetSessionState,
    loadMessages: vi.fn(),
    sendMessage: vi.fn(),
    submitFeedback: vi.fn(),
    appendAssistantReply: vi.fn(),
  }),
}));

// Import component *after* the mock is in place
const AgentActivityPanel = (await import("@/components/agent/AgentActivityPanel")).default;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const DEFAULT_USAGE: SessionUsage = { inputTokens: 0, outputTokens: 0, costUsd: 0 };

function makeSessionState(
  processingSteps: AgentStep[],
  extra?: {
    sessionStartedAt?: string | null;
    sessionEndedAt?: string | null;
    isSending?: boolean;
  },
) {
  return {
    messages: [],
    isSending: extra?.isSending ?? false,
    usage: DEFAULT_USAGE,
    isLoadingMessages: false,
    agentNodes: [],
    executionMode: undefined,
    processingSteps,
    sessionStartedAt: extra?.sessionStartedAt ?? null,
    sessionEndedAt: extra?.sessionEndedAt ?? null,
  };
}

function makeCompletedStep(id: string, label: string): AgentStep {
  return { id, label, status: "completed" };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

const SESSION_ID = "sess-panel-test";

describe("AgentActivityPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // jsdom does not implement scrollIntoView; mock it to prevent errors from
    // AgentActivityPanel's useEffect that calls bottomRef.current?.scrollIntoView
    Element.prototype.scrollIntoView = vi.fn();
  });

  // T-127 scenario 1: 2 completed processingSteps → both labels appear
  it("renders both step labels when processingSteps has 2 completed steps", () => {
    const steps: AgentStep[] = [
      makeCompletedStep("intent", "Classifying intent"),
      makeCompletedStep("route", "Planning analysis route"),
    ];
    mockGetSessionState.mockReturnValue(makeSessionState(steps));

    render(<AgentActivityPanel sessionId={SESSION_ID} />);

    expect(screen.getByText("Classifying intent")).toBeInTheDocument();
    expect(screen.getByText("Planning analysis route")).toBeInTheDocument();
  });

  // T-127 scenario 2: empty processingSteps → empty state message shown
  it("shows 'No active analysis yet.' when processingSteps is empty", () => {
    mockGetSessionState.mockReturnValue(makeSessionState([]));

    render(<AgentActivityPanel sessionId={SESSION_ID} />);

    expect(screen.getByText("No active analysis yet.")).toBeInTheDocument();
  });

  // Additional: getSessionState is called with the correct sessionId
  it("calls getSessionState with the provided sessionId", () => {
    mockGetSessionState.mockReturnValue(makeSessionState([]));

    render(<AgentActivityPanel sessionId="my-session-id" />);

    expect(mockGetSessionState).toHaveBeenCalledWith("my-session-id");
  });

  // Additional: "Live" badge shown when isSending is true
  it("shows the 'Live' badge when isSending is true", () => {
    mockGetSessionState.mockReturnValue(makeSessionState([], { isSending: true }));

    render(<AgentActivityPanel sessionId={SESSION_ID} />);

    expect(screen.getByText("Live")).toBeInTheDocument();
  });

  // Additional: "Live" badge NOT shown when isSending is false
  it("does not show the 'Live' badge when isSending is false", () => {
    mockGetSessionState.mockReturnValue(makeSessionState([], { isSending: false }));

    render(<AgentActivityPanel sessionId={SESSION_ID} />);

    expect(screen.queryByText("Live")).not.toBeInTheDocument();
  });

  // Additional: step subtext rendered when present
  it("renders step subtext when a step includes it", () => {
    const steps: AgentStep[] = [
      {
        id: "intent",
        label: "Classifying intent",
        status: "completed",
        subtext: "optimization · 90% confidence",
      },
    ];
    mockGetSessionState.mockReturnValue(makeSessionState(steps));

    render(<AgentActivityPanel sessionId={SESSION_ID} />);

    expect(screen.getByText("optimization · 90% confidence")).toBeInTheDocument();
  });

  // Additional: component renders "Agent Activity" header
  it("renders the 'Agent Activity' header", () => {
    mockGetSessionState.mockReturnValue(makeSessionState([]));

    render(<AgentActivityPanel sessionId={SESSION_ID} />);

    expect(screen.getByText("Agent Activity")).toBeInTheDocument();
  });
});
