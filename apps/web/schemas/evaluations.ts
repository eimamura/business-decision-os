import { z } from "zod";

import { KpiScoreSchema } from "./recommendation";

// AUTO-GENERATED — do not edit by hand.
// Single Source of Truth: packages/schemas/evaluations.py
// Regenerate:  make codegen
export const EvaluationCriteriaSchema = z.object({
  kpi_names: z.array(z.string()),
  weights: z.record(z.number()),
  risk_thresholds: z.record(z.unknown()),
});

export const EvaluationResultSchema = z.object({
  candidate_id: z.string(),
  kpi_scores: z.array(KpiScoreSchema),
  risk_level: z.enum(["low", "medium", "high"]),
});
