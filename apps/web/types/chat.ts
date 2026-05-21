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

export type SSEEventType =
  | "session_started"
  | "step_started"
  | "step_completed"
  | "specialist_started"
  | "specialist_completed"
  | "tool_called"
  | "tool_completed"
  | "memory_retrieved"
  | "memory_written"
  | "recommendation_ready"
  | "auto_executed"
  | "awaiting_approval"
  | "error"
  | "done";

export interface SSEEvent {
  type: SSEEventType;
  reply?: string;
  message_id?: string;
  message?: string;
  code?: string;
  recoverable?: boolean;
  step_id?: string;
  step_type?: string;
  specialist_role?: string;
  started_at?: string;
  duration_ms?: number;
  output_preview?: string;
  tokens?: number;
  cost_usd?: number;
  input_tokens?: number;
  output_tokens?: number;
  requires_approval?: boolean;
  risk_level?: string;
  approval_id?: string;
  tool_name?: string;
  tool_call_id?: string;
  executed_query?: string;
}
