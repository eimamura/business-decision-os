# Testing Guide

## Test Tiers

| Tier | Requires Docker | DB access | Mark |
|---|---|---|---|
| Unit | No | No — test pure logic only | (none) |
| Integration | Yes | Real database | (none) |
| E2E | Yes | Real database + running server | `@pytest.mark.e2e` |

- **Unit tests** cover pure functions, domain logic, and schema validation — no I/O. If a function
  queries the DB, it belongs in integration.
- **Integration tests** hit the real database. Do not mock the DB — mocking leads to false passes
  when schema or query behavior diverges.
- **E2E tests** require a live server; mark with `@pytest.mark.e2e`.

## Running Tests

```bash
# Unit tests (no Docker required)
uv run pytest tests/unit/ -x --timeout=30

# Integration tests (requires Docker Compose up)
uv run pytest tests/integration/ -x

# E2E tests (requires running server)
uv run pytest tests/e2e/ -x -m e2e
```

## vcrpy Cassettes for LLM Calls

Integration tests that call the real Anthropic API must use `@pytest.mark.vcr`. This records HTTP
interactions once and replays them on subsequent runs — eliminating API costs and flakiness.

### Configuration

The `vcr_config` session fixture in `tests/integration/conftest.py` sets:

- `cassette_library_dir`: `tests/cassettes/` — cassettes are committed to the repository
- `record_mode`: `none` — cassettes must be pre-recorded; playback only in CI
- `match_on`: `["uri", "method", "body"]` — strict matching to catch prompt changes
- `filter_headers`: `["Authorization", "x-api-key"]` — API keys are scrubbed before saving

### Recording a New Cassette

To record a cassette for a new or updated integration test:

```bash
VCR_RECORD=new uv run pytest tests/integration/test_your_module.py::test_your_function -v
```

This writes the cassette to `tests/cassettes/<test_name>.yaml`. Commit the cassette alongside the
test. Never record cassettes against production endpoints with real credentials in CI.

### Usage Pattern

```python
import pytest

@pytest.mark.vcr
async def test_llm_call_returns_valid_response() -> None:
    from packages.agent.llm import create_llm_client
    client = create_llm_client()
    # ... call the client; the cassette replays the response
```

The cassette file name defaults to the test module path + test function name. Override with
`@pytest.mark.vcr("custom-cassette-name.yaml")`.

## Zero-Network Rule in Unit Tests

Unit tests must never make real network calls. The `tests/unit/conftest.py` autouse fixture blocks:

- `anthropic.AsyncAnthropic` message creation
- `httpx.AsyncHTTPTransport` (real HTTP connections; ASGI transport is still allowed)

Tests that need LLM responses must use `StubClaudeClient` or `unittest.mock`.

## TEST_MODEL Override

To reduce API costs during integration test development, set `TEST_MODEL` to a cheaper model:

```bash
TEST_MODEL=claude-haiku-4-5-20251001 uv run pytest tests/integration/ -x
```

This passes the model override to `create_llm_client()` without touching production config.
See `.env.example` for the full variable reference.
