# ADR: Separate Forecast Training Job from Realtime Inference

**Date:** 2026-05-20
**Status:** Accepted
**Deciders:** Engineering Team

## Context

`LinearRegressionPredictor.predict()` calls `model.fit()` on every invocation,
re-training from `demand_history` on each API request. This couples offline training
with online inference, making every forecast request as expensive as a training run.
The `Predictor` Protocol is correct and must not change. Only the implementation
behind it needs to be rearchitected.

The fix requires adding `kind="train_forecast"` to `JobSpec.kind` — a change to
the `JobRunner` public interface that triggers an ADR per AGENTS.md.

## Decision

Add `kind="train_forecast"` to `JobSpec.kind` Literal. Implement a
`TrainedModelPredictor` that loads pre-fitted model coefficients from the
`prediction_features` table and calls only `model.predict()` at request time.
The `InProcessJobRunner` gains a `_run_train_forecast` handler that fits the model
and writes coefficients back to `prediction_features`. Training is triggered
explicitly (via `JobRunner.submit`) on a schedule or on demand — never implicitly
inside a `predict()` call.

## Rationale

- **Separation of concerns:** Training is a batch job; inference is a hot path.
  They have different latency requirements and should not share a call stack.
- **Consistency with Databricks path:** `DatabasePredictor` already reads pre-computed
  features written by Databricks jobs (T-6002/T-6003). `TrainedModelPredictor` mirrors
  this pattern for the in-process backend.
- **No Protocol change:** `Predictor.predict(sku_id, horizon_days) → PredictorResult`
  is unchanged. `ForecastTool` requires no modification.

## Trade-offs

- **Benefit:** Inference latency drops from O(training) to O(predict). Model is
  reproducible and versionable via `model_version` field.
- **Cost / risk:** Model can become stale if training job is not triggered after
  demand pattern shifts. First `predict()` on a fresh DB returns no coefficients
  and must fall back to `LinearRegressionPredictor`.
- **Mitigation:** `TrainedModelPredictor` falls back to `LinearRegressionPredictor`
  when `prediction_features` has no row for the requested SKU. Fallback is logged
  with `source="in_process_fallback"` so staleness is observable.

## Consequences

- `packages/agent/job_runner/__init__.py`: `JobSpec.kind` Literal gains `"train_forecast"`.
  `InProcessJobRunner.result()` gains a `_run_train_forecast` branch.
- `packages/prediction/__init__.py`: New `TrainedModelPredictor` class added.
  `LinearRegressionPredictor` unchanged (still used as fallback).
- `docs/DESIGN.md` §JobRunner: `JobSpec.kind` Literal must be updated to include
  `"train_forecast"` in the canonical definition.
- No schema migration required: `prediction_features` table already exists (T-6003).
- Follow-up: Consider adding `train_forecast` support to `AcaJobsRunner` and
  `CeleryJobRunner` in a future task.
