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

### Playwright note

`make test-playwright` sets `NODE_PATH`, `WEB_URL`, and `NEXT_PUBLIC_API_URL` automatically
to match the ports configured in the Makefile (`WEB_PORT=3002`, `API_PORT=8002`).
Never run `npx playwright test` by hand — the env vars will be wrong and the module
resolution for `@playwright/test` will fail because the test files live outside `apps/web/`.

---

## Recording vcrpy Cassettes

Integration tests that call the real Anthropic API must use `@pytest.mark.vcr`. Record once,
replay forever — eliminating API costs and flakiness in CI.

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
ollama pull qwen2.5-coder:7b
```

Then set in `.env`:

```
LLM_PROVIDER=ollama
```

`OLLAMA_BASE_URL` defaults to `http://localhost:11434` and `OLLAMA_MODEL` defaults to `qwen2.5-coder:7b`. See `.env.example` for overrides.

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

## Unit Test Scope

- KPI formula correctness (`packages/knowledge/kpi.py`)
- Risk classification (3-tier thresholds from `config/risk_thresholds.yaml`)
- Sample data generator: seed-42 determinism, NULL rate ≈ 2%, seasonal amplitude > 0.3
- Approval state machine transitions
- Audit hash chain: each row's `audit_hash` depends on `prev_audit_hash`
- Pydantic ↔ Zod schema parity (CI equivalence check)
