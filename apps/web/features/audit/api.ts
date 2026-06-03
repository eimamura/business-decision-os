import { apiFetch } from "@/lib/api";

export interface AuditEntry {
  id: string;
  session_id?: string;
  agent?: string;
  tool_name?: string;
  status: string;
  input?: unknown;
  output?: unknown;
  tokens_in?: number;
  tokens_out?: number;
  cost_usd?: number;
  created_at: string;
  audit_hash?: string;
}

export async function getAuditEntries(
  params?: { sessionId?: string; role?: string; limit?: number },
): Promise<AuditEntry[]> {
  const qs = new URLSearchParams();
  if (params?.sessionId) qs.set("session_id", params.sessionId);
  if (params?.role) qs.set("role", params.role);
  if (params?.limit != null) qs.set("limit", String(params.limit));
  const query = qs.toString();
  const data = await apiFetch<AuditEntry[] | { items?: AuditEntry[] }>(
    `/api/v1/audit${query ? `?${query}` : ""}`,
  );
  if (Array.isArray(data)) return data;
  return (data as { items?: AuditEntry[] }).items ?? [];
}
