export type MessageRole = "user" | "assistant" | "tool";

export interface ChatMessage {
  id: string;
  messageId?: string;
  role: MessageRole;
  content: string;
  feedback?: 1 | -1;
  created_at?: string;
  isError?: boolean;
  isStreaming?: boolean;
  toolName?: string;
  sql?: string;
}

export interface Session {
  session_id: string;
  status: string;
  goal?: string;
  created_at: string;
}

export interface SessionUsage {
  inputTokens: number;
  outputTokens: number;
  costUsd: number;
}

export type { SseEvent } from "@bdos/schemas-ts";
export type { SseEvent as SSEEvent } from "@bdos/schemas-ts";
