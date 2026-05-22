"use client";

import { useEffect, useRef, useState } from "react";
import { fetchSessionEvents } from "@/lib/api";
import { SseEventSchema } from "@/types/chat";
import type { SessionUsage, SseEvent } from "@/types/chat";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ---- Helpers ----

function parseSseEvent(data: string): SseEvent | null {
  try {
    const parsed: unknown = JSON.parse(data);
    const result = SseEventSchema.safeParse(parsed);
    return result.success ? result.data : null;
  } catch {
    return null;
  }
}

function formatBRT(iso: string): string {
  try {
    return new Intl.DateTimeFormat("pt-BR", {
      timeZone: "America/Sao_Paulo",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function fmsDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

// ---- Event rendering ----

interface EventRowProps {
  ev: SseEvent;
  index: number;
}

function EventRow({ ev }: EventRowProps) {
  const ts = "timestamp" in ev && typeof ev.timestamp === "string" ? ev.timestamp : "";

  switch (ev.type) {
    case "query_received":
      return (
        <Row ts={ts} badge="QUERY" badgeColor="text-gray-400 bg-gray-800">
          received
        </Row>
      );

    case "intent_classified":
      return (
        <Row ts={ts} badge="INTENT" badgeColor="text-gray-400 bg-gray-800">
          <span className="text-gray-300">{ev.category}</span>
          <span className="text-gray-400"> · {(ev.confidence * 100).toFixed(0)}%</span>
          {ev.rationale && (
            <span className="text-gray-400 ml-1">— {ev.rationale}</span>
          )}
        </Row>
      );

    case "execution_mode_selected":
      return (
        <Row ts={ts} badge="ROUTE" badgeColor="text-gray-400 bg-gray-800">
          <span className="text-indigo-300">{ev.mode}</span>
          {ev.agents.length > 0 && (
            <span className="text-gray-500"> → {ev.agents.join(" → ")}</span>
          )}
        </Row>
      );

    case "plan_created":
      return (
        <Row ts={ts} badge="PLAN" badgeColor="text-gray-400 bg-gray-800">
          <span className="text-gray-300">{ev.mode}</span>
          {ev.steps && (
            <span className="text-gray-400"> · {ev.steps.length} steps</span>
          )}
          {ev.nodes && (
            <span className="text-gray-400"> · {ev.nodes.length} nodes</span>
          )}
        </Row>
      );

    case "agent_started":
      return (
        <Row ts={ev.started_at} badge="AGENT" badgeColor="text-indigo-300 bg-indigo-950">
          <span className="text-gray-200">{ev.agent_name}</span>
          {ev.input_summary && (
            <span className="text-gray-400 ml-1">— {ev.input_summary}</span>
          )}
        </Row>
      );

    case "agent_completed":
      return (
        <Row ts={ts} badge="AGENT" badgeColor="text-indigo-300 bg-indigo-950">
          <span className="text-emerald-400">✓</span>
          <span className="text-gray-200 ml-1">{ev.agent_name}</span>
          <span className="text-gray-400 ml-1">{fmsDuration(ev.duration_ms)}</span>
          {ev.output_summary && (
            <span className="text-gray-400 ml-1">— {ev.output_summary}</span>
          )}
        </Row>
      );

    case "tool_started":
      return (
        <Row ts={ts} badge="TOOL" badgeColor="text-yellow-400 bg-yellow-950">
          <span className="text-yellow-300">{ev.tool_name}</span>
          <span className="text-gray-400 ml-1">↗ {ev.agent_role}</span>
        </Row>
      );

    case "tool_completed":
      return (
        <Row ts={ts} badge="TOOL" badgeColor="text-yellow-400 bg-yellow-950">
          {ev.status === "error" ? (
            <span className="text-red-400">✗</span>
          ) : (
            <span className="text-emerald-400">✓</span>
          )}
          <span className="text-yellow-300 ml-1">{ev.tool_name}</span>
          <span className="text-gray-400 ml-1">{fmsDuration(ev.duration_ms)}</span>
          {ev.executed_query && (
            <span className="text-emerald-400/70 ml-1 truncate max-w-[180px]">
              {ev.executed_query.replace(/\s+/g, " ").slice(0, 60)}…
            </span>
          )}
          {ev.error && (
            <span className="text-red-400 ml-1">{ev.error}</span>
          )}
        </Row>
      );

    case "response_ready":
      return (
        <Row ts={ts} badge="RESPONSE" badgeColor="text-emerald-400 bg-emerald-950">
          <span className="text-gray-300">{ev.mode}</span>
          {ev.risk_level && (
            <RiskBadge level={ev.risk_level} />
          )}
          {ev.requires_approval && (
            <span className="text-amber-400 ml-1 text-[10px] uppercase">approval required</span>
          )}
        </Row>
      );

    case "approval_requested":
      return (
        <Row ts={ts} badge="APPROVAL" badgeColor="text-amber-400 bg-amber-950">
          <RiskBadge level={ev.risk_level} />
          <span className="text-gray-500 ml-1">expires {formatBRT(ev.expires_at)}</span>
        </Row>
      );

    case "auto_executed":
      return (
        <Row ts={ts} badge="AUTO" badgeColor="text-emerald-400 bg-emerald-950">
          <span className="text-emerald-300">executed</span>
        </Row>
      );

    case "error":
      return (
        <Row ts={ts} badge="ERROR" badgeColor="text-red-400 bg-red-950">
          <span className="text-red-300">{ev.message}</span>
        </Row>
      );

    default:
      return null;
  }
}

function Row({
  ts,
  badge,
  badgeColor,
  children,
}: {
  ts: string;
  badge: string;
  badgeColor: string;
  children: React.ReactNode;
}): React.ReactElement {
  return (
    <div className="flex items-baseline gap-2 py-0.5 leading-snug">
      <span className="shrink-0 text-gray-500 text-xs tabular-nums w-[52px]">
        {ts ? formatBRT(ts) : ""}
      </span>
      <span
        className={`shrink-0 text-[10px] font-bold uppercase px-1.5 py-0.5 rounded ${badgeColor} w-[72px] text-center`}
      >
        {badge}
      </span>
      <span className="text-xs text-gray-400 min-w-0 flex items-baseline gap-1 flex-wrap">
        {children}
      </span>
    </div>
  );
}

function RiskBadge({ level }: { level: string }): React.ReactElement {
  const colors: Record<string, string> = {
    low: "text-emerald-400",
    medium: "text-amber-400",
    high: "text-red-400",
  };
  return (
    <span className={`ml-1 text-[10px] font-bold uppercase ${colors[level] ?? "text-gray-400"}`}>
      {level}
    </span>
  );
}

// ---- Props ----

interface Props {
  sessionId: string;
  usage: SessionUsage;
}

// ---- Main component ----

function eventKey(ev: SseEvent): string {
  const ts = "timestamp" in ev && typeof (ev as { timestamp?: string }).timestamp === "string"
    ? (ev as { timestamp: string }).timestamp
    : "";
  return `${ev.type}:${ts}`;
}

export default function EventLog({ sessionId, usage }: Props): React.ReactElement {
  const [events, setEvents] = useState<SseEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const lastEventIdRef = useRef<string>("");
  const esRef = useRef<EventSource | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const seenKeysRef = useRef<Set<string>>(new Set());

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

    fetchSessionEvents(sessionId).then((historical) => {
      const filtered = historical.filter((ev) => ev.type !== "done");
      filtered.forEach((ev) => seenKeysRef.current.add(eventKey(ev)));
      setEvents(filtered);
    }).catch(() => undefined);

    return () => {
      esRef.current?.close();
    };
  }, [sessionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  return (
    <div className="flex flex-col h-full bg-gray-950 text-gray-100 font-mono text-xs">
      {/* Header */}
      <div className="px-4 py-2.5 border-b border-gray-800 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <span
            className={`w-1.5 h-1.5 rounded-full ${connected ? "bg-emerald-400" : "bg-red-500"}`}
          />
          <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest">
            Event Log
          </span>
        </div>
        <span className="text-[10px] text-gray-500">{events.length} events</span>
      </div>

      {/* Log body */}
      <div className="flex-1 overflow-y-auto px-3 py-2">
        {events.length === 0 && (
          <p className="text-[11px] text-gray-400 text-center py-10">
            Waiting for events…
          </p>
        )}
        {events.map((ev, i) => (
          <EventRow key={i} ev={ev} index={i} />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Footer: token usage */}
      <div className="border-t border-gray-800 px-4 py-2.5 shrink-0">
        <div className="flex items-center justify-between text-[10px] text-gray-500">
          <span>{usage.inputTokens.toLocaleString()} in</span>
          <span className="text-gray-500">|</span>
          <span>{usage.outputTokens.toLocaleString()} out</span>
          <span className="text-gray-500">|</span>
          <span className="text-emerald-600">${usage.costUsd.toFixed(4)}</span>
        </div>
      </div>
    </div>
  );
}
