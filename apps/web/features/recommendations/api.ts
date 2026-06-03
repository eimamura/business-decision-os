import { apiFetch } from "@/lib/api";

export interface KpiScore {
  kpi: string;
  score: number;
}

export interface TradeoffExplanation {
  what_you_give_up: string;
  benefit: string;
}

export interface Alternative {
  id: string;
  label: string;
  kpi_scores: KpiScore[];
  tradeoff: TradeoffExplanation;
}

export interface Recommendation {
  id: string;
  session_id: string;
  primary_candidate_id: string;
  primary_label: string;
  primary_kpi_scores: KpiScore[];
  alternatives: Alternative[];
  rationale: string;
  risk_level: "low" | "medium" | "high";
  requires_approval: boolean;
  weight_vector: Record<string, number>;
  created_at: string;
}

export async function getRecommendation(id: string): Promise<Recommendation> {
  return apiFetch<Recommendation>(`/api/v1/recommendations/${id}`);
}
