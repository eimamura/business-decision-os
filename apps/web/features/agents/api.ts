import { apiFetch } from "@/lib/api";

export interface AgentEntry {
  role: string;
  display_name: string;
  category: "domain" | "cross_domain" | "orchestrator";
  tools: string[];
  execution_count: number;
  last_executed_at: string | null;
}

export interface ToolEntry {
  name: string;
  display_name: string;
  used_by_agents: string[];
  execution_count: number;
  last_executed_at: string | null;
}

export interface RegistryData {
  agents: AgentEntry[];
  tools: ToolEntry[];
}

export async function getAgentRegistry(): Promise<RegistryData> {
  return apiFetch<RegistryData>("/api/v1/admin/registry");
}
