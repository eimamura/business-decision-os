"use client";

import { useEffect, useRef, useState } from "react";
import { fetchSessionEvents } from "@/lib/api";
import { SseEventSchema } from "@/types/chat";
import type { SessionUsage, SseEvent } from "@/types/chat";
import type { AgentStep, AgentStepStatus } from "@/types/workspace";
import EvidenceSources from "./EvidenceSources";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ---- SSE parsing ----

function parseSseEvent(data: string): SseEvent | null {
  try {
    const parsed: unknown = JSON.parse(data);
    const result = SseEventSchema.safeParse(parsed);
    return result.success ? result.data : null;
  } catch {
    return null;
  }
}

function eventKey(ev: SseEvent): string {
  const ts =
    "timestamp" in ev && typeof (ev as { timestamp?: string }).timestamp === "string"
      ? (ev as { timestamp: string }).timestamp
      : "";
  return `${ev.type}:${ts}`;
}

// ---- Event → Step conversion ----

function eventsToSteps(events: SseEvent[]): AgentStep[] {
  const steps: AgentStep[] = [];
  const seen = new Set<string>();

  for (const ev of events) {
    switch (ev.type) {
      case "query_received":
        if (!seen.has("query")) {
          steps.push({ id: "query", label: "Understanding your question", status: "completed" });
          seen.add("query");
        }
        break;

      case "intent_classified":
        if (!seen.has("intent")) {
          steps.push({ id: "intent", label: "Classifying intent", status: "completed" });
          seen.add("intent");
        }
        break;

      case "execution_mode_selected":
        if (!seen.has("route")) {
          steps.push({ id: "route", label: "Planning analysis route", status: "completed" });
          seen.add("route");
        }
        break;

      case "plan_created":
        if (!seen.has("plan")) {
          steps.push({ id: "plan", label: "Building execution plan", status: "completed" });
          seen.add("plan");
        }
        break;

      case "agent_started": {
        const stepId = `agent:${ev.agent_name}`;
        if (!seen.has(stepId)) {
          steps.push({ id: stepId, label: `Analyzing with ${ev.agent_name}`, status: "running" });
          seen.add(stepId);
        }
        break;
      }

      case "agent_completed": {
        const stepId = `agent:${ev.agent_name}`;
        const existing = steps.find((s) => s.id === stepId);
        if (existing) {
          existing.status = "completed";
          if (ev.duration_ms) {
            existing.duration =
              ev.duration_ms < 1000 ? `${ev.duration_ms}ms` : `${(ev.duration_ms / 1000).toFixed(1)}s`;
          }
        } else if (!seen.has(`done:${ev.agent_name}`)) {
          steps.push({ id: `done:${ev.agent_name}`, label: `Analysis complete`, status: "completed" });
          seen.add(`done:${ev.agent_name}`);
        }
        break;
      }

      case "tool_started": {
        const stepId = `tool:${ev.tool_name}`;
        if (!seen.has(stepId)) {
          steps.push({ id: stepId, label: `Retrieving data: ${ev.tool_name}`, status: "running" });
          seen.add(stepId);
        }
        break;
      }

      case "tool_completed": {
        const stepId = `tool:${ev.tool_name}`;
        const existing = steps.find((s) => s.id === stepId);
        const status: AgentStepStatus = ev.status === "error" ? "failed" : "completed";
        if (existing) {
          existing.status = status;
        } else if (!seen.has(`tdone:${ev.tool_name}`)) {
          steps.push({
            id: `tdone:${ev.tool_name}`,
            label: ev.status === "error" ? "Data retrieval failed" : "Data retrieved",
            status,
          });
          seen.add(`tdone:${ev.tool_name}`);
        }
        break;
      }

      case "response_ready":
        if (!seen.has("response")) {
          steps.push({ id: "response", label: "Generating insights", status: "completed" });
          seen.add("response");
        }
        break;
    }
  }

  return steps;
}

// ---- Step icon ----

function StepIcon({ status }: { status: AgentStepStatus }): React.ReactElement {
  switch (status) {
    case "completed":
      return (
        <span className="shrink-0 w-5 h-5 rounded-full bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-400 text-[10px]">
          ✓
        </span>
      );
    case "failed":
      return (
        <span className="shrink-0 w-5 h-5 rounded-full bg-red-500/15 border border-red-500/30 flex items-center justify-center text-red-400 text-[10px]">
          ✗
        </span>
      );
    case "running":
      return (
        <span className="shrink-0 w-5 h-5 rounded-full bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center">
          <span className="inline-block w-2 h-2 rounded-full bg-indigo-400 animate-pulse" />
        </span>
      );
    default:
      return (
        <span className="shrink-0 w-5 h-5 rounded-full bg-white/5 border border-white/10 flex items-center justify-center text-white/20 text-[10px]">
          ○
        </span>
      );
  }
}

// ---- Props ----

interface Props {
  sessionId: string;
  usage: SessionUsage;
}

type ActiveTab = "evidence" | "notes";

// ---- Main component ----

export default function AgentActivityPanel({ sessionId, usage }: Props): React.ReactElement {
  const [events, setEvents] = useState<SseEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [activeTab, setActiveTab] = useState<ActiveTab>("evidence");
  const lastEventIdRef = useRef<string>("");
  const esRef = useRef<EventSource | null>(null);
  const seenKeysRef = useRef<Set<string>>(new Set());
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setEvents([]);
    seenKeysRef.current = new Set();

    function connect(): void {
      const url = new URL(`${API_BASE}/api/v1/sessions/${sessionId}/stream`);
      if (lastEventIdRef.current) {
        url.searchParams.set("last_event_id", lastEventIdRef.current);
      }

      const es = new EventSource(url.toString());
      esRef.current = es;

      es.onopen = () => setConnected(true);

      es.onmessage = (e: MessageEvent) => {
        if (e.lastEventId) lastEventIdRef.current = e.lastEventId;
        const ev = parseSseEvent(e.data as string);
        if (!ev) return;
        if (ev.type === "done") return;
        if (ev.type === "error" && (ev as { code?: string }).code === "no_stream") return;
        const key = eventKey(ev);
        if (seenKeysRef.current.has(key)) return;
        seenKeysRef.current.add(key);
        setEvents((prev) => [...prev, ev]);
      };

      es.onerror = () => {
        setConnected(false);
        es.close();
        setTimeout(connect, 3000);
      };
    }

    connect();

    fetchSessionEvents(sessionId)
      .then((historical) => {
        const filtered = historical.filter((ev) => ev.type !== "done");
        filtered.forEach((ev) => seenKeysRef.current.add(eventKey(ev)));
        setEvents(filtered);
      })
      .catch(() => undefined);

    return () => {
      esRef.current?.close();
    };
  }, [sessionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  const steps = eventsToSteps(events);

  return (
    <div className="flex flex-col h-full bg-[#0B1020] text-gray-100 text-xs">
      {/* Header */}
      <div className="px-4 py-3 border-b border-white/8 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-semibold text-white/70 uppercase tracking-wider">
            Agent Activity
          </span>
        </div>
        {connected && (
          <span className="flex items-center gap-1.5 text-[10px] font-semibold text-emerald-400 uppercase tracking-wider">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            Live
          </span>
        )}
        {!connected && (
          <span className="flex items-center gap-1.5 text-[10px] text-white/25">
            <span className="w-1.5 h-1.5 rounded-full bg-white/25" />
            Connecting
          </span>
        )}
      </div>

      {/* Processing Steps */}
      <div className="px-4 pt-3 pb-1 shrink-0">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-white/30 mb-2.5">
          Processing steps
        </p>
        {steps.length === 0 ? (
          <div className="py-4 text-center">
            <p className="text-[11px] text-white/35">No active analysis yet.</p>
          </div>
        ) : null}
      </div>

      <div className="flex-1 overflow-y-auto px-4 pb-3 min-h-0">
        {steps.length > 0 && (
          <div>
            {steps.map((step, idx) => (
              <div key={step.id} className="relative flex items-start gap-2.5 pb-3">
                {idx < steps.length - 1 && (
                  <div className="absolute left-[9px] top-[22px] w-px bg-white/10" style={{ height: "calc(100% - 14px)" }} />
                )}
                <StepIcon status={step.status} />
                <div className="flex-1 min-w-0 pt-0.5">
                  <span
                    className={`text-[11px] leading-snug ${
                      step.status === "completed"
                        ? "text-white/60"
                        : step.status === "running"
                        ? "text-white/90 font-medium"
                        : step.status === "failed"
                        ? "text-red-400"
                        : "text-white/25"
                    }`}
                  >
                    {step.label}
                  </span>
                  {step.duration && (
                    <span className="block text-[10px] text-white/25 mt-0.5">
                      Completed • {step.duration}
                    </span>
                  )}
                </div>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Evidence / Notes tabs */}
      <div className="border-t border-white/8 shrink-0">
        <div className="flex px-4 pt-2 gap-4">
          <button
            onClick={() => setActiveTab("evidence")}
            className={`text-[11px] font-semibold pb-2 border-b-2 transition-colors ${
              activeTab === "evidence"
                ? "border-indigo-400 text-white/80"
                : "border-transparent text-white/30 hover:text-white/50"
            }`}
          >
            Evidence / Data Sources
          </button>
          <button
            onClick={() => setActiveTab("notes")}
            className={`text-[11px] font-semibold pb-2 border-b-2 transition-colors ${
              activeTab === "notes"
                ? "border-indigo-400 text-white/80"
                : "border-transparent text-white/30 hover:text-white/50"
            }`}
          >
            Notes
          </button>
        </div>
        <div className="px-4 py-2">
          {activeTab === "evidence" ? (
            <EvidenceSources events={events} />
          ) : (
            <p className="text-[11px] text-white/25 py-2">No notes yet.</p>
          )}
        </div>
      </div>

      {/* Footer: token usage */}
      <div className="border-t border-white/8 px-4 py-2 shrink-0">
        <div className="flex items-center justify-between text-[10px] text-white/25">
          <span>{usage.inputTokens.toLocaleString()} in</span>
          <span>|</span>
          <span>{usage.outputTokens.toLocaleString()} out</span>
          <span>|</span>
          <span className="text-emerald-600/70">${usage.costUsd.toFixed(4)}</span>
        </div>
      </div>
    </div>
  );
}
