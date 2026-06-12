# ADR: Daily Screening Scheduler — In-Process Asyncio Task (Interim), Not Celery

- Date: 2026-06-12
- Status: Accepted
- Phase: P93
- Decision owner: User (approved 2026-06-12: "activate the daily screening cadence"); mechanism chosen by Orchestrator

## Context

DESIGN.md §Operational Cadence states "MVP targets the daily cadence" and §Screening Layer
specifies that screening "runs on the operational cadence (daily for MVP) as a scheduled
job", naming a Celery task as the trigger ("its trigger lives in `apps/api/` (or a
dedicated worker), but its logic resides in `packages/tools/`").

Two settled decisions conflict with activating that Celery trigger now:

1. **P69 (2026-06-10, user decision):** Celery worker and `celery`/`redis` dependencies
   stay untouched until Azure deployment — they are not exercised by the local dev stack.
2. **P86 (2026-06-11):** the scheduled daily screening job was deferred for exactly that
   reason; `list_today_exceptions` shipped as an on-demand tool only.

On 2026-06-12 the user approved closing the daily-cadence gap as the top MVP priority.
Activating Celery beat locally would require running a worker + redis in the dev stack,
contradicting P69. Not scheduling at all leaves the SPEC framing ("scan operational data
daily, surface anomalies") unmet.

## Decision

1. **Interim scheduler: an in-process asyncio background task** managed by the FastAPI
   lifespan in `apps/api/`. On startup it runs the screening if no completed run exists for
   today, then ticks daily at `SCREENING_HOUR_UTC` (default 6). It can be disabled with
   `SCREENING_SCHEDULER_ENABLED=false` (tests/CI).
2. **Screening logic stays in `packages/tools/`** (`list_today_exceptions`), invoked
   directly via its `handle()` — deterministic SQL, no LLM call. This preserves the
   DESIGN.md placement rule: trigger in `apps/api/`, logic in `packages/tools/`.
3. **Results persist to a new `screening_runs` table** (run_date, status, counts, payload
   JSONB) — the Working Context Store artifact DESIGN.md §Screening Layer calls for. The
   `notifications` table remains approval-centric and untouched; the user-facing surface is
   a Daily Exceptions panel on the web chat page reading `GET /api/v1/screenings/today`.
4. **Celery remains the deployment-target mechanism.** Migration trigger: when the Azure
   deployment activates the Celery worker (P69 unlock), the lifespan task is replaced by a
   Celery beat schedule invoking the same service function. The service function MUST stay
   transport-agnostic (plain async callable) so the swap is a trigger change only.

## Consequences

- Daily cadence works on the local dev stack with zero new infrastructure.
- A single-process API is assumed; if the API ever runs multi-replica before Azure, the
  daily tick could double-fire — acceptable because runs are idempotent-by-read (readers
  take the latest completed row per day) and re-runs are harmless reads.
- `.claude/rules/fastapi.md` "long-running work → Celery" is intentionally not violated:
  the screening run is a bounded read-only aggregation (seconds), within the rule's
  lightweight-background allowance; the rule's Celery path is deferred with P69.
- DESIGN.md §Screening Layer's Celery sentence is now qualified by this ADR (interim
  mechanism documented here; DESIGN.md text unchanged — code is runtime truth, this ADR is
  design truth for the interim).
