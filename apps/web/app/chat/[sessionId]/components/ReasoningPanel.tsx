"use client";

import { useEffect, useRef, useState } from "react";
import type { SessionUsage } from "@/types/chat";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface StepEvent {
  type: string;
  step_id?: string;
  specialist_role?: string;
  step_type?: string;
  started_at?: string;
  duration_ms?: number;
  output_preview?: string;
  tokens?: number;
  cost_usd?: number;
  tool_name?: string;
  tool_call_id?: string;
  input?: unknown;
  output?: unknown;
  executed_query?: string;
  status?: string;
  error?: string;
  code?: string;
  message?: string;
  recoverable?: boolean;
}

interface Props {
  sessionId: string;
  usage: SessionUsage;
}

const ROLE_LABELS: Record<string, string> = {
  domain_expert: "Domain Expert",
  data_engineer: "Data Engineer",
  sim_opt: "Sim/Opt",
  evaluator: "Evaluator",
};

export default function ReasoningPanel({ sessionId, usage }: Props) {
  const [events, setEvents] = useState<StepEvent[]>([]);
  const [activeRole, setActiveRole] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const lastEventIdRef = useRef<string>("");
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    function connect() {
      const url = new URL(`${API_BASE}/api/v1/sessions/${sessionId}/stream`);
      if (lastEventIdRef.current) {
        url.searchParams.set("last_event_id", lastEventIdRef.current);
      }

      const es = new EventSource(url.toString());
      esRef.current = es;

      es.onopen = () => setConnected(true);

      es.onmessage = (e: MessageEvent) => {
        if (e.lastEventId) lastEventIdRef.current = e.lastEventId;
        try {
          const data: StepEvent = JSON.parse(e.data as string);
          setEvents((prev) => [...prev, data]);
          if (data.type === "step_started" && data.specialist_role) {
            setActiveRole(data.specialist_role);
          }
          if (data.type === "step_completed") {
            setActiveRole(null);
          }
        } catch {
          // ignore parse errors
        }
      };

      es.onerror = () => {
        setConnected(false);
        es.close();
        setTimeout(connect, 3000);
      };
    }

    connect();

    return () => {
      esRef.current?.close();
    };
  }, [sessionId]);

  return (
    <div className="flex flex-col h-full bg-gray-900 text-gray-100">
      <div className="px-4 py-3 border-b border-gray-700 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className={`w-2 h-2 rounded-full ${connected ? "bg-green-400" : "bg-red-400"}`}
          />
          <span className="text-xs font-semibold text-gray-300 uppercase tracking-wide">
            Reasoning Panel
          </span>
        </div>
      </div>

      {activeRole && (
        <div className="px-4 py-2 bg-blue-900/40 border-b border-blue-700/50">
          <p className="text-xs text-blue-300 font-medium">
            Active: {ROLE_LABELS[activeRole] ?? activeRole}
          </p>
        </div>
      )}

      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-2">
        {events.length === 0 && (
          <p className="text-xs text-gray-500 text-center py-8">
            Waiting for agent activity...
          </p>
        )}
        {events.map((ev, i) => (
          <EventRow key={i} event={ev} />
        ))}
      </div>

      <div className="border-t border-gray-700 px-4 py-3">
        <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">
          Token Usage
        </p>
        <div className="space-y-1 text-xs">
          <div className="flex justify-between text-gray-300">
            <span>Input</span>
            <span>{usage.inputTokens.toLocaleString()}</span>
          </div>
          <div className="flex justify-between text-gray-300">
            <span>Output</span>
            <span>{usage.outputTokens.toLocaleString()}</span>
          </div>
          <div className="flex justify-between text-gray-500">
            <span>Est. cost</span>
            <span>${usage.costUsd.toFixed(4)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function EventRow({ event }: { event: StepEvent }) {
  const [expanded, setExpanded] = useState(false);

  const icon = EVENT_ICON[event.type] ?? "○";
  const label = EVENT_LABEL[event.type] ?? event.type;
  const hasDetail =
    event.input != null ||
    event.output != null ||
    event.executed_query != null ||
    event.error != null;

  return (
    <div className="text-xs">
      <button
        className="w-full text-left flex items-start gap-2 hover:bg-gray-800 px-2 py-1.5 rounded"
        onClick={() => hasDetail && setExpanded((p) => !p)}
      >
        <span className="text-gray-500 shrink-0 mt-0.5">{icon}</span>
        <span className="flex-1 text-gray-300">
          {label}
          {event.specialist_role && (
            <span className="ml-1 text-gray-500">
              [{ROLE_LABELS[event.specialist_role] ?? event.specialist_role}]
            </span>
          )}
          {event.tool_name && (
            <span className="ml-1 text-yellow-400">{event.tool_name}</span>
          )}
          {event.duration_ms != null && (
            <span className="ml-1 text-gray-600">{event.duration_ms}ms</span>
          )}
        </span>
        {event.cost_usd != null && (
          <span className="text-green-400 shrink-0">
            ${event.cost_usd.toFixed(4)}
          </span>
        )}
      </button>
      {expanded && hasDetail && (
        <div className="ml-6 mt-1 bg-gray-800 rounded p-2 space-y-2">
          {event.executed_query && (
            <pre className="text-green-300 text-xs whitespace-pre-wrap overflow-x-auto">
              {event.executed_query}
            </pre>
          )}
          {event.input != null && (
            <pre className="text-blue-300 text-xs whitespace-pre-wrap overflow-x-auto">
              {JSON.stringify(event.input, null, 2)}
            </pre>
          )}
          {event.output != null && (
            <pre className="text-gray-300 text-xs whitespace-pre-wrap overflow-x-auto">
              {JSON.stringify(event.output, null, 2)}
            </pre>
          )}
          {event.error && (
            <pre className="text-red-400 text-xs whitespace-pre-wrap">{event.error}</pre>
          )}
        </div>
      )}
    </div>
  );
}

const EVENT_ICON: Record<string, string> = {
  step_started: "▶",
  step_completed: "✓",
  tool_called: "⚙",
  tool_completed: "✓",
  recommendation_ready: "★",
  awaiting_approval: "⏸",
  error: "✗",
};

const EVENT_LABEL: Record<string, string> = {
  step_started: "Step started",
  step_completed: "Step completed",
  tool_called: "Tool called",
  tool_completed: "Tool completed",
  recommendation_ready: "Recommendation ready",
  awaiting_approval: "Awaiting approval",
  error: "Error",
};
