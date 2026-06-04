import { z } from "zod";

// AUTO-GENERATED — do not edit by hand.
// Single Source of Truth: packages/schemas/recommendation.py
// Regenerate:  make codegen
export const KpiScoreSchema = z.object({
  name: z.string(),
  value: z.number(),
  unit: z.string(),
  direction: z.enum(["higher_better", "lower_better"]),
});

export const CandidateSchema = z.object({
  id: z.string(),
  action: z.record(z.unknown()),
  kpi_scores: z.array(KpiScoreSchema),
  constraints_satisfied: z.array(z.string()),
  constraints_violated: z.array(z.string()),
});

export const TradeoffExplanationSchema = z.object({
  weight_vector: z.record(z.number()),
  weight_source: z.enum(["default", "user_policy", "session_goal", "critical_sku"]),
  primary_vs_alternative: z.array(z.record(z.unknown())),
});

export const RecommendationSchema = z.object({
  primary: CandidateSchema.nullable().optional(),
  alternatives: z.array(CandidateSchema),
  tradeoff: TradeoffExplanationSchema.nullable().optional(),
  rationale: z.string(),
  risk_level: z.enum(["low", "medium", "high"]),
  requires_approval: z.boolean(),
  direct_reply: z.string().nullable().optional(),
});
