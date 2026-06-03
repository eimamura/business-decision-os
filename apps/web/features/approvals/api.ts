import { apiFetch } from "@/lib/api";

export interface Approval {
  id: string;
  recommendation_id: string;
  status: "pending" | "approved" | "rejected" | "needs_revision" | "expired";
  risk_level: "low" | "medium" | "high";
  summary?: string;
  expires_at?: string;
  created_at: string;
}

export type ApprovalDecision = "approved" | "rejected";

export interface RevisionPayload {
  decision: "needs_revision";
  reason: string;
  kpi_weights?: Record<string, number>;
}

export async function getApprovals(status: string): Promise<Approval[]> {
  const data = await apiFetch<Approval[] | { items?: Approval[] }>(
    `/api/v1/approvals?status=${status}`,
  );
  if (Array.isArray(data)) return data;
  return (data as { items?: Approval[] }).items ?? [];
}

export async function postDecision(
  id: string,
  decision: ApprovalDecision,
): Promise<void> {
  await apiFetch<unknown>(`/api/v1/approvals/${id}/decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision }),
  });
}

export async function postRevision(
  id: string,
  payload: RevisionPayload,
): Promise<void> {
  await apiFetch<unknown>(`/api/v1/approvals/${id}/decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
