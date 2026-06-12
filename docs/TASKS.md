# TASKS.md

## Goal

Implementation tasks for Business Decision OS, decomposed into phases and batches by the
Orchestrator. See `docs/DESIGN.md` for architecture and `docs/ORCHESTRATOR.md` for the
execution process.

**Baseline: v0.1.0 (2026-06-12) — MVP complete.** All phases up to P100 are Done. Full
phase detail archived at `docs/archive/v5/TASKS.md` (P24–P64 in `docs/archive/v4/`,
P0–P23 in `docs/archive/v3/`).

Numbering continues repository-wide: **next phase = P101, next task = T-600, next defect
= D-016, next failure pattern = FP-015.**

---

## MVP Baseline (v0.1.0) — What Is Done

Tagged `v0.1.0` (commit 039c43a); merged to `main`; GitHub release published.

- **SPEC coverage**: all 10 SPEC questions answered by deterministic tools (registry: 39
  tools, 12 allowlisted tables) through the ControlAgent (single-agent MVP routing per
  the P65/P66 routing-collapse ADR).
- **Judged quality**: LLM-as-a-Judge campaign over all 10 questions — final 10/10 PASS
  (scores 0.72–0.88 on gemma4:12b). Report:
  `docs/judge-reports/2026-06-12-spec10-campaign.md`.
- **Daily cadence**: in-process scheduler (advisory-lock safe under multi-process) runs
  exception screening daily → `screening_runs` table → `/api/v1/screenings` API →
  persistent Daily Exceptions strip in the chat UI.
- **Context budget**: `peak_input_tokens` is the authoritative saturation signal; live
  peaks 30–40% of num_ctx 16384 (AGENTS.md prohibition + pinning tests guard regression).
- **Test assets at the tag**: unit 1234, integration 158 (full DSN), Playwright 45 — all
  green. Failure patterns FP-001–FP-014 recorded; FP-011 hardened.

## Carry-Over for Re-Planning (known deferrals & limitations)

| Item | Status / Decision |
|---|---|
| Authentication | Out of scope by user decision (2026-06-12, twice confirmed) — required before any non-local exposure |
| Real ERP / real data integration | No target system exists; SPEC known limitation |
| Azure deployment / Celery activation | P69 freeze — infra preserved untouched; screening scheduler migrates to Celery beat at unlock (ADR 2026-06-12-daily-screening-scheduler) |
| Model capability | gemma4:12b first-pass degeneration on some question classes (recovered via goal-refine + text_reset at ~2× latency); root fix = model upgrade or Anthropic API switch |
| Continuous quality measurement | Judge campaign is a one-shot run; no recurring evaluation automation |
| Anthropic cost computation | Tokens recorded, `total_cost_usd` 0.0 (P83 deferral) |
| npm audit | 18 known vulnerabilities (4 high) in web dependencies, pre-existing |
| SPEC Agent Catalog runtime agents | Deliberately not instantiated; promotion governed by DESIGN.md §Domain Capability Maturity Model |

---

## Active Phases

None — awaiting re-planning (next phase: P101).
