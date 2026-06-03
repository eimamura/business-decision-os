import { apiFetch } from "@/lib/api";

export interface AgentStep {
  step_id: string;
  session_id: string;
  session_title: string;
  specialist_role: string;
  step_type: string;
  started_at: string | null;
  ended_at: string | null;
  duration_ms: number | null;
  input_tokens: number;
  output_tokens: number;
  total_cost_usd: number;
}

export interface LlmUsageRow {
  id: string;
  agent_step_id: string;
  specialist_role: string;
  session_id: string;
  session_title: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
  total_cost_usd: number;
  latency_ms: number | null;
  created_at: string;
}

export async function getAgentSteps(): Promise<AgentStep[]> {
  const data = await apiFetch<AgentStep[] | { items?: AgentStep[] }>("/api/v1/admin/steps");
  if (Array.isArray(data)) return data;
  return (data as { items?: AgentStep[] }).items ?? [];
}

export async function getLlmUsage(): Promise<LlmUsageRow[]> {
  const data = await apiFetch<LlmUsageRow[] | { items?: LlmUsageRow[] }>("/api/v1/admin/llm-usage");
  if (Array.isArray(data)) return data;
  return (data as { items?: LlmUsageRow[] }).items ?? [];
}

export async function deleteAllUsage(): Promise<void> {
  await apiFetch<unknown>("/api/v1/admin/sessions", { method: "DELETE" });
}
