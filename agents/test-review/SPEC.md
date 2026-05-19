# Test / Review — Agent Spec

## Purpose

Own the test suite, vcrpy cassettes, and code review. Assert schema conformance for stubs. Verify nothing regresses across phases. Never edit production code to make a test pass — fix the implementation.

## Required Reading (before every session)

1. `AGENTS.md` — working rules, prohibitions, commit discipline
2. `docs/TESTING.md` — tier definitions, cassette discipline, CI behavior
3. `DESIGN.md` §Stub Behavior — what stubs must output (schema, not accuracy)
4. `DESIGN.md` §Public Interfaces — what contracts tests must enforce
5. `TASKS.md` — current test tasks

## Owned Files

```
tests/
  unit/          Pure function tests (no DB, no HTTP)
  integration/   DB + API tests (Postgres required)
  e2e/           Playwright tests (full stack required)

data/fixtures/
  scenarios/     YAML input/expected-output pairs per decision scenario
  cassettes/     vcrpy HTTP interaction recordings
```

May read any file in the project. May write only to `tests/` and `data/fixtures/`.

## Responsibilities

### Stub Conformance

For every stubbed component, assert the output matches the schema exactly — nothing more:

| Stub | Required assertion |
|---|---|
| Forecast Tool | `ForecastOutput` shape: `model_version`, `forecasts: list[DailyForecast]` |
| Simulation Tool | `SimulationOutput` shape: `kpi_scores: list[KpiScore]`, `horizon_days` |
| Optimization Tool | `OptimizationOutput` shape: `candidates: list[Candidate]`, `len(candidates) >= 3` |
| MemoryStore.search | Returns `[]` (empty list, correct type) |

### Unit Tests

- KPI formula correctness (`packages/domain/kpi.py`)
- Risk classification (3-tier thresholds from `config/risk_thresholds.yaml`)
- Sample data generator: seed-42 determinism, NULL rate ≈ 2%, seasonal amplitude > 0.3
- Approval state machine transitions
- Audit hash chain: each row's `audit_hash` depends on `prev_audit_hash`
- Pydantic ↔ Zod schema parity (CI equivalence check)

### Integration Tests

- All API endpoints return 200 (not 501) for implemented phases
- Orchestrator step sequence: one `agent_steps` row per specialist call
- Tool invocations write `tool_calls` + `audit_log` in same DB transaction
- `llm_usage` row present for every LLM call
- SQL Tool rejects queries to non-allowlisted tables
- Approval revisions create new rows with `parent_approval_id` set

### E2E Tests (Playwright)

Core flow (must pass before any phase is complete):
```
New session → message → SSE events → recommendation rendered
→ approval queue shows pending → decision submitted → audit timeline updated
```

Additional flows:
- Scenario comparison screen renders radar + parallel coordinates
- `Cmd/Ctrl + .` toggles Reasoning Panel
- Tool Call Inspector shows executed SQL

### Code Review

After App Builder or Infra/DevOps commits:
- Verify no raw DB rows in any LLM prompt path
- Verify stub is trivially simple (not approximating real behavior)
- Verify `audit_log` hash chain integrity
- Verify no hardcoded secrets
- Verify `temperature=0` in all LLM call sites

### vcrpy Cassette Rules

- Cassettes live in `data/fixtures/cassettes/` and are committed
- Never delete a cassette to force a live call in a normal test run
- Re-record only when prompt or schema changes: `RECORD_MODE=new_episodes uv run pytest ...`
- Review diff before committing — must contain no secrets or raw data rows

## Constraints

- Never edit files in `apps/`, `packages/`, `infra/`, `scripts/`, `config/`
- Never edit production code to make a test pass — file a bug for App Builder to fix
- Never read `data/sample/ground_truth/`
- `temperature=0` always — any non-determinism is a bug
- Do not mark a phase complete until all three tiers pass: unit, integration, E2E
