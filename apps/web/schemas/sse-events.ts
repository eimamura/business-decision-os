import { z } from "zod";

// AUTO-GENERATED — do not edit by hand.
// Single Source of Truth: packages/schemas/sse_events.py
// Regenerate:  make codegen
export const TokenCostSchema = z.object({
  input_tokens: z.number().int(),
  output_tokens: z.number().int(),
  cost_usd: z.number(),
});

export const GraphNodeEventSchema = z.object({
  type: z.literal("graph_node"),
  event: z.enum(["start", "end"]),
  kind: z.enum(["orchestrator", "agent", "tool"]),
  name: z.string(),
  run_id: z.string(),
  parent_run_id: z.string().nullable().optional(),
  timestamp: z.string(),
  input_summary: z.string().nullable().optional(),
  duration_ms: z.number().int().nullable().optional(),
  status: z.enum(["ok", "error"]),
  meta: z.record(z.unknown()),
  output: z.record(z.unknown()).nullable().optional(),
  token_cost: TokenCostSchema.nullable().optional(),
  error: z.string().nullable().optional(),
});

export const MemoryRetrievedEventSchema = z.object({
  type: z.literal("memory_retrieved"),
  count: z.number().int(),
  source: z.string().nullable().optional(),
  timestamp: z.string(),
});

export const MemoryWrittenEventSchema = z.object({
  type: z.literal("memory_written"),
  timestamp: z.string(),
});

export const ResponseReadyEventSchema = z.object({
  type: z.literal("response_ready"),
  mode: z.string(),
  risk_level: z.enum(["low", "medium", "high"]).nullable().optional(),
  requires_approval: z.boolean().nullable().optional(),
  timestamp: z.string(),
});

export const AutoExecutedEventSchema = z.object({
  type: z.literal("auto_executed"),
  recommendation_id: z.string(),
  timestamp: z.string(),
});

export const ApprovalRequestedEventSchema = z.object({
  type: z.literal("approval_requested"),
  approval_id: z.string(),
  expires_at: z.string(),
  risk_level: z.enum(["low", "medium", "high"]),
  timestamp: z.string(),
});

export const AwaitingApprovalEventSchema = z.object({
  type: z.literal("awaiting_approval"),
  session_id: z.string(),
  approval_id: z.string(),
  tool_name: z.string(),
  tool_input: z.record(z.unknown()),
  job_id: z.string().nullable().optional(),
  description: z.string(),
  timestamp: z.string(),
});

export const AskUserRequiredEventSchema = z.object({
  type: z.literal("ask_user_required"),
  session_id: z.string(),
  ask_user_id: z.string(),
  question: z.string(),
  suggestions: z.array(z.string()),
  timestamp: z.string(),
});

export const ClarificationRequiredEventSchema = z.object({
  type: z.literal("clarification_required"),
  session_id: z.string(),
  round: z.number().int(),
  message: z.string(),
  timestamp: z.string(),
});

export const SessionPausedEventSchema = z.object({
  type: z.literal("session_paused"),
  session_id: z.string(),
  approval_id: z.string(),
  tool_name: z.string(),
  timestamp: z.string(),
});

export const JobFileSchema = z.object({
  file_name: z.string(),
  download_url: z.string(),
});

export const JobCompletedEventSchema = z.object({
  type: z.literal("job_completed"),
  job_id: z.string(),
  job_type: z.string(),
  file_count: z.number().int(),
  files: z.array(JobFileSchema),
  timestamp: z.string(),
});

export const JobFailedEventSchema = z.object({
  type: z.literal("job_failed"),
  job_id: z.string(),
  job_type: z.string(),
  error: z.string(),
  timestamp: z.string(),
});

export const ErrorEventSchema = z.object({
  type: z.literal("error"),
  step_id: z.string().nullable().optional(),
  code: z.string(),
  message: z.string(),
  recoverable: z.boolean(),
  timestamp: z.string(),
});

export const TextDeltaEventSchema = z.object({
  type: z.literal("text_delta"),
  session_id: z.string(),
  delta: z.string(),
  timestamp: z.string(),
});

export const DoneEventSchema = z.object({
  type: z.literal("done"),
  session_id: z.string().uuid(),
  reply: z.string().nullable().optional(),
  timestamp: z.string(),
});

export const AwaitingInputEventSchema = z.object({
  type: z.literal("awaiting_input"),
  session_id: z.string().uuid(),
  ask_user_id: z.string(),
  timestamp: z.string(),
});

export const SseEventSchema = z.discriminatedUnion("type", [
  GraphNodeEventSchema,
  MemoryRetrievedEventSchema,
  MemoryWrittenEventSchema,
  ResponseReadyEventSchema,
  ApprovalRequestedEventSchema,
  AutoExecutedEventSchema,
  AwaitingApprovalEventSchema,
  AskUserRequiredEventSchema,
  ClarificationRequiredEventSchema,
  SessionPausedEventSchema,
  JobCompletedEventSchema,
  JobFailedEventSchema,
  ErrorEventSchema,
  TextDeltaEventSchema,
  DoneEventSchema,
  AwaitingInputEventSchema,
]);

export type SseEvent = z.infer<typeof SseEventSchema>;
