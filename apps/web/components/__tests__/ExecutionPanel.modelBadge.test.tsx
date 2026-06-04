/**
 * Vitest tests for T-171: ExecutionPanel model badge rendering.
 *
 * Verifies that the model-name badge (data-testid="model-name-badge") is
 * rendered for orchestrator and agent nodes when meta.model_name is a string,
 * and is NOT rendered for tool nodes.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import type { GraphRunNode } from "@/types/workspace";
import type { SessionUsage } from "@/types/chat";

// ---------------------------------------------------------------------------
// Mock useChatStateContext — same pattern as ExecutionPanel.test.tsx
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

const ExecutionPanel = (await import("@/components/agent/ExecutionPanel")).default;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const DEFAULT_USAGE: SessionUsage = { inputTokens: 0, outputTokens: 0, costUsd: 0 };

function makeSessionState(graphRun: GraphRunNode[]) {
  return {
    messages: [],
    isSending: false,
    usage: DEFAULT_USAGE,
    isLoadingMessages: false,
    graphRun,
    agentNodes: [],
    executionMode: undefined,
    sessionStartedAt: null,
    sessionEndedAt: null,
  };
}

function makeNode(
  kind: GraphRunNode["kind"],
  meta?: Record<string, unknown>,
): GraphRunNode {
  return {
    runId: `run-${kind}-${Math.random().toString(36).slice(2)}`,
    kind,
    name: "test_node",
    status: "completed",
    startedAt: "2024-01-01T00:00:00.000Z",
    completedAt: "2024-01-01T00:00:01.000Z",
    durationMs: 1000,
    meta,
  };
}

const SESSION_ID = "sess-badge-test";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ExecutionPanel — model-name badge", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Element.prototype.scrollIntoView = vi.fn();
  });

  it("renders model badge for orchestrator node with model_name in meta", () => {
    const graphRun: GraphRunNode[] = [
      makeNode("orchestrator", { model_name: "claude-haiku-4-5-20251001" }),
    ];
    mockGetSessionState.mockReturnValue(makeSessionState(graphRun));

    render(<ExecutionPanel sessionId={SESSION_ID} />);

    const badge = screen.getByTestId("model-name-badge");
    expect(badge).toBeInTheDocument();
    expect(badge.textContent).toBe("claude-haiku-4-5-20251001");
  });

  it("renders model badge for agent node with model_name in meta", () => {
    const graphRun: GraphRunNode[] = [
      makeNode("agent", { model_name: "claude-sonnet-4-6" }),
    ];
    mockGetSessionState.mockReturnValue(makeSessionState(graphRun));

    render(<ExecutionPanel sessionId={SESSION_ID} />);

    const badge = screen.getByTestId("model-name-badge");
    expect(badge).toBeInTheDocument();
    expect(badge.textContent).toBe("claude-sonnet-4-6");
  });

  it("does not render model badge for tool node even when meta.model_name is set", () => {
    const graphRun: GraphRunNode[] = [
      makeNode("tool", { model_name: "claude-sonnet-4-6" }),
    ];
    mockGetSessionState.mockReturnValue(makeSessionState(graphRun));

    render(<ExecutionPanel sessionId={SESSION_ID} />);

    expect(screen.queryByTestId("model-name-badge")).not.toBeInTheDocument();
  });
});
