# Testing Guide

Canonical rules and standards are defined in `.claude/rules/testing.md`.
This file covers operational How-to: running tests, recording cassettes, and CI configuration.

---

## Running Tests

Always use `make` targets — never call `pytest`, `npx playwright`, or `npx vitest` directly.
The Makefile wires up required env vars (ports, NODE_PATH) and keeps commands reproducible.

```bash
make test-unit          # unit tests only (no Docker required)
make test-integration   # integration tests (requires docker compose up -d db)
make test-e2e           # Python E2E tests (requires running API server)
make test-playwright    # Playwright browser E2E (requires make dev-up)
make test               # all Python tests (unit + integration + e2e)
```

Frontend (Vitest) — always via npm script, not npx directly:
```bash
cd apps/web && npm test
```

### Why `npx playwright test` fails directly

1. `@playwright/test` is installed under `apps/web/node_modules/` but spec files live in
   `tests/e2e/playwright/` — Node module resolution breaks without `NODE_PATH`.
2. The Makefile sets `WEB_URL` and `NEXT_PUBLIC_API_URL` to match the configured ports
   (`WEB_PORT=3002`, `API_PORT=8002`). Skipping the Makefile points Playwright at the
   wrong ports.

---

## Recording vcrpy Cassettes

Integration tests that call the real Anthropic API must use `@pytest.mark.vcr`. Record once,
replay forever — eliminating API costs and flakiness in CI.

The `vcr_config` fixture in `tests/integration/conftest.py` sets:
- `cassette_library_dir`: `tests/cassettes/` — committed to the repository
- `record_mode`: `none` — playback only in CI; use `VCR_RECORD=new` to record locally
- `match_on`: `["uri", "method", "body"]` — strict matching catches prompt changes
- `filter_headers`: `["Authorization", "x-api-key"]` — API keys scrubbed before saving

```python
@pytest.mark.vcr
async def test_llm_call_returns_valid_response() -> None:
    client = create_llm_client()
    # cassette replays the response on subsequent runs
```

To record a cassette for a new or updated test:

```bash
VCR_RECORD=new uv run pytest tests/integration/test_your_module.py::test_your_function -v
```

The cassette is written to `tests/cassettes/<test_name>.yaml`. Commit it alongside the test.
Override the default name with `@pytest.mark.vcr("custom-cassette-name.yaml")`.

---

## Cost-Saving Overrides

```bash
# Use a cheaper model during integration test development
TEST_MODEL=claude-haiku-4-5-20251001 uv run pytest tests/integration/ -x
```

### Local LLM (Ollama) — zero API cost

Ollama runs as a systemd service on this machine — no manual startup needed.
Port 11434 does not conflict with Docker Compose (API: 8002, web: 3002, DB: 5432, Redis: 6379).

```bash
# Verify it's up
curl -s http://localhost:11434/api/tags | python3 -m json.tool

# First time only: pull the model
ollama pull gemma4:12b
```

Then set in `.env`:

```
LLM_PROVIDER=ollama
OLLAMA_MODEL=gemma4:12b
```

`OLLAMA_BASE_URL` defaults to `http://localhost:11434`. The code-level fallback for `OLLAMA_MODEL` (used
only if the env var is unset) lives in `create_model_registry()` in `packages/agent/model_registry.py` — that
is the SSoT for the default; do not hand-copy the literal here, as it has drifted before. The operational
model recommended for local dev is `gemma4:12b` (switched 2026-06-07); set `OLLAMA_MODEL=gemma4:12b`
explicitly rather than relying on the code fallback. See `.env.example` for overrides.

See `.env.example` for the full variable reference.

---

## Stub Conformance

Pattern:

```python
def test_stub_returns_correct_schema():
    result = stub.run(valid_input)
    assert isinstance(result, ExpectedOutputType)
    # For Optimization:
    assert len(result.candidates) >= 3
    # Do NOT assert numerical values
```

Required assertions per stub:

| Stub | Required assertion |
|---|---|
| Forecast Tool | `ForecastOutput` shape: `model_version`, `forecasts: list[DailyForecast]` |
| Simulation Tool | `SimulationOutput` shape: `kpi_scores: list[KpiScore]`, `horizon_days` |
| Optimization Tool | `OptimizationOutput` shape: `candidates: list[Candidate]`, `len(candidates) >= 3` |
| MemoryStore.search | Returns `[]` (empty list, correct type) |
| ScenarioStubClaudeClient | `complete()` returns `LLMResponse`; `text` is JSON with shape determined by system prompt keywords: intent/category → `{"category", "confidence", "rationale", "goal_text"}`; route/primary_role → `{"mode", "primary_role", "rationale"}`; verify/findings → `{"status", "rationale"}`; default → plain string. Do NOT assert specific field values. |

---

## Eval Runner

The eval runner tests the full agent pipeline against golden cases — not just code correctness, but **judgment quality**: which tools the agent calls, what it says, and whether it avoids known failure modes.

```bash
make eval                             # run all 10 SPEC golden cases (requires running API)
API_URL=http://localhost:8002 make eval  # explicit API URL
uv run python scripts/run_evals.py --dry-run  # list cases without running
```

The runner writes a timestamped markdown report to `docs/eval-reports/YYYY-MM-DD-HHMM-eval-run.md`.

### Golden cases

`data/evals/spec10_golden_cases.yaml` — 10 cases, one per SPEC question (Q1–Q10). Each case defines:

| Field | Purpose |
|---|---|
| `required_tools` | Tools that must be called — absence → `retrieval` or `routing` failure |
| `must_not_use_tools` | Tools that must NOT be called — presence → `pollution` or `routing` failure |
| `response_assertions.must_contain` | Strings that must appear in the reply |
| `response_assertions.must_not_contain` | Degenerate patterns (e.g. "I don't have", French text from context overflow) |
| `expected_behavior` | Human-readable assertions for manual review |
| `failure_modes` | Pre-identified failure patterns per question |

### Failure classification

The runner classifies each failure into one of five types:

| Type | Meaning | Fix target |
|---|---|---|
| `routing` | Required tool not called AND prohibited tool called | `context_builder.py` — keyword map |
| `pollution` | Prohibited tool called (required tools also called) | `USE_CASE_PACKS[Qn].prohibited_tools` |
| `retrieval` | Required tool not called at all | `USE_CASE_PACKS[Qn].required_tools` or routing policy |
| `reasoning` | Tool calls correct but degenerate/wrong response | system prompt, context overflow (check context_log) |
| `output` | Tools correct but response missing expected content | response format rules or routing hint |

### Extending golden cases

1. Add a new entry to `data/evals/spec10_golden_cases.yaml`
2. Add the corresponding `ContextPack` to `packages/schemas/context_packs.py §USE_CASE_PACKS`
3. Add keywords to `packages/agent/control/context_builder.py §_USE_CASE_KEYWORDS`
4. Run `make eval` to verify the new case passes

### Context trace logs

After a failed eval run, inspect what the agent actually received:

```bash
# Requires running API + DB
curl "http://localhost:8002/api/v1/admin/context-logs?session_id=<uuid>"
```

Each log row shows: `use_case_id`, `intent`, `required_tools`, `prohibited_tools`, `context_pack_json`.
If `use_case_id == "GENERIC"` for a Q1–Q10 question, the keyword classifier did not match — add the user's phrasing as a new keyword.

---

## Unit Test Scope

- KPI formula correctness (`packages/knowledge/kpi.py`)
- Risk classification (3-tier thresholds from `config/risk_thresholds.yaml`)
- Sample data generator: seed-42 determinism, NULL rate ≈ 2%, seasonal amplitude > 0.3
- Approval state machine transitions
- Audit hash chain: each row's `audit_hash` depends on `prev_audit_hash`
- Pydantic ↔ Zod schema parity (CI equivalence check)
