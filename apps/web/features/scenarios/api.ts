import { apiFetch } from "@/lib/api";

export interface KpiScore {
  kpi: string;
  score: number;
}

export interface Candidate {
  id: string;
  label: string;
  kpi_scores: KpiScore[];
  is_primary: boolean;
}

export async function getScenarios(sessionId: string): Promise<Candidate[]> {
  const data = await apiFetch<Candidate[] | { candidates?: Candidate[] }>(
    `/api/v1/sessions/${sessionId}/scenarios`,
  );
  if (Array.isArray(data)) return data;
  return (data as { candidates?: Candidate[] }).candidates ?? [];
}
