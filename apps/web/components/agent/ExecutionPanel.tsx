"use client";

import { useEffect, useRef, useState } from "react";
import { useChatStateContext } from "@/app/chat/ChatStateContext";
import type { GraphNodeKind, GraphNodeStatus, GraphRunNode } from "@/types/workspace";
import EvidenceSources from "./EvidenceSources";

// ---- Label map ----

const GRAPH_NODE_LABELS: Record<string, string> = {
  classify_intent: "Classifying intent",
  prepare_ask_user: "Preparing clarification",
  wait_for_answer: "Waiting for answer",
  select_mode: "Planning analysis route",
  run_direct_chat: "Generating response",
  run_sequential: "Running agents",
  run_planned: "Executing plan",
  run_dag: "Executing analysis graph",
  sql_query: "Loading inventory data",
  nl_query: "Loading inventory data",
  forecast: "Checking demand forecast",
  simulate_inventory: "Running inventory simulation",
  optimize_replenishment: "Optimizing replenishment plan",
  evaluate_candidates: "Evaluating action candidates",
  write_audit_log: "Writing audit log",
};

function nodeLabel(node: GraphRunNode): string {
  const base = GRAPH_NODE_LABELS[node.name] ?? node.name.replace(/_/g, " ");
  return node.kind === "agent" ? `Agent: ${base}` : base;
}

function kindIndent(kind: GraphNodeKind): string {
  if (kind === "tool") return "pl-5";
  if (kind === "agent") return "pl-2.5";
  return "";
}

// ---- Step icon ----

function StepIcon({ status }: { status: GraphNodeStatus }): React.ReactElement {
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
          <span className="inline-block w-3 h-3 rounded-full border-2 border-indigo-400/30 border-t-indigo-400 animate-spin" />
        </span>
      );
  }
}

// ---- Props ----

interface Props {
  sessionId: string;
}

type ActiveTab = "evidence" | "notes";

// ---- Main component ----

export default function ExecutionPanel({ sessionId }: Props): React.ReactElement {
  const { getSessionState } = useChatStateContext();
  const { graphRun, sessionStartedAt, sessionEndedAt, isSending, usage } =
    getSessionState(sessionId);

  const [activeTab, setActiveTab] = useState<ActiveTab>("evidence");
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [graphRun]);

  return (
    <div className="flex flex-col h-full bg-[#0B1020] text-gray-100 text-xs">
      {/* Header */}
      <div className="px-4 py-3 border-b border-white/8 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-semibold text-white/70 uppercase tracking-wider">
            Execution Trace
          </span>
        </div>
        {isSending && (
          <span className="flex items-center gap-1.5 text-[10px] font-semibold text-emerald-400 uppercase tracking-wider">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            Live
          </span>
        )}
      </div>

      <div className="px-4 pt-3 pb-1 shrink-0">
        {graphRun.length === 0 ? (
          <div className="py-4 text-center">
            <p className="text-[11px] text-white/35">No active analysis yet.</p>
          </div>
        ) : null}
      </div>

      <div className="flex-1 overflow-y-auto px-4 pb-3 min-h-0">
        {graphRun.length > 0 && (
          <div>
            {sessionStartedAt && (
              <div className="flex items-center gap-1.5 mb-3 text-[10px] text-white/30">
                <span className="w-1 h-1 rounded-full bg-white/20 shrink-0" />
                Started{" "}
                {new Date(sessionStartedAt).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                  second: "2-digit",
                })}
              </div>
            )}
            {graphRun.map((node, idx) => (
              <div
                key={node.runId}
                className={`relative flex items-start gap-2.5 pb-3 ${kindIndent(node.kind)}`}
              >
                {idx < graphRun.length - 1 && (
                  <div
                    className="absolute left-[9px] top-[22px] w-px bg-white/10"
                    style={{ height: "calc(100% - 14px)" }}
                  />
                )}
                <StepIcon status={node.status} />
                <div className="flex-1 min-w-0 pt-0.5">
                  <span
                    className={`text-[11px] leading-snug ${
                      node.status === "completed"
                        ? "text-white/60"
                        : node.status === "running"
                        ? "text-white/90 font-medium"
                        : "text-red-400"
                    }`}
                  >
                    {nodeLabel(node)}
                  </span>
                  {node.kind === "orchestrator" &&
                    typeof node.meta?.category === "string" && (
                      <span className="block text-[10px] text-white/40 mt-0.5 leading-relaxed truncate">
                        {node.meta.category}
                        {typeof node.meta.confidence === "number"
                          ? ` · ${Math.round((node.meta.confidence as number) * 100)}% confidence`
                          : ""}
                      </span>
                    )}
                  {node.kind === "orchestrator" &&
                    typeof node.meta?.mode === "string" && (
                      <span className="block text-[10px] text-white/40 mt-0.5 leading-relaxed truncate">
                        {node.meta.mode}
                        {Array.isArray(node.meta.agents) && node.meta.agents.length > 0
                          ? ` · ${node.meta.agents.length} agent${node.meta.agents.length !== 1 ? "s" : ""}`
                          : ""}
                      </span>
                    )}
                  {(node.kind === "orchestrator" || node.kind === "agent") &&
                    typeof node.meta?.model_name === "string" && (
                      <span className="block mt-0.5">
                        <span
                          className="inline-block px-1 py-0 text-[10px] font-mono text-indigo-300/50 bg-indigo-500/10 border border-indigo-500/20 rounded"
                          data-testid="model-name-badge"
                        >
                          {node.meta.model_name as string}
                        </span>
                      </span>
                    )}
                  {node.durationMs != null && node.status !== "running" && (
                    <span className="block text-[10px] text-white/25 mt-0.5">
                      Completed ·{" "}
                      {node.durationMs < 1000
                        ? `${node.durationMs}ms`
                        : `${(node.durationMs / 1000).toFixed(1)}s`}
                    </span>
                  )}
                  {node.tokenCost && (
                    <span className="block text-[10px] text-white/25 mt-0.5 font-mono">
                      {node.tokenCost.inputTokens.toLocaleString()} in ·{" "}
                      {node.tokenCost.outputTokens.toLocaleString()} out ·{" "}
                      <span className="text-emerald-600/60">
                        ${node.tokenCost.costUsd.toFixed(4)}
                      </span>
                    </span>
                  )}
                </div>
              </div>
            ))}
            {sessionEndedAt && (
              <div className="flex items-center gap-1.5 mt-1 text-[10px] text-white/30">
                <span className="w-1 h-1 rounded-full bg-emerald-400/50 shrink-0" />
                Completed{" "}
                {new Date(sessionEndedAt).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                  second: "2-digit",
                })}
                {sessionStartedAt &&
                  (() => {
                    const diffMs =
                      new Date(sessionEndedAt).getTime() -
                      new Date(sessionStartedAt).getTime();
                    return diffMs > 0 ? ` · ${(diffMs / 1000).toFixed(1)}s total` : null;
                  })()}
              </div>
            )}
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
            <EvidenceSources graphRun={graphRun} />
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
