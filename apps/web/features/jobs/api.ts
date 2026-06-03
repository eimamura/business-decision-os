import { apiFetch } from "@/lib/api";

export interface JobFileResponse {
  id: string;
  job_id: string;
  file_name: string;
  file_size_bytes: number;
  mime_type: string;
  download_url: string;
  created_at: string;
}

export interface JobResponse {
  id: string;
  session_id: string | null;
  status: string;
  job_type: string;
  created_at: string;
  completed_at: string | null;
  approval_id: string | null;
  result_json: Record<string, unknown> | null;
  generated_files: JobFileResponse[];
}

export type StatusFilter =
  | ""
  | "pending_approval"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export async function getJobs(
  params: { cursor?: string | null; status?: string },
): Promise<{ items: JobResponse[]; next_cursor: string | null }> {
  const qs = new URLSearchParams({ limit: "20" });
  if (params.cursor) qs.set("cursor", params.cursor);
  if (params.status) qs.set("status", params.status);
  return apiFetch<{ items: JobResponse[]; next_cursor: string | null }>(
    `/api/v1/jobs?${qs}`,
  );
}

export async function getJobFiles(
  cursor?: string | null,
): Promise<{ items: JobFileResponse[]; next_cursor: string | null }> {
  const qs = new URLSearchParams({ limit: "20" });
  if (cursor) qs.set("cursor", cursor);
  return apiFetch<{ items: JobFileResponse[]; next_cursor: string | null }>(
    `/api/v1/files?${qs}`,
  );
}

export async function getJobDetail(jobId: string): Promise<JobResponse> {
  return apiFetch<JobResponse>(`/api/v1/jobs/${jobId}`);
}
