"use client";

import { useEffect, useRef, useState } from "react";
import type { SessionUsage } from "@/types/chat";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ---- Types ----

interface RawEvent {
  type: string;
  [key: string]: unknown;
}

interface ToolTrace {
  toolName: string;
  toolCallId: string;
  input?: unknown;
  output?: unknown;
  executedQuery?: string;
  startedAt: string;
  durationMs?: number;
  status: "running" | "completed" | "error";
  error?: string;
}

interface SpecialistTrace {
  name: string;
  role: string;
  taskId?: string;
  stepId?: string;
  startedAt: string;
  durationMs?: number;
  status: "running" | "completed" | "failed";
  tools: ToolTrace[];
  outputSummary?: string;
  isAgent: boolean; // true = product agent, false = prompt-based execution role
  inputSummary?: string;
}

interface OrchestratorTrace {
  startedAt: string;
  route: string[];
  rationale: string;
  specialists: SpecialistTrace[];
  recommendation?: {
    riskLevel: string;
    requiresApproval: boolean;
    autoExecute: boolean;
  };
  durationMs?: number;
}

// ---- BRT formatting ----

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

// ---- Role labels ----

const ROLE_LABELS: Record<string, string> = {
  orchestrator: "Orchestrator",
  demand: "Demand",
  data_engineer: "Data Engineer",
  simulation_optimizer: "Simulation Optimizer",
  evaluator: "Evaluator",
  inventory: "Inventory",
  replenishment: "Replenishment",
  procurement: "Procurement",
  supplier: "Supplier",
  production: "Production",
  logistics: "Logistics",
  anomaly_detector: "Anomaly Detector",
};

const RISK_COLORS: Record<string, string> = {
  low: "text-emerald-400 bg-emerald-400/10",
  medium: "text-amber-400 bg-amber-400/10",
  high: "text-red-400 bg-red-400/10",
};

// ---- Props ----

interface Props {
  sessionId: string;
  usage: SessionUsage;
}

// ---- Main component ----

export default function ReasoningPanel({ sessionId, usage }: Props) {
  const [orchestrator, setOrchestrator] = useState<OrchestratorTrace | null>(null);
  const [connected, setConnected] = useState(false);
  const [sessionStartedAt, setSessionStartedAt] = useState<string | null>(null);
  const lastEventIdRef = useRef<string>("");
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    setOrchestrator(null);
    setSessionStartedAt(null);

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
          const ev: RawEvent = JSON.parse(e.data as string);
          if (ev.type === "error" && ev.code === "no_stream") return;
          handleEvent(ev);
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
  }, [sessionId]); // eslint-disable-line react-hooks/exhaustive-deps

  function handleEvent(ev: RawEvent) {
    switch (ev.type) {
      case "query_received": {
        const startedAt = (ev.timestamp as string) ?? new Date().toISOString();
        setSessionStartedAt(startedAt);
        setOrchestrator({
          startedAt,
          route: [],
          rationale: "",
          specialists: [],
        });
        break;
      }

      case "execution_mode_selected": {
        const route = ev.agents as string[];
        const rationale = ev.rationale as string;
        setOrchestrator((prev) =>
          prev ? { ...prev, route, rationale } : prev
        );
        break;
      }

      case "agent_started": {
        const name = ev.agent_name as string;
        const role = ev.agent_role as string;
        const taskId = ev.task_id as string;
        const startedAt = ev.started_at as string;
        setOrchestrator((prev) => {
          if (!prev) return prev;
          const exists = prev.specialists.some((s) => s.taskId === taskId);
          if (exists) return prev;
          return {
            ...prev,
            specialists: [
              ...prev.specialists,
              {
                name,
                role,
                taskId,
                startedAt,
                status: "running",
                tools: [],
                isAgent: true,
                inputSummary: ev.input_summary as string | undefined,
              },
            ],
          };
        });
        break;
      }

      case "agent_completed": {
        const taskId = ev.task_id as string;
        const durationMs = ev.duration_ms as number | undefined;
        const outputSummary = ev.output_summary as string | undefined;
        setOrchestrator((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            specialists: prev.specialists.map((s) =>
              s.taskId === taskId
                ? { ...s, status: "completed", durationMs, outputSummary }
                : s
            ),
          };
        });
        break;
      }

      case "tool_started": {
        const toolName = ev.tool_name as string;
        const toolCallId = ev.tool_call_id as string;
        const agentRole = ev.agent_role as string;
        const input = ev.input as unknown;
        const timestamp = ev.timestamp as string;

        setOrchestrator((prev) => {
          if (!prev) return prev;
          const specialists = prev.specialists.map((s) => {
            if (s.role !== agentRole) return s;
            return {
              ...s,
              tools: [
                ...s.tools,
                {
                  toolName,
                  toolCallId,
                  input,
                  startedAt: timestamp,
                  status: "running" as const,
                },
              ],
            };
          });
          return { ...prev, specialists };
        });
        break;
      }

      case "tool_completed": {
        const toolCallId = ev.tool_call_id as string;
        const output = ev.output as unknown;
        const executedQuery = ev.executed_query as string | undefined;
        const durationMs = ev.duration_ms as number | undefined;
        const toolStatus = (ev.status as string) === "error" ? "error" : "completed";
        const toolError = ev.error as string | undefined;

        setOrchestrator((prev) => {
          if (!prev) return prev;
          const specialists = prev.specialists.map((s) => ({
            ...s,
            tools: s.tools.map((t) =>
              t.toolCallId === toolCallId
                ? {
                    ...t,
                    output,
                    executedQuery,
                    durationMs,
                    status: toolStatus as "completed" | "error",
                    error: toolError,
                  }
                : t
            ),
          }));
          return { ...prev, specialists };
        });
        break;
      }

      case "response_ready": {
        setOrchestrator((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            recommendation: {
              riskLevel: (ev.risk_level as string) ?? "low",
              requiresApproval: Boolean(ev.requires_approval),
              autoExecute: !ev.requires_approval,
            },
          };
        });
        break;
      }
    }
  }

  return (
    <div className="flex flex-col h-full bg-gray-950 text-gray-100 font-mono text-xs">
      {/* Header */}
      <div className="px-4 py-2.5 border-b border-gray-800 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <span
            className={`w-1.5 h-1.5 rounded-full ${connected ? "bg-emerald-400" : "bg-red-500"}`}
          />
          <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest">
            Agent Trace
          </span>
        </div>
        {sessionStartedAt && (
          <span className="text-[10px] text-gray-600">
            {formatBRT(sessionStartedAt)} BRT
          </span>
        )}
      </div>

      {/* Trace body */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-2">
        {!orchestrator && (
          <p className="text-[11px] text-gray-600 text-center py-10">
            Waiting for agent activity...
          </p>
        )}

        {orchestrator && (
          <OrchestratorNode trace={orchestrator} />
        )}
      </div>

      {/* Footer: token usage */}
      <div className="border-t border-gray-800 px-4 py-2.5 shrink-0">
        <div className="flex items-center justify-between text-[10px] text-gray-500">
          <span>{usage.inputTokens.toLocaleString()} in</span>
          <span className="text-gray-700">|</span>
          <span>{usage.outputTokens.toLocaleString()} out</span>
          <span className="text-gray-700">|</span>
          <span className="text-emerald-600">${usage.costUsd.toFixed(4)}</span>
        </div>
      </div>
    </div>
  );
}

// ---- Orchestrator node ----

function OrchestratorNode({ trace }: { trace: OrchestratorTrace }) {
  return (
    <div className="space-y-1.5">
      {/* Orchestrator header */}
      <div className="flex items-start gap-2 text-indigo-400">
        <span className="shrink-0 mt-0.5">⬡</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <span className="font-bold text-[11px] text-indigo-300 uppercase tracking-wider">
              Orchestrator
            </span>
            <span className="text-gray-600 text-[10px] shrink-0">
              {formatBRT(trace.startedAt)} BRT
            </span>
          </div>
          {trace.route.length > 0 && (
            <div className="mt-1 space-y-0.5">
              <div className="text-gray-400">
                Route:{" "}
                <span className="text-indigo-300">
                  {trace.route.join(" → ")}
                </span>
              </div>
              {trace.rationale && (
                <div className="text-gray-600 leading-relaxed">
                  {trace.rationale}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Specialist list */}
      {trace.specialists.length > 0 && (
        <div className="ml-4 border-l border-gray-800 pl-3 space-y-1">
          {trace.specialists.map((s, i) => (
            <SpecialistNode key={s.taskId ?? s.stepId ?? i} specialist={s} />
          ))}
        </div>
      )}

      {/* Recommendation */}
      {trace.recommendation && (
        <div className="ml-4 border-l border-gray-800 pl-3">
          <RecommendationRow rec={trace.recommendation} />
        </div>
      )}
    </div>
  );
}

// ---- Specialist node ----

function SpecialistNode({ specialist: s }: { specialist: SpecialistTrace }) {
  const [expanded, setExpanded] = useState(false);
  const hasSub = s.tools.length > 0 || !!s.outputSummary;
  const isRunning = s.status === "running";
  const isFailed = s.status === "failed";

  return (
    <div>
      <button
        onClick={() => hasSub && setExpanded((p) => !p)}
        className={`w-full text-left flex items-start gap-2 py-1 pr-1 rounded hover:bg-gray-900/60 transition-colors ${hasSub ? "cursor-pointer" : "cursor-default"}`}
      >
        <span className={`shrink-0 mt-0.5 ${isFailed ? "text-red-400" : isRunning ? "text-amber-400" : "text-emerald-400"}`}>
          {isFailed ? "✗" : isRunning ? "▶" : "✓"}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <span className={`font-semibold ${isFailed ? "text-red-300" : "text-gray-200"}`}>
              {s.name}
            </span>
            <div className="flex items-center gap-2 shrink-0">
              {isRunning && (
                <span className="text-amber-400/80 text-[10px]">running…</span>
              )}
              {s.durationMs != null && !isRunning && (
                <span className="text-gray-600 text-[10px]">
                  {fmsDuration(s.durationMs)}
                </span>
              )}
              {s.startedAt && (
                <span className="text-gray-700 text-[10px]">
                  {formatBRT(s.startedAt)}
                </span>
              )}
            </div>
          </div>
          {s.tools.length > 0 && !expanded && (
            <div className="text-gray-600 text-[10px]">
              {s.tools.length} tool call{s.tools.length > 1 ? "s" : ""}
              {" · "}
              {[...new Set(s.tools.map((t) => t.toolName))].join(", ")}
            </div>
          )}
        </div>
      </button>

      {expanded && (
        <div className="ml-5 border-l border-gray-800/60 pl-2.5 mt-0.5 space-y-0.5">
          {s.tools.map((t, i) => (
            <ToolRow key={t.toolCallId ?? i} tool={t} />
          ))}
          {s.outputSummary && (
            <div className="py-1 text-gray-500 text-[10px] leading-relaxed">
              ↳ {s.outputSummary}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---- Tool row ----

function ToolRow({ tool: t }: { tool: ToolTrace }) {
  const [expanded, setExpanded] = useState(false);
  const hasDetail = !!(t.input != null || t.output != null || t.executedQuery || t.error);
  const isRunning = t.status === "running";

  return (
    <div>
      <button
        onClick={() => hasDetail && setExpanded((p) => !p)}
        className={`w-full text-left flex items-center gap-2 py-0.5 rounded hover:bg-gray-900/40 ${hasDetail ? "cursor-pointer" : "cursor-default"}`}
      >
        <span className={`shrink-0 text-[10px] ${isRunning ? "text-amber-500" : "text-gray-500"}`}>
          ⚙
        </span>
        <span className="text-yellow-500/90 flex-1">{t.toolName}</span>
        {t.durationMs != null && (
          <span className="text-gray-700 text-[10px] shrink-0">
            {fmsDuration(t.durationMs)}
          </span>
        )}
        <span className="text-gray-700 text-[10px] shrink-0">
          {formatBRT(t.startedAt)}
        </span>
      </button>
      {expanded && hasDetail && (
        <div className="ml-4 mt-0.5 mb-1 space-y-1">
          {t.executedQuery && (
            <pre className="text-emerald-400/80 text-[10px] whitespace-pre-wrap break-all bg-gray-900 rounded px-2 py-1 max-h-32 overflow-y-auto">
              {t.executedQuery}
            </pre>
          )}
          {t.input != null && (
            <pre className="text-blue-400/80 text-[10px] whitespace-pre-wrap break-all bg-gray-900 rounded px-2 py-1 max-h-24 overflow-y-auto">
              {JSON.stringify(t.input, null, 2)}
            </pre>
          )}
          {t.output != null && (
            <pre className="text-gray-400 text-[10px] whitespace-pre-wrap break-all bg-gray-900 rounded px-2 py-1 max-h-24 overflow-y-auto">
              {JSON.stringify(t.output, null, 2)}
            </pre>
          )}
          {t.error && (
            <pre className="text-red-400 text-[10px] whitespace-pre-wrap bg-gray-900 rounded px-2 py-1">
              {t.error}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

// ---- Recommendation row ----

function RecommendationRow({
  rec,
}: {
  rec: { riskLevel: string; requiresApproval: boolean; autoExecute: boolean };
}) {
  const colorClass = RISK_COLORS[rec.riskLevel] ?? "text-gray-400 bg-gray-400/10";
  return (
    <div className="flex items-center gap-2 py-1">
      <span className="text-amber-400 shrink-0">★</span>
      <span className="text-gray-300">Recommendation ready</span>
      <span
        className={`text-[9px] font-bold uppercase px-1.5 py-0.5 rounded ${colorClass}`}
      >
        {rec.riskLevel}
      </span>
      {rec.autoExecute && (
        <span className="text-[9px] text-emerald-500 uppercase">auto-executed</span>
      )}
      {rec.requiresApproval && !rec.autoExecute && (
        <span className="text-[9px] text-amber-500 uppercase">awaiting approval</span>
      )}
    </div>
  );
}
