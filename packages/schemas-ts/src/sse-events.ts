import { z } from "zod";

export const SessionStartedEventSchema = z.object({
  event: z.literal("session_started"),
  session_id: z.string().uuid(),
  timestamp: z.string(),
});

export const SpecialistActivatedEventSchema = z.object({
  event: z.literal("specialist_activated"),
  session_id: z.string().uuid(),
  timestamp: z.string(),
  specialist_role: z.string(),
  step_id: z.string().uuid(),
});

export const ToolCalledEventSchema = z.object({
  event: z.literal("tool_called"),
  session_id: z.string().uuid(),
  timestamp: z.string(),
  tool_call_id: z.string().uuid(),
  step_id: z.string().uuid(),
  tool_name: z.string(),
  input: z.record(z.unknown()),
  specialist_role: z.string(),
});

export const ToolCompletedEventSchema = z.object({
  event: z.literal("tool_completed"),
  session_id: z.string().uuid(),
  timestamp: z.string(),
  tool_call_id: z.string().uuid(),
  tool_name: z.string(),
  duration_ms: z.number().int(),
  output: z.record(z.unknown()),
  executed_query: z.string().nullable().optional(),
  status: z.enum(["success", "error"]),
  error: z.string().nullable().optional(),
});

export const RecommendationReadyEventSchema = z.object({
  event: z.literal("recommendation_ready"),
  session_id: z.string().uuid(),
  timestamp: z.string(),
  recommendation_id: z.string().uuid(),
  risk_level: z.enum(["low", "medium", "high"]),
  requires_approval: z.boolean(),
});

export const AwaitingApprovalEventSchema = z.object({
  event: z.literal("awaiting_approval"),
  session_id: z.string().uuid(),
  timestamp: z.string(),
  approval_id: z.string().uuid(),
  recommendation_id: z.string().uuid(),
  expires_at: z.string(),
});

export const ErrorEventSchema = z.object({
  event: z.literal("error"),
  session_id: z.string().uuid(),
  timestamp: z.string(),
  code: z.string(),
  message: z.string(),
  recoverable: z.boolean(),
});

export const DoneEventSchema = z.object({
  event: z.literal("done"),
  session_id: z.string().uuid(),
  timestamp: z.string(),
});

export const SseEventSchema = z.discriminatedUnion("event", [
  SessionStartedEventSchema,
  SpecialistActivatedEventSchema,
  ToolCalledEventSchema,
  ToolCompletedEventSchema,
  RecommendationReadyEventSchema,
  AwaitingApprovalEventSchema,
  ErrorEventSchema,
  DoneEventSchema,
]);

export type SseEvent = z.infer<typeof SseEventSchema>;
