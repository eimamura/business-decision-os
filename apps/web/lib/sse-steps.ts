import type { SseEvent } from "@/types/chat";
import type { AgentStep, AgentStepStatus } from "@/types/workspace";

export function toolStepLabel(toolName: string): string {
  const MAP: Record<string, string> = {
    sql_query: "Loading inventory data",
    nl_query: "Loading inventory data",
    forecast: "Checking demand forecast",
    simulate_inventory: "Running inventory simulation",
    optimize_replenishment: "Optimizing replenishment plan",
    evaluate_candidates: "Evaluating action candidates",
    write_audit_log: "Writing audit log",
  };
  return MAP[toolName] ?? `Retrieving data: ${toolName}`;
}

export function eventsToSteps(events: SseEvent[]): AgentStep[] {
  const steps: AgentStep[] = [];
  const seen = new Set<string>();

  for (const ev of events) {
    switch (ev.type) {
      case "query_received":
        // Session start time is extracted separately; no step pushed here.
        break;

      case "intent_classified":
        if (!seen.has("intent")) {
          const evRec = ev as Record<string, unknown>;
          const category = typeof evRec.category === "string" ? evRec.category : "";
          const confidence = typeof evRec.confidence === "number" ? evRec.confidence : null;
          steps.push({
            id: "intent",
            label: "Classifying intent",
            status: "completed",
            subtext:
              category && confidence !== null
                ? `${category} · ${Math.round(confidence * 100)}% confidence`
                : category || undefined,
          });
          seen.add("intent");
        }
        break;

      case "execution_mode_selected":
        if (!seen.has("route")) {
          const evRec = ev as Record<string, unknown>;
          const mode = typeof evRec.mode === "string" ? evRec.mode : "";
          const agents = Array.isArray(evRec.agents) ? evRec.agents : [];
          const agentCount = agents.length;
          steps.push({
            id: "route",
            label: "Planning analysis route",
            status: "completed",
            subtext: mode
              ? `${mode}${agentCount > 0 ? ` · ${agentCount} agent${agentCount !== 1 ? "s" : ""}` : ""}`
              : undefined,
          });
          seen.add("route");
        }
        break;

      case "plan_created":
        if (!seen.has("plan")) {
          const evRec = ev as Record<string, unknown>;
          const planItems = Array.isArray(evRec.steps)
            ? (evRec.steps as Record<string, unknown>[])
            : Array.isArray(evRec.nodes)
            ? (evRec.nodes as Record<string, unknown>[])
            : [];
          const roleList = planItems
            .map((s) => String(s.agent_role ?? ""))
            .filter(Boolean)
            .join(", ");
          steps.push({
            id: "plan",
            label: "Building analysis plan",
            status: "completed",
            subtext:
              planItems.length > 0
                ? `${planItems.length} step${planItems.length !== 1 ? "s" : ""}${roleList ? `: ${roleList}` : ""}`
                : undefined,
          });
          seen.add("plan");
        }
        break;

      case "agent_started": {
        const stepId = `agent:${ev.agent_name}`;
        if (!seen.has(stepId)) {
          const evRec = ev as Record<string, unknown>;
          const inputSummary =
            typeof evRec.input_summary === "string" ? evRec.input_summary.slice(0, 80) : undefined;
          const startedAt =
            typeof evRec.started_at === "string" ? evRec.started_at : undefined;
          steps.push({
            id: stepId,
            label: `Running Agent: ${ev.agent_name}`,
            status: "running",
            startedAt,
            subtext: inputSummary,
          });
          seen.add(stepId);
        }
        break;
      }

      case "agent_completed": {
        const stepId = `agent:${ev.agent_name}`;
        const existing = steps.find((s) => s.id === stepId);
        const evRec = ev as Record<string, unknown>;
        const timestamp = typeof evRec.timestamp === "string" ? evRec.timestamp : undefined;
        if (existing) {
          existing.status = "completed";
          existing.completedAt = timestamp;
          if (ev.duration_ms) {
            existing.duration =
              ev.duration_ms < 1000
                ? `${ev.duration_ms}ms`
                : `${(ev.duration_ms / 1000).toFixed(1)}s`;
          }
          const inputTok = evRec.input_tokens;
          const outputTok = evRec.output_tokens;
          const costUsd = evRec.cost_usd;
          if (
            typeof inputTok === "number" &&
            typeof outputTok === "number" &&
            typeof costUsd === "number"
          ) {
            existing.tokenCost = { inputTokens: inputTok, outputTokens: outputTok, costUsd };
          }
        } else if (!seen.has(`done:${ev.agent_name}`)) {
          steps.push({
            id: `done:${ev.agent_name}`,
            label: `Running Agent: ${ev.agent_name}`,
            status: "completed",
            completedAt: timestamp,
            duration: ev.duration_ms
              ? ev.duration_ms < 1000
                ? `${ev.duration_ms}ms`
                : `${(ev.duration_ms / 1000).toFixed(1)}s`
              : undefined,
          });
          seen.add(`done:${ev.agent_name}`);
        }
        break;
      }

      case "tool_started": {
        const stepId = `tool:${ev.tool_call_id}`;
        if (!seen.has(stepId)) {
          steps.push({ id: stepId, label: toolStepLabel(ev.tool_name), status: "running" });
          seen.add(stepId);
        }
        break;
      }

      case "tool_completed": {
        const stepId = `tool:${ev.tool_call_id}`;
        const existing = steps.find((s) => s.id === stepId);
        const status: AgentStepStatus = ev.status === "error" ? "failed" : "completed";
        if (existing) {
          existing.status = status;
        } else if (!seen.has(`tdone:${ev.tool_call_id}`)) {
          steps.push({
            id: `tdone:${ev.tool_call_id}`,
            label:
              ev.status === "error"
                ? "Data retrieval failed"
                : `Data loaded: ${toolStepLabel(ev.tool_name)}`,
            status,
          });
          seen.add(`tdone:${ev.tool_call_id}`);
        }
        break;
      }

      case "response_ready":
        if (!seen.has("response")) {
          steps.push({ id: "response", label: "Generating recommended actions", status: "completed" });
          seen.add("response");
        }
        break;
    }
  }

  return steps;
}
