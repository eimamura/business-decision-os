# Testing Strategy

## Tiers

| Tier | Tooling | Scope | Real LLM? |
|---|---|---|---|
| Unit | `pytest` | Single function / class; stubs return fixed values | No — `vcrpy` cassettes |
| Integration | `pytest` | API endpoints, DB operations, agent step sequences | No — `vcrpy` cassettes |
| E2E | `playwright` | Full user flows through the running stack | No — cassettes by default |

## Core Rules

- **`temperature=0` everywhere.** Any non-determinism in a test is a bug.
- **`vcrpy` cassettes block real LLM API calls** in unit and integration tiers. Never make live Anthropic calls in CI.
- **Stubs: assert schema conformance, not numerical accuracy.** Tests verify that stubs return the correct shape (`KpiScore`, `Candidate`, `SimulationOutput`, etc.) — not that the numbers are meaningful.
- **Smart stubs are forbidden.** A stub that approximates real behavior hides schema mismatches. Stubs must be trivially simple.

## Directory Layout

```
tests/
  unit/          # Pure function tests; no DB, no HTTP
  integration/   # DB + API tests; Postgres required
  e2e/           # Playwright tests; full stack required
data/
  fixtures/      # YAML test scenarios + vcrpy cassettes
    scenarios/   # Input/expected-output YAML per decision scenario
    cassettes/   # vcrpy HTTP interaction recordings
```

## Running Tests

```bash
# Unit + integration (cassettes replay LLM calls)
uv run pytest

# Unit only
uv run pytest tests/unit/

# Integration only (Postgres must be running)
uv run pytest tests/integration/

# E2E (full stack via make dev must be up)
npx playwright test
```

## vcrpy Cassette Discipline

Cassettes are committed to `data/fixtures/cassettes/` and replayed in CI. **Never delete a cassette to force a live call in a normal test run.**

To record or re-record a cassette:

```bash
RECORD_MODE=new_episodes uv run pytest tests/integration/path/to/test.py
```

When recording:
- Set `ANTHROPIC_API_KEY` in `.env`.
- Review the cassette diff before committing — it must contain no secrets or raw data rows.
- Re-record only when the prompt or schema changes, not to "refresh" values.

## What Each Tier Tests

### Unit

- KPI formula correctness (`packages/domain/kpi.py`)
- Risk classification logic (`config/risk_thresholds.yaml` loading + evaluation)
- Sample data generator: deterministic output under seed 42; NULL injection rate ≈ 2%; seasonal SKUs show autocorrelation amplitude > 0.3
- Approval state machine transitions
- Audit hash chain integrity
- Schema parity: Pydantic ↔ Zod equivalence check (generated types)

### Integration

- API endpoint contracts (status codes, response shapes) — 200 not 501
- Orchestrator step sequence: one `agent_steps` row per specialist call
- Tool invocations write `tool_calls` + `audit_log` in the same transaction
- `llm_usage` row written with every LLM call, never missing
- SQL Tool allowlist enforcement (queries to non-allowlisted tables rejected)
- Approval state transitions persist correctly; revisions create new rows with `parent_approval_id`

### E2E

Core flow (must pass before any phase is considered complete):

```
New session → chat message → SSE events received → recommendation rendered
→ approval queue shows pending item → decision submitted → audit timeline updated
```

Additional flows:
- Scenario comparison: two recommendations viewable side-by-side
- Reasoning Panel toggles with `Cmd/Ctrl + .`
- Tool Call Inspector shows executed SQL

## Stub Conformance Assertions

For every stubbed component, the test asserts the output matches the schema — nothing more:

| Stub | Schema to assert |
|---|---|
| Forecast Tool | `ForecastOutput` with `model_version`, `forecasts: list[DailyForecast]` |
| Simulation Tool | `SimulationOutput` with `kpi_scores: list[KpiScore]`, `horizon_days` |
| Optimization Tool | `OptimizationOutput` with `candidates: list[Candidate]`, `len >= 3` |
| MemoryStore.search | Returns `[]` (empty list, correct type) |

## CI Behavior

| Event | Tiers run |
|---|---|
| Pull request | Unit + integration |
| Merge to `main` | Unit + integration + E2E (against built image) |

E2E in CI runs against the Docker images built from the same commit, not the host dev server.
