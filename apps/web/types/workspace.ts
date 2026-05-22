export type AgentStepStatus = "pending" | "running" | "completed" | "failed";

export interface AgentStep {
  id: string;
  label: string;
  status: AgentStepStatus;
  duration?: string;
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
