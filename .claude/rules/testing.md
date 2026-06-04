# Testing Rules

Standards for pytest, vcrpy, and Playwright.

## How to Run Tests (mandatory)

Always use `make` targets. Never invoke `pytest`, `npx playwright test`, or `npx vitest` directly.

| Command | What it runs | Prerequisites |
|---|---|---|
| `make test-unit` | `pytest tests/unit` | none |
| `make test-integration` | `pytest tests/integration` | `docker compose up -d db` |
| `make test-e2e` | `pytest tests/e2e` | API server running |
| `make test-playwright` | Playwright browser E2E | `make dev-up` |
| `make test` | all Python tiers | varies |

**Playwright must always go through `make test-playwright`.** Running `npx playwright test`
directly fails because:
1. `@playwright/test` is installed under `apps/web/node_modules/` but spec files live in
   `tests/e2e/playwright/` — Node module resolution breaks without `NODE_PATH`.
2. The Makefile sets `WEB_URL` and `NEXT_PUBLIC_API_URL` to match the configured ports
   (`WEB_PORT=3002`, `API_PORT=8002`). Skipping the Makefile points Playwright at the
   wrong ports.

## Test Tiers

Three tiers, with different infrastructure requirements:

| Tier | Requires Docker | DB access | Mark |
|---|---|---|---|
| Unit | No | No — test pure logic only | (none) |
| Integration | Yes | Real database | (none) |
| E2E | Yes | Real database + running server | `@pytest.mark.e2e` |

- **Unit tests** cover pure functions, domain logic, and schema validation — no I/O. If a function queries the DB, it belongs in integration.
- **Integration tests** hit the real database. Do not mock the DB — mocking leads to false passes when schema or query behavior diverges.
- **E2E tests** require a live server; mark with `@pytest.mark.e2e`.

## pytest

- `asyncio_mode = "auto"` is set globally — do not add `@pytest.mark.asyncio` per test; **remove it if you find it in existing tests**
- Test file naming: `test_<module>.py`
- Test function naming: `test_<subject>_<condition>_<expected_outcome>`
- Fixtures: define in the nearest `conftest.py`; default to function scope; justify session scope explicitly
- One logical assertion per test; use `pytest.raises(ExcType)` as a context manager for expected exceptions
- Parametrize repetitive cases with `@pytest.mark.parametrize`

## Zero-Network Rule in Unit Tests

Unit tests must never make real network calls. The `tests/unit/conftest.py` autouse fixture blocks:

- `anthropic.AsyncAnthropic` message creation
- `httpx.AsyncHTTPTransport` (real HTTP connections; ASGI transport is still allowed)

Tests that need LLM responses must use `StubClaudeClient`, `ScenarioStubClaudeClient` (scenario-aware variant), or `unittest.mock`. Both stubs live in `packages/agent/llm/__init__.py`.

## External HTTP / LLM Calls (Integration)

- All outbound HTTP and LLM calls in integration tests must be wrapped in vcrpy cassettes
- Never record cassettes against production endpoints with real credentials
- The `vcr_config` fixture in `tests/integration/conftest.py` sets:
  - `cassette_library_dir`: `tests/cassettes/` — committed to the repository
  - `record_mode`: `none` — playback only in CI; use `VCR_RECORD=new` to record locally
  - `match_on`: `["uri", "method", "body"]` — strict matching catches prompt changes
  - `filter_headers`: `["Authorization", "x-api-key"]` — API keys scrubbed before saving
- To reduce API costs during development, set `TEST_MODEL=claude-haiku-4-5-20251001`

## FastAPI Testing

- Use `httpx.AsyncClient` with `transport=ASGITransport(app=app)` — not the `requests` library
- Do not spin up a live server for unit or integration tests

## End-to-End Tests

- Mark with `@pytest.mark.e2e`; these require a running server
- Unit tests must pass without Docker; integration and E2E tests require Docker Compose

## Test Data

- Never commit real or production data to fixtures
- Use factory functions in `conftest.py` to build domain objects; avoid large inline dicts in test bodies

## Playwright (E2E Web)

- Page object pattern: one class per page/component
- Locate elements with `page.locator("[data-testid=...]")`; add `data-testid` attributes to components under test

## Coverage

- Do not chase coverage percentage; optimize for testing real behavior
- A test that doesn't assert meaningful behavior is worse than no test
