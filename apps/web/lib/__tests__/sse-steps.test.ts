/**
 * T-127: Unit tests for eventsToSteps() in lib/sse-steps.ts.
 *
 * eventsToSteps() is a pure function — no I/O, no React, no mocks needed.
 * All SseEvent objects are constructed to satisfy the discriminated union.
 */

import { describe, it, expect } from "vitest";
import type { SseEvent } from "@/types/chat";
import { eventsToSteps } from "@/lib/sse-steps";

// ---------------------------------------------------------------------------
// Minimal event factories — satisfy the SseEvent discriminated union exactly
// ---------------------------------------------------------------------------

function makeQueryReceived(timestamp = "2024-01-01T00:00:00.000Z"): SseEvent {
  return { type: "query_received", session_id: "sess-1", timestamp };
}

function makeIntentClassified(
  category: string,
  confidence: number,
  timestamp = "2024-01-01T00:00:01.000Z",
): SseEvent {
  return {
    type: "intent_classified",
    category,
    confidence,
    rationale: "test rationale",
    timestamp,
  };
}

function makeExecutionModeSelected(
  mode: string,
  agents: string[],
  timestamp = "2024-01-01T00:00:02.000Z",
): SseEvent {
  return {
    type: "execution_mode_selected",
    mode,
    agents,
    requires_planning: false,
    requires_dag: false,
    rationale: "test rationale",
    timestamp,
  };
}

function makeAgentStarted(
  agentName: string,
  startedAt = "2024-01-01T00:00:03.000Z",
): SseEvent {
  return {
    type: "agent_started",
    agent_name: agentName,
    agent_role: "analyst",
    task_id: `task-${agentName}`,
    started_at: startedAt,
  };
}

function makeAgentCompleted(
  agentName: string,
  durationMs: number,
  timestamp = "2024-01-01T00:00:04.000Z",
): SseEvent {
  return {
    type: "agent_completed",
    agent_name: agentName,
    agent_role: "analyst",
    task_id: `task-${agentName}`,
    duration_ms: durationMs,
    timestamp,
  };
}

function makeToolStarted(toolName: string, toolCallId: string): SseEvent {
  return {
    type: "tool_started",
    tool_name: toolName,
    tool_call_id: toolCallId,
    agent_role: "analyst",
    timestamp: "2024-01-01T00:00:05.000Z",
  };
}

function makeToolCompleted(
  toolName: string,
  toolCallId: string,
  status: "success" | "error",
): SseEvent {
  return {
    type: "tool_completed",
    tool_name: toolName,
    tool_call_id: toolCallId,
    agent_role: "analyst",
    duration_ms: 120,
    status,
    timestamp: "2024-01-01T00:00:06.000Z",
  };
}

function makeResponseReady(timestamp = "2024-01-01T00:00:07.000Z"): SseEvent {
  return {
    type: "response_ready",
    mode: "sequential",
    timestamp,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("eventsToSteps", () => {
  // T-127 scenario 1: empty array → empty steps
  it("returns an empty array when given no events", () => {
    expect(eventsToSteps([])).toEqual([]);
  });

  // T-127 scenario 2: intent_classified → one completed step with correct label and subtext
  it("produces a 'Classifying intent' step with correct subtext from intent_classified", () => {
    const events: SseEvent[] = [makeIntentClassified("inventory_optimization", 0.92)];
    const steps = eventsToSteps(events);

    expect(steps).toHaveLength(1);
    expect(steps[0].id).toBe("intent");
    expect(steps[0].label).toBe("Classifying intent");
    expect(steps[0].status).toBe("completed");
    // 0.92 * 100 rounds to 92
    expect(steps[0].subtext).toBe("inventory_optimization · 92% confidence");
  });

  // T-127 scenario 3: execution_mode_selected → step with mode and agent count subtext
  it("produces a 'Planning analysis route' step with mode and agent count from execution_mode_selected", () => {
    const events: SseEvent[] = [
      makeExecutionModeSelected("parallel", ["AgentA", "AgentB", "AgentC"]),
    ];
    const steps = eventsToSteps(events);

    expect(steps).toHaveLength(1);
    expect(steps[0].id).toBe("route");
    expect(steps[0].label).toBe("Planning analysis route");
    expect(steps[0].status).toBe("completed");
    expect(steps[0].subtext).toBe("parallel · 3 agents");
  });

  it("uses singular 'agent' when exactly one agent is listed in execution_mode_selected", () => {
    const events: SseEvent[] = [makeExecutionModeSelected("sequential", ["AgentA"])];
    const steps = eventsToSteps(events);

    expect(steps[0].subtext).toBe("sequential · 1 agent");
  });

  // T-127 scenario 4: agent_started then agent_completed → step transitions running → completed with duration
  it("creates a running step on agent_started and marks it completed on agent_completed (< 1s)", () => {
    const events: SseEvent[] = [
      makeAgentStarted("InventoryAgent"),
      makeAgentCompleted("InventoryAgent", 450),
    ];
    const steps = eventsToSteps(events);

    expect(steps).toHaveLength(1);
    expect(steps[0].id).toBe("agent:InventoryAgent");
    expect(steps[0].label).toBe("Running Agent: InventoryAgent");
    expect(steps[0].status).toBe("completed");
    expect(steps[0].duration).toBe("450ms");
  });

  it("formats duration as seconds when agent_completed duration_ms >= 1000", () => {
    const events: SseEvent[] = [
      makeAgentStarted("SlowAgent"),
      makeAgentCompleted("SlowAgent", 2500),
    ];
    const steps = eventsToSteps(events);

    expect(steps[0].duration).toBe("2.5s");
  });

  // T-127 scenario 5: tool_started + tool_completed (success) → step completes
  it("creates a running tool step on tool_started and marks it completed on tool_completed success", () => {
    const events: SseEvent[] = [
      makeToolStarted("sql_query", "tc-001"),
      makeToolCompleted("sql_query", "tc-001", "success"),
    ];
    const steps = eventsToSteps(events);

    expect(steps).toHaveLength(1);
    expect(steps[0].id).toBe("tool:tc-001");
    expect(steps[0].label).toBe("Loading inventory data");
    expect(steps[0].status).toBe("completed");
  });

  // T-127 scenario 6: tool_completed with status "error" → step status is "failed"
  it("marks the tool step as 'failed' when tool_completed has status error", () => {
    const events: SseEvent[] = [
      makeToolStarted("sql_query", "tc-002"),
      makeToolCompleted("sql_query", "tc-002", "error"),
    ];
    const steps = eventsToSteps(events);

    expect(steps).toHaveLength(1);
    expect(steps[0].status).toBe("failed");
  });

  it("produces a 'failed' orphan tool step when tool_completed error arrives without tool_started", () => {
    const events: SseEvent[] = [makeToolCompleted("sql_query", "tc-999", "error")];
    const steps = eventsToSteps(events);

    expect(steps).toHaveLength(1);
    expect(steps[0].status).toBe("failed");
    expect(steps[0].label).toBe("Data retrieval failed");
  });

  // T-127 scenario 7: response_ready → step "Generating recommended actions" added
  it("adds a 'Generating recommended actions' step on response_ready", () => {
    const events: SseEvent[] = [makeResponseReady()];
    const steps = eventsToSteps(events);

    expect(steps).toHaveLength(1);
    expect(steps[0].id).toBe("response");
    expect(steps[0].label).toBe("Generating recommended actions");
    expect(steps[0].status).toBe("completed");
  });

  // T-127 scenario 8: duplicate events → deduplication; only one step per type
  it("deduplicates intent_classified when the same event type appears twice", () => {
    const events: SseEvent[] = [
      makeIntentClassified("optimization", 0.8),
      makeIntentClassified("forecasting", 0.95),
    ];
    const steps = eventsToSteps(events);

    // Only one intent step should exist — the second duplicate is ignored
    const intentSteps = steps.filter((s) => s.id === "intent");
    expect(intentSteps).toHaveLength(1);
    expect(intentSteps[0].subtext).toBe("optimization · 80% confidence");
  });

  it("deduplicates execution_mode_selected when emitted twice", () => {
    const events: SseEvent[] = [
      makeExecutionModeSelected("sequential", ["A"]),
      makeExecutionModeSelected("parallel", ["A", "B"]),
    ];
    const steps = eventsToSteps(events);

    const routeSteps = steps.filter((s) => s.id === "route");
    expect(routeSteps).toHaveLength(1);
    expect(routeSteps[0].subtext).toBe("sequential · 1 agent");
  });

  it("deduplicates response_ready when emitted twice", () => {
    const events: SseEvent[] = [makeResponseReady(), makeResponseReady("2024-01-01T00:01:00.000Z")];
    const steps = eventsToSteps(events);

    const responseSteps = steps.filter((s) => s.id === "response");
    expect(responseSteps).toHaveLength(1);
  });

  // Full pipeline: all major events produce correct ordered steps
  it("produces correct ordered steps for a full intent→route→agent→tool→response pipeline", () => {
    const events: SseEvent[] = [
      makeQueryReceived(),
      makeIntentClassified("optimization", 0.9),
      makeExecutionModeSelected("sequential", ["AgentA"]),
      makeAgentStarted("AgentA"),
      makeToolStarted("sql_query", "tc-1"),
      makeToolCompleted("sql_query", "tc-1", "success"),
      makeAgentCompleted("AgentA", 800),
      makeResponseReady(),
    ];
    const steps = eventsToSteps(events);

    // query_received produces no step; tool step is between agent steps
    // Order: intent, route, agent:AgentA, tool:tc-1, response
    expect(steps.length).toBe(5);
    expect(steps[0].id).toBe("intent");
    expect(steps[1].id).toBe("route");
    expect(steps[2].id).toBe("agent:AgentA");
    expect(steps[2].status).toBe("completed");
    expect(steps[3].id).toBe("tool:tc-1");
    expect(steps[3].status).toBe("completed");
    expect(steps[4].id).toBe("response");
    expect(steps[4].label).toBe("Generating recommended actions");
  });
});
