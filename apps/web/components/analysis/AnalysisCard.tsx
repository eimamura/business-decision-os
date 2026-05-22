"use client";

import type { ChatMessage } from "@/types/chat";

interface ParsedAnalysis {
  title: string;
  summary: string;
  keyFindings: string[];
  recommendedActions: Array<{ label: string; priority: "high" | "medium" | "low" }>;
  confidence: { score: number; label: string } | undefined;
  dataUsed: string[];
}

function extractSection(content: string, heading: string): string {
  const headingPattern = new RegExp(`##\\s+${heading}\\s*\\n([\\s\\S]*?)(?=\\n##\\s|$)`, "i");
  const match = headingPattern.exec(content);
  return match ? match[1].trim() : "";
}

function parseBullets(text: string): string[] {
  return text
    .split("\n")
    .map((line) => line.replace(/^[-*•]\s*/, "").replace(/^\d+\.\s*/, "").trim())
    .filter((line) => line.length > 0);
}

function parsePriority(line: string): "high" | "medium" | "low" {
  const lower = line.toLowerCase();
  if (lower.includes("high") || lower.includes("— high") || lower.includes("- high")) return "high";
  if (lower.includes("medium") || lower.includes("— medium")) return "medium";
  return "low";
}

function parseAnalysis(content: string, firstLine: string): ParsedAnalysis {
  const summary = extractSection(content, "Summary");
  const keyFindingsRaw = extractSection(content, "Key Findings");
  const actionsRaw = extractSection(content, "Recommended Actions");
  const confidenceRaw = extractSection(content, "Confidence");
  const dataUsedRaw = extractSection(content, "Data Used");

  const keyFindings = parseBullets(keyFindingsRaw);

  const recommendedActions = parseBullets(actionsRaw).map((line) => ({
    label: line.replace(/\s*[—-]\s*(high|medium|low)\s*$/i, "").trim(),
    priority: parsePriority(line),
  }));

  let confidence: ParsedAnalysis["confidence"];
  const confMatch = /(\d{1,3})%/.exec(confidenceRaw);
  if (confMatch) {
    const score = parseInt(confMatch[1], 10);
    confidence = {
      score,
      label: score >= 80 ? "High confidence" : score >= 60 ? "Medium confidence" : "Low confidence",
    };
  }

  const dataUsed = parseBullets(dataUsedRaw);

  return { title: firstLine, summary, keyFindings, recommendedActions, confidence, dataUsed };
}

const PRIORITY_STYLES: Record<string, string> = {
  high: "bg-red-500/15 text-red-400 border border-red-500/20",
  medium: "bg-amber-500/15 text-amber-400 border border-amber-500/20",
  low: "bg-emerald-500/15 text-emerald-400 border border-emerald-500/20",
};

interface AnalysisCardProps {
  message: ChatMessage;
  onFeedback?: (messageId: string, feedback: 1 | -1) => void;
}

export function isAnalysisCard(content: string): boolean {
  return content.includes("## Summary") && content.includes("## Key Findings");
}

export default function AnalysisCard({ message, onFeedback }: AnalysisCardProps): React.ReactElement {
  const lines = message.content.split("\n");
  const firstLine = lines.find((l) => l.trim() && !l.startsWith("#"))?.trim() ?? "Analysis";
  const analysis = parseAnalysis(message.content, firstLine);

  const status = message.isStreaming ? "running" : message.isError ? "failed" : "completed";

  return (
    <div className="max-w-[85%]">
      <div className="rounded-xl border border-indigo-500/20 bg-indigo-950/20 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/8 bg-white/3">
          <span className="text-xs font-semibold text-white/80 truncate">{analysis.title}</span>
          <span className={`shrink-0 ml-3 text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${
            status === "running"
              ? "bg-indigo-500/20 text-indigo-300 animate-pulse"
              : status === "failed"
              ? "bg-red-500/20 text-red-400"
              : "bg-emerald-500/15 text-emerald-400"
          }`}>
            {status === "running" ? "Running" : status === "failed" ? "Failed" : "Completed"}
          </span>
        </div>

        <div className="px-4 py-3 space-y-4">
          {/* Summary */}
          {analysis.summary && (
            <section>
              <h3 className="text-[10px] font-bold uppercase tracking-widest text-white/35 mb-1.5">Summary</h3>
              <p className="text-sm text-white/70 leading-relaxed">{analysis.summary}</p>
            </section>
          )}

          {/* Key Findings */}
          {analysis.keyFindings.length > 0 && (
            <section>
              <h3 className="text-[10px] font-bold uppercase tracking-widest text-white/35 mb-1.5">Key Findings</h3>
              <ul className="space-y-1">
                {analysis.keyFindings.map((f, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-white/65">
                    <span className="text-indigo-400 mt-0.5 shrink-0">›</span>
                    {f}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Recommended Actions */}
          {analysis.recommendedActions.length > 0 && (
            <section>
              <h3 className="text-[10px] font-bold uppercase tracking-widest text-white/35 mb-1.5">Recommended Actions</h3>
              <ol className="space-y-1.5">
                {analysis.recommendedActions.map((a, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-white/70">
                    <span className="text-white/30 w-4 shrink-0 tabular-nums">{i + 1}.</span>
                    <span className="flex-1">{a.label}</span>
                    <span className={`shrink-0 text-[10px] font-bold uppercase px-1.5 py-0.5 rounded ${PRIORITY_STYLES[a.priority]}`}>
                      {a.priority}
                    </span>
                  </li>
                ))}
              </ol>
            </section>
          )}

          {/* Confidence */}
          {analysis.confidence && (
            <section>
              <h3 className="text-[10px] font-bold uppercase tracking-widest text-white/35 mb-1.5">Confidence</h3>
              <div className="flex items-center gap-2">
                <div className="flex-1 h-1.5 rounded-full bg-white/10 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-indigo-500 transition-all"
                    style={{ width: `${analysis.confidence.score}%` }}
                  />
                </div>
                <span className="text-xs text-white/55 shrink-0 tabular-nums">
                  {analysis.confidence.score}% · {analysis.confidence.label}
                </span>
              </div>
            </section>
          )}

          {/* Data Used */}
          {analysis.dataUsed.length > 0 && (
            <section>
              <h3 className="text-[10px] font-bold uppercase tracking-widest text-white/35 mb-1.5">Data Used</h3>
              <div className="flex flex-wrap gap-1.5">
                {analysis.dataUsed.map((d, i) => (
                  <span key={i} className="text-xs px-2 py-0.5 rounded-full bg-white/8 text-white/50 border border-white/10">
                    {d}
                  </span>
                ))}
              </div>
            </section>
          )}
        </div>
      </div>

      {/* Footer: timestamp + feedback */}
      <div className="flex items-center justify-between mt-1 px-1">
        {message.created_at && (
          <p className="text-xs text-white/30">
            {new Date(message.created_at).toLocaleTimeString()}
          </p>
        )}
        {onFeedback && message.messageId && !message.isStreaming && (
          <div className="flex gap-1">
            {([-1, 1] as const).map((v) => (
              <button
                key={v}
                onClick={() => onFeedback(message.messageId!, v)}
                className={`text-xs px-1.5 py-0.5 rounded transition-colors ${
                  message.feedback === v
                    ? "text-indigo-400"
                    : "text-white/20 hover:text-white/50"
                }`}
              >
                {v === 1 ? "👍" : "👎"}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
