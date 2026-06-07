/**
 * T-106: Unit tests for useAgentProgress hook.
 *
 * Strategy: renderHook with a wrapper that injects a mock ChatStateContext
 * value, so we can control exactly what getSessionState returns without
 * rendering the full ChatStateProvider (which depends on @tanstack/react-query
 * and real API modules).
 */

import { describe, it, expect } from "vitest";
import { renderHook } from "@testing-library/react";
import React from "react";
import type { AgentNodeState } from "@/types/chat";

// ---------------------------------------------------------------------------
// Inline mock context — avoids touching production modules
// ---------------------------------------------------------------------------

// We need the real context object so we can provide a value for it.
// Import it lazily after the vi.mock for any deps has been set up.
// ChatStateContext itself has no problematic deps, so we import directly.
import { useChatStateContext } from "@/app/chat/ChatStateContext";
import { vi } from "vitest";

// Stub out the entire ChatStateContext module so we can inject our own value.
vi.mock("@/app/chat/ChatStateContext", () => {
  const React = require("react");
  // eslint-disable-next-line @typescript-eslint/no-unsafe-member-access, @typescript-eslint/no-unsafe-call
  const Context = (React.createContext as (v: unknown) => unknown)(null);
  return {
    // useChatStateContext will be overridden per-test by controlling the context
    // value via the wrapper; here we just expose a hook that reads from context.
    useChatStateContext: () => {
      const ctx = React.useContext(Context);
      if (ctx === null) throw new Error("no context");
      return ctx;
    },
    _TestContext: Context,
  };
});

// Pull the hidden test context out of the mock.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const { _TestContext } = (await import("@/app/chat/ChatStateContext")) as any;

// Import the hook under test *after* the mock is established.
const { useAgentProgress } = await import("@/hooks/useAgentProgress");

// ---------------------------------------------------------------------------
// Helper to build a wrapper component that provides a mock context value
// ---------------------------------------------------------------------------

type MockSessionState = {
  agentNodes: AgentNodeState[];
  executionMode?: string;
  isSending: boolean;
};

function makeWrapper(state: MockSessionState) {
  return function Wrapper({ children }: { children: React.ReactNode }): React.ReactElement {
    const value = {
      getSessionState: (_sessionId: string) => state,
    };
    return React.createElement(_TestContext.Provider, { value }, children);
  };
}

// ---------------------------------------------------------------------------
// Fixture builders
// ---------------------------------------------------------------------------

function runningNode(overrides: Partial<AgentNodeState> = {}): AgentNodeState {
  return {
    taskId: "agent-a:2024-01-01T00:00:00.000Z",
    agentName: "Agent A",
    agentRole: "analyst",
    status: "running",
    startedAt: "2024-01-01T00:00:00.000Z",
    toolCalls: [],
    ...overrides,
  };
}

function completedNode(overrides: Partial<AgentNodeState> = {}): AgentNodeState {
  return {
    taskId: "agent-b:2024-01-01T00:00:00.000Z",
    agentName: "Agent B",
    agentRole: "reporter",
    status: "completed",
    startedAt: "2024-01-01T00:00:00.000Z",
    durationMs: 450,
    toolCalls: [],
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

const SESSION_ID = "sess-test";

describe("useAgentProgress", () => {
  // T-106 scenario 1: empty state, not sending
  it("returns empty nodes and isRunning=false when agentNodes is empty and isSending is false", () => {
    const { result } = renderHook(() => useAgentProgress(SESSION_ID), {
      wrapper: makeWrapper({ agentNodes: [], isSending: false }),
    });

    expect(result.current.nodes).toEqual([]);
    expect(result.current.isRunning).toBe(false);
    expect(result.current.executionMode).toBeUndefined();
  });

  // T-106 scenario 2: one running agent
  it("returns isRunning=true and the running node when isSending is true", () => {
    const node = runningNode();
    const { result } = renderHook(() => useAgentProgress(SESSION_ID), {
      wrapper: makeWrapper({ agentNodes: [node], isSending: true }),
    });

    expect(result.current.isRunning).toBe(true);
    expect(result.current.nodes).toHaveLength(1);
    expect(result.current.nodes[0].status).toBe("running");
  });

  // T-106 scenario 3: one completed agent
  it("returns isRunning=false and the completed node when isSending is false", () => {
    const node = completedNode();
    const { result } = renderHook(() => useAgentProgress(SESSION_ID), {
      wrapper: makeWrapper({ agentNodes: [node], isSending: false }),
    });

    expect(result.current.isRunning).toBe(false);
    expect(result.current.nodes).toHaveLength(1);
    expect(result.current.nodes[0].status).toBe("completed");
    expect(result.current.nodes[0].durationMs).toBe(450);
  });

  // T-106 scenario 4: multiple agents with tool calls
  it("returns all nodes with their toolCalls when multiple agents are present", () => {
    const nodeA = runningNode({
      toolCalls: [
        {
          toolCallId: "tc-1",
          toolName: "nl_query",
          status: "completed",
          durationMs: 120,
        },
      ],
    });
    const nodeB = completedNode({
      toolCalls: [
        {
          toolCallId: "tc-2",
          toolName: "nl_query",
          status: "completed",
          durationMs: 80,
        },
        {
          toolCallId: "tc-3",
          toolName: "forecast",
          status: "running",
        },
      ],
    });

    const { result } = renderHook(() => useAgentProgress(SESSION_ID), {
      wrapper: makeWrapper({ agentNodes: [nodeA, nodeB], isSending: true }),
    });

    expect(result.current.nodes).toHaveLength(2);
    expect(result.current.nodes[0].toolCalls).toHaveLength(1);
    expect(result.current.nodes[1].toolCalls).toHaveLength(2);
  });

  // T-106 scenario 5: executionMode propagates from context
  it("propagates executionMode from context", () => {
    const { result } = renderHook(() => useAgentProgress(SESSION_ID), {
      wrapper: makeWrapper({
        agentNodes: [],
        executionMode: "sequential",
        isSending: true,
      }),
    });

    expect(result.current.executionMode).toBe("sequential");
  });
});
