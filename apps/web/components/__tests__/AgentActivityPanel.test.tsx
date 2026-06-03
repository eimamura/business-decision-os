/**
 * Render tests for AgentActivityPanel component.
 *
 * AgentActivityPanel reads graphRun, sessionStartedAt, sessionEndedAt,
 * isSending, and usage from ChatStateContext.
 *
 * Strategy: vi.mock useChatStateContext to inject controlled state without
 * rendering ChatStateProvider.
 *
 * Scenarios:
 * 1. 2 completed orchestrator nodes → both node labels appear in the document
 * 2. Empty graphRun → "No active analysis yet." is shown
 * 3. getSessionState called with the correct sessionId
 * 4. "Live" badge shown when isSending is true
 * 5. "Live" badge NOT shown when isSending is false
 * 6. Orchestrator node meta (category + confidence) rendered as subtext
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import type { GraphRunNode } from "@/types/workspace";
import type { SessionUsage } from "@/types/chat";

// ---------------------------------------------------------------------------
// Mock useChatStateContext
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

const AgentActivityPanel = (await import("@/components/agent/AgentActivityPanel")).default;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const DEFAULT_USAGE: SessionUsage = { inputTokens: 0, outputTokens: 0, costUsd: 0 };

function makeSessionState(
  graphRun: GraphRunNode[],
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
    graphRun,
    agentNodes: [],
    executionMode: undefined,
    sessionStartedAt: extra?.sessionStartedAt ?? null,
    sessionEndedAt: extra?.sessionEndedAt ?? null,
  };
}

function makeCompletedOrchestratorNode(
  name: string,
  runId: string,
  meta?: Record<string, unknown>,
): GraphRunNode {
  return {
    runId,
    kind: "orchestrator",
    name,
    status: "completed",
    startedAt: "2024-01-01T00:00:00.000Z",
    completedAt: "2024-01-01T00:00:01.000Z",
    durationMs: 1000,
    meta,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

const SESSION_ID = "sess-panel-test";

describe("AgentActivityPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Element.prototype.scrollIntoView = vi.fn();
  });

  it("renders both node labels when graphRun has 2 completed orchestrator nodes", () => {
    const graphRun: GraphRunNode[] = [
      makeCompletedOrchestratorNode("classify_intent", "run-1"),
      makeCompletedOrchestratorNode("select_mode", "run-2"),
    ];
    mockGetSessionState.mockReturnValue(makeSessionState(graphRun));

    render(<AgentActivityPanel sessionId={SESSION_ID} />);

    expect(screen.getByText("Classifying intent")).toBeInTheDocument();
    expect(screen.getByText("Planning analysis route")).toBeInTheDocument();
  });

  it("shows 'No active analysis yet.' when graphRun is empty", () => {
    mockGetSessionState.mockReturnValue(makeSessionState([]));

    render(<AgentActivityPanel sessionId={SESSION_ID} />);

    expect(screen.getByText("No active analysis yet.")).toBeInTheDocument();
  });

  it("calls getSessionState with the provided sessionId", () => {
    mockGetSessionState.mockReturnValue(makeSessionState([]));

    render(<AgentActivityPanel sessionId="my-session-id" />);

    expect(mockGetSessionState).toHaveBeenCalledWith("my-session-id");
  });

  it("shows the 'Live' badge when isSending is true", () => {
    mockGetSessionState.mockReturnValue(makeSessionState([], { isSending: true }));

    render(<AgentActivityPanel sessionId={SESSION_ID} />);

    expect(screen.getByText("Live")).toBeInTheDocument();
  });

  it("does not show the 'Live' badge when isSending is false", () => {
    mockGetSessionState.mockReturnValue(makeSessionState([], { isSending: false }));

    render(<AgentActivityPanel sessionId={SESSION_ID} />);

    expect(screen.queryByText("Live")).not.toBeInTheDocument();
  });

  it("renders orchestrator node meta (category + confidence) as subtext", () => {
    const graphRun: GraphRunNode[] = [
      makeCompletedOrchestratorNode("classify_intent", "run-1", {
        category: "optimization",
        confidence: 0.9,
      }),
    ];
    mockGetSessionState.mockReturnValue(makeSessionState(graphRun));

    render(<AgentActivityPanel sessionId={SESSION_ID} />);

    expect(screen.getByText("optimization · 90% confidence")).toBeInTheDocument();
  });

  it("renders the 'Agent Activity' header", () => {
    mockGetSessionState.mockReturnValue(makeSessionState([]));

    render(<AgentActivityPanel sessionId={SESSION_ID} />);

    expect(screen.getByText("Agent Activity")).toBeInTheDocument();
  });
});
