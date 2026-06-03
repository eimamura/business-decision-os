import { apiFetch } from "@/lib/api";

export interface KpiTrend {
  date: string;
  service_level?: number;
  inventory_cost?: number;
  stockout_days?: number;
  working_capital?: number;
}

export interface LlmCostEntry {
  date: string;
  specialist: string;
  model: string;
  cost_usd: number;
}

export async function getKpiTrends(): Promise<KpiTrend[]> {
  const data = await apiFetch<KpiTrend[] | { items?: KpiTrend[] }>("/api/v1/kpi/trends");
  if (Array.isArray(data)) return data;
  return (data as { items?: KpiTrend[] }).items ?? [];
}

export async function getLlmCostEntries(): Promise<LlmCostEntry[]> {
  const data = await apiFetch<LlmCostEntry[] | { items?: LlmCostEntry[] }>("/api/v1/kpi/llm-cost");
  if (Array.isArray(data)) return data;
  return (data as { items?: LlmCostEntry[] }).items ?? [];
}
