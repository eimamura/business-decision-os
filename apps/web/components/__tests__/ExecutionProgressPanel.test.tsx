/**
 * T-108: Render tests for ExecutionProgressPanel component.
 *
 * Strategy: vi.mock the useAgentProgress hook at the module level so we can
 * control its return value without needing to set up ChatStateContext or
 * any API dependencies.
 *
 * Scenarios:
 * 1. nodes=[], isRunning=false → returns null (panel not in DOM)
 * 2. nodes=[running agent], isRunning=true → panel visible, one AgentNodeCard
 * 3. nodes=[2 completed agents], isRunning=false → summary visible, "2 agents"
 * 4. Clicking summary toggle → expanded card list becomes visible
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import type { AgentNodeState } from "@/types/chat";

// ---------------------------------------------------------------------------
// Mock useAgentProgress before importing the component under test
// ---------------------------------------------------------------------------

const mockUseAgentProgress = vi.fn();

vi.mock("@/hooks/useAgentProgress", () => ({
  useAgentProgress: (sessionId: string) => mockUseAgentProgress(sessionId),
}));

// Import component *after* the mock is in place
const { ExecutionProgressPanel } = await import("@/components/ExecutionProgressPanel");

// ---------------------------------------------------------------------------
// Fixture builders
// ---------------------------------------------------------------------------

function makeNode(
  overrides: Partial<AgentNodeState> & { taskId: string },
): AgentNodeState {
  return {
    agentName: "Test Agent",
    agentRole: "analyst",
    status: "running",
    startedAt: "2024-01-01T00:00:00.000Z",
    toolCalls: [],
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

const SESSION_ID = "sess-panel-test";

describe("ExecutionProgressPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // T-108 scenario 1: empty + not running → null render
  it("renders nothing when nodes is empty and isRunning is false", () => {
    mockUseAgentProgress.mockReturnValue({
      nodes: [],
      isRunning: false,
      executionMode: undefined,
    });

    const { container } = render(<ExecutionProgressPanel sessionId={SESSION_ID} />);

    expect(container.firstChild).toBeNull();
    expect(screen.queryByTestId("execution-progress-panel")).not.toBeInTheDocument();
  });

  // T-108 scenario 2: one running agent → panel visible, one card
  it("renders the panel and one AgentNodeCard when one agent is running", () => {
    const node = makeNode({ taskId: "task-1", status: "running" });
    mockUseAgentProgress.mockReturnValue({
      nodes: [node],
      isRunning: true,
      executionMode: "sequential",
    });

    render(<ExecutionProgressPanel sessionId={SESSION_ID} />);

    expect(screen.getByTestId("execution-progress-panel")).toBeInTheDocument();
    expect(screen.getAllByTestId("agent-node-card")).toHaveLength(1);
  });

  // T-108 scenario 2 extra: panel is not null even when nodes is empty but isRunning=true
  it("renders the panel when isRunning is true even if nodes list is empty", () => {
    mockUseAgentProgress.mockReturnValue({
      nodes: [],
      isRunning: true,
      executionMode: undefined,
    });

    render(<ExecutionProgressPanel sessionId={SESSION_ID} />);

    expect(screen.getByTestId("execution-progress-panel")).toBeInTheDocument();
  });

  // T-108 scenario 3: 2 completed agents → summary visible with "2 agents"
  it("renders the summary element showing '2 agents completed' when two agents have completed", () => {
    const nodeA = makeNode({ taskId: "task-1", status: "completed", durationMs: 300 });
    const nodeB = makeNode({ taskId: "task-2", status: "completed", durationMs: 400 });
    mockUseAgentProgress.mockReturnValue({
      nodes: [nodeA, nodeB],
      isRunning: false,
      executionMode: undefined,
    });

    render(<ExecutionProgressPanel sessionId={SESSION_ID} />);

    expect(screen.getByTestId("execution-progress-panel-summary")).toBeInTheDocument();
    expect(screen.getByTestId("execution-progress-panel-summary")).toHaveTextContent("2 agents");
  });

  // T-108 scenario 3: completed agents do not show cards before toggle
  it("does not show agent cards before the summary is expanded", () => {
    const nodeA = makeNode({ taskId: "task-1", status: "completed", durationMs: 300 });
    const nodeB = makeNode({ taskId: "task-2", status: "completed", durationMs: 400 });
    mockUseAgentProgress.mockReturnValue({
      nodes: [nodeA, nodeB],
      isRunning: false,
      executionMode: undefined,
    });

    render(<ExecutionProgressPanel sessionId={SESSION_ID} />);

    // Cards are inside the collapsible section — not rendered until expanded
    expect(screen.queryByTestId("agent-node-card")).not.toBeInTheDocument();
  });

  // T-108 scenario 4: clicking summary toggle expands card list
  it("shows agent cards after clicking the summary toggle button", () => {
    const nodeA = makeNode({ taskId: "task-1", status: "completed", durationMs: 300 });
    const nodeB = makeNode({ taskId: "task-2", status: "completed", durationMs: 400 });
    mockUseAgentProgress.mockReturnValue({
      nodes: [nodeA, nodeB],
      isRunning: false,
      executionMode: undefined,
    });

    render(<ExecutionProgressPanel sessionId={SESSION_ID} />);

    // Click the summary toggle button (the button inside execution-progress-panel-summary)
    const summary = screen.getByTestId("execution-progress-panel-summary");
    const toggleButton = summary.querySelector("button");
    expect(toggleButton).not.toBeNull();
    fireEvent.click(toggleButton!);

    // Both cards should now be visible
    expect(screen.getAllByTestId("agent-node-card")).toHaveLength(2);
  });

  // Additional: single completed agent shows singular "agent" text
  it("shows '1 agent completed' (singular) when exactly one agent completed", () => {
    const node = makeNode({ taskId: "task-1", status: "completed", durationMs: 150 });
    mockUseAgentProgress.mockReturnValue({
      nodes: [node],
      isRunning: false,
      executionMode: undefined,
    });

    render(<ExecutionProgressPanel sessionId={SESSION_ID} />);

    expect(screen.getByTestId("execution-progress-panel-summary")).toHaveTextContent(
      "1 agent completed",
    );
  });
});
