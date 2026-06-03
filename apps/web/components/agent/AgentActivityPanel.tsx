"use client";

import { useEffect, useRef, useState } from "react";
import { useChatStateContext } from "@/app/chat/ChatStateContext";
import type { AgentStepStatus } from "@/types/workspace";
import EvidenceSources from "./EvidenceSources";

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
}

type ActiveTab = "evidence" | "notes";

// ---- Main component ----

export default function AgentActivityPanel({ sessionId }: Props): React.ReactElement {
  const { getSessionState } = useChatStateContext();
  const { processingSteps, sessionStartedAt, sessionEndedAt, isSending, usage } =
    getSessionState(sessionId);

  const [activeTab, setActiveTab] = useState<ActiveTab>("evidence");
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [processingSteps]);

  return (
    <div className="flex flex-col h-full bg-[#0B1020] text-gray-100 text-xs">
      {/* Header */}
      <div className="px-4 py-3 border-b border-white/8 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-semibold text-white/70 uppercase tracking-wider">
            Agent Activity
          </span>
        </div>
        {isSending && (
          <span className="flex items-center gap-1.5 text-[10px] font-semibold text-emerald-400 uppercase tracking-wider">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            Live
          </span>
        )}
      </div>

      {/* Processing Steps */}
      <div className="px-4 pt-3 pb-1 shrink-0">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-white/30 mb-2.5">
          Processing steps
        </p>
        {processingSteps.length === 0 ? (
          <div className="py-4 text-center">
            <p className="text-[11px] text-white/35">No active analysis yet.</p>
          </div>
        ) : null}
      </div>

      <div className="flex-1 overflow-y-auto px-4 pb-3 min-h-0">
        {processingSteps.length > 0 && (
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
            {processingSteps.map((step, idx) => (
              <div key={step.id} className="relative flex items-start gap-2.5 pb-3">
                {idx < processingSteps.length - 1 && (
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
                  {step.subtext && (
                    <span className="block text-[10px] text-white/40 mt-0.5 leading-relaxed truncate">
                      {step.subtext}
                    </span>
                  )}
                  {step.duration && (
                    <span className="block text-[10px] text-white/25 mt-0.5">
                      Completed · {step.duration}
                    </span>
                  )}
                  {step.tokenCost && (
                    <span className="block text-[10px] text-white/25 mt-0.5 font-mono">
                      {step.tokenCost.inputTokens.toLocaleString()} in ·{" "}
                      {step.tokenCost.outputTokens.toLocaleString()} out ·{" "}
                      <span className="text-emerald-600/60">
                        ${step.tokenCost.costUsd.toFixed(4)}
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
            <EvidenceSources steps={processingSteps} />
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
