import { z } from "zod";

// AUTO-GENERATED — do not edit by hand.
// Single Source of Truth: packages/schemas/jobs.py
// Regenerate:  make codegen
export const JobFileResponseSchema = z.object({
  id: z.string().uuid(),
  job_id: z.string().uuid(),
  file_name: z.string(),
  file_size_bytes: z.number().int(),
  mime_type: z.string(),
  download_url: z.string(),
  created_at: z.string().datetime(),
});

export const JobResponseSchema = z.object({
  id: z.string().uuid(),
  session_id: z.string().uuid().nullable().optional(),
  status: z.string(),
  job_type: z.string(),
  created_at: z.string().datetime(),
  completed_at: z.string().datetime().nullable().optional(),
  approval_id: z.string().uuid().nullable().optional(),
  result_json: z.record(z.unknown()).nullable().optional(),
  generated_files: z.array(JobFileResponseSchema),
});

export const JobListResponseSchema = z.object({
  items: z.array(JobResponseSchema),
  next_cursor: z.string().uuid().nullable().optional(),
});

export const FileListResponseSchema = z.object({
  items: z.array(JobFileResponseSchema),
  next_cursor: z.string().uuid().nullable().optional(),
});
