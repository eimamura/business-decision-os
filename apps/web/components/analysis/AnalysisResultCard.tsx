"use client";

import type { InventoryShortageAnalysis } from "@/types/analysis";
import RiskSummaryCards from "@/components/analysis/RiskSummaryCards";
import RiskBreakdownSection from "@/components/analysis/RiskBreakdownSection";
import RecommendedActionsPanel from "@/components/analysis/RecommendedActionsPanel";
import ConfidencePanel from "@/components/analysis/ConfidencePanel";
import DataUsedPanel from "@/components/analysis/DataUsedPanel";

interface AnalysisResultCardProps {
  analysis: InventoryShortageAnalysis;
  isStreaming?: boolean;
  isError?: boolean;
  createdAt?: string;
}

function SectionHeading({ children }: { children: React.ReactNode }): React.ReactElement {
  return (
    <h3 className="text-[10px] font-bold uppercase tracking-widest text-white/35 mb-3 flex items-center gap-1.5">
      {children}
    </h3>
  );
}

export default function AnalysisResultCard({
  analysis,
  isStreaming = false,
  isError = false,
  createdAt,
}: AnalysisResultCardProps): React.ReactElement {
  const status = isStreaming ? "running" : isError ? "failed" : "completed";

  return (
    <div className="rounded-2xl border border-indigo-500/20 bg-[rgba(15,23,42,0.78)] overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-white/8 bg-white/3">
        <span className="text-sm font-semibold text-white/90 truncate">{analysis.title}</span>
        <div className="flex items-center gap-2 shrink-0 ml-3">
          {/* Status badge */}
          <span
            className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${
              status === "running"
                ? "bg-indigo-500/20 text-indigo-300 animate-pulse"
                : status === "failed"
                ? "bg-red-500/20 text-red-400"
                : "bg-emerald-500/15 text-emerald-400"
            }`}
          >
            {status === "running" ? "Running" : status === "failed" ? "Failed" : "Completed"}
          </span>
          {/* Duration */}
          {analysis.duration && (
            <span className="text-[11px] text-white/30 tabular-nums">{analysis.duration}</span>
          )}
          {/* Confidence chip */}
          <span className="text-[11px] px-2 py-0.5 rounded-full bg-indigo-500/15 text-indigo-300 tabular-nums">
            {analysis.confidence}% confident
          </span>
        </div>
      </div>

      {/* KPI Cards */}
      {analysis.summaryCards.length > 0 && (
        <div className="px-5 py-4 border-b border-white/8">
          <RiskSummaryCards cards={analysis.summaryCards} />
        </div>
      )}

      {/* Middle 3-column section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-0 divide-y lg:divide-y-0 lg:divide-x divide-white/8 border-b border-white/8">
        {/* Col 1: Summary + Key Findings */}
        <div className="px-5 py-4">
          <SectionHeading>Summary</SectionHeading>
          <p className="text-sm text-white/70 leading-relaxed mb-4">{analysis.summary}</p>

          {analysis.keyFindings.length > 0 && (
            <>
              <SectionHeading>Key Findings</SectionHeading>
              <ul className="space-y-1.5">
                {analysis.keyFindings.map((finding, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-white/65">
                    <span className="text-indigo-400 mt-0.5 shrink-0">›</span>
                    {finding}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>

        {/* Col 2: Recommended Actions */}
        <div className="px-5 py-4">
          <SectionHeading>Recommended Actions</SectionHeading>
          <RecommendedActionsPanel actions={analysis.recommendedActions} />
        </div>

        {/* Col 3: Confidence + Data Used */}
        <div className="px-5 py-4">
          <SectionHeading>Confidence</SectionHeading>
          <ConfidencePanel score={analysis.confidence} label={analysis.confidenceLabel} />

          {analysis.dataUsed.length > 0 && (
            <div className="mt-5">
              <SectionHeading>Data Sources</SectionHeading>
              <DataUsedPanel dataUsed={analysis.dataUsed} />
            </div>
          )}
        </div>
      </div>

      {/* Risk Breakdown */}
      {analysis.riskGroups.length > 0 && (
        <div className="px-5 py-4 border-b border-white/8">
          <SectionHeading>Risk Breakdown</SectionHeading>
          <RiskBreakdownSection riskGroups={analysis.riskGroups} />
        </div>
      )}

      {/* Footer: timestamp */}
      {createdAt && (
        <div className="px-5 py-2.5 bg-white/2">
          <p className="text-[11px] text-white/30">
            {new Date(createdAt).toLocaleTimeString()}
          </p>
        </div>
      )}
    </div>
  );
}
