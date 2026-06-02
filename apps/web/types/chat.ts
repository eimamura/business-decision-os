export type MessageRole = "user" | "assistant" | "tool" | "job_approval" | "job_files";

export interface ChatMessage {
  id: string;
  messageId?: string;
  role: MessageRole;
  content: string;
  feedback?: 1 | -1;
  created_at?: string;
  isError?: boolean;
  isStreaming?: boolean;
  errorCode?: "network_error" | "server_error" | "unknown_error";
  toolName?: string;
  sql?: string;
  // job_approval card fields (role === "job_approval")
  approvalId?: string;
  jobId?: string | null;
  jobType?: string;
  jobDescription?: string;
  jobParams?: Record<string, unknown>;
  // job_files message fields (role === "job_files")
  jobFiles?: ReadonlyArray<{ readonly file_name: string; readonly download_url: string }>;
}

export interface Session {
  session_id: string;
  status: string;
  goal?: string;
  title?: string;
  created_at: string;
}

export interface SessionUsage {
  inputTokens: number;
  outputTokens: number;
  costUsd: number;
}

export { SseEventSchema } from "@bdos/schemas-ts";
export type { SseEvent } from "@bdos/schemas-ts";
