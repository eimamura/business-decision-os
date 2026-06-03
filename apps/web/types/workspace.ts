export type GraphNodeKind = "orchestrator" | "agent" | "tool";
export type GraphNodeStatus = "running" | "completed" | "failed";

export interface GraphRunNode {
  runId: string;
  parentRunId?: string;
  kind: GraphNodeKind;
  name: string;
  status: GraphNodeStatus;
  startedAt: string;
  completedAt?: string;
  durationMs?: number;
  meta?: Record<string, unknown>;
  output?: Record<string, unknown>;
  tokenCost?: { inputTokens: number; outputTokens: number; costUsd: number };
}

export interface EvidenceSource {
  id: string;
  name: string;
  period: string;
  status: "used" | "available";
}

export interface RecommendedAction {
  id: string;
  label: string;
  priority: "high" | "medium" | "low";
}

export interface AnalysisResult {
  title: string;
  status: "running" | "completed" | "failed" | "needs_review";
  duration?: string;
  summary: string;
  keyFindings: string[];
  recommendedActions: RecommendedAction[];
  confidence: { score: number; label: string };
  dataUsed: EvidenceSource[];
}

export interface QuickAction {
  id: string;
  title: string;
  description: string;
  prompt: string;
}
