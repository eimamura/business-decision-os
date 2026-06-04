# Testing Guide

Canonical rules and standards are defined in `.claude/rules/testing.md`.
This file covers operational How-to: running tests, recording cassettes, and CI configuration.

---

## Running Tests

```bash
# Unit tests (no Docker required)
uv run pytest tests/unit/ -x --timeout=30

# Integration tests (requires Docker Compose up)
uv run pytest tests/integration/ -x

# E2E tests (requires running server)
uv run pytest tests/e2e/ -x -m e2e

# Frontend tests
cd apps/web && npx vitest run
```

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

See `.env.example` for the full variable reference.
