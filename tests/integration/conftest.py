from __future__ import annotations

from typing import Any, AsyncGenerator

import pytest

VCR_CONFIG: dict = {  # type: ignore[type-arg]
    "cassette_library_dir": "tests/cassettes",
    "record_mode": "none",
    "match_on": ["uri", "method", "body"],
    "filter_headers": ["Authorization", "x-api-key"],
}


# ---------------------------------------------------------------------------
# Shared structured-output fake model helpers for integration tests.
#
# These mirror the pattern in tests/unit/helpers.py but are defined here so
# integration tests can import them from conftest without crossing tier
# boundaries.
# ---------------------------------------------------------------------------


class _TypeAwareFakeStructuredInvoker:
    """Returned by _StructuredOutputFakeModel.with_structured_output(schema).

    Searches the shared response list for the first item that is an instance of
    the requested schema class and pops it (type-aware match).  Falls back to
    positional (first item) when no typed match is found and the head of the
    list is not a *different* Pydantic model.  Raises LookupError when nothing
    usable remains — the orchestrator's fail-open try/except catches this for
    GoalSpec / GoalEvaluation, so existing tests do not need to supply those
    objects unless they are asserting goal-loop behaviour.
    """

    def __init__(self, schema: Any, responses: list[Any]) -> None:
        self._schema = schema
        self._responses = responses  # shared list reference

    async def ainvoke(self, messages: Any, **kwargs: Any) -> Any:
        import pydantic

        # 1. Search for a typed match.
        for i, item in enumerate(self._responses):
            if self._schema is not None and isinstance(item, self._schema):
                return self._responses.pop(i)

        # 2. No typed match — if the list is non-empty and the first item is NOT a
        #    different Pydantic model, return it positionally (backward compat).
        if self._responses:
            first = self._responses[0]
            if self._schema is None or not (
                isinstance(first, pydantic.BaseModel)
                and not isinstance(first, self._schema)
            ):
                return self._responses.pop(0)

        # 3. Nothing usable — raise so that orchestrator fail-open paths can recover.
        schema_name = getattr(self._schema, "__name__", str(self._schema))
        raise LookupError(
            f"_TypeAwareFakeStructuredInvoker: no response of type {schema_name!r} available"
        )


class _StructuredOutputFakeModel:
    """Minimal LangChain-compatible fake that supports with_structured_output().

    Pass `structured_responses` as an ordered list of Pydantic model instances
    (SessionIntent, AskUserDecision, AgentRoute, …).  Each call to
    .with_structured_output(Schema).ainvoke(...) uses type-aware matching:
    it searches the list for the first item that is an instance of Schema before
    falling back to positional order.  New orchestrator nodes that consume types
    not present in the list (e.g. GoalSpec / GoalEvaluation added in P71) raise
    LookupError, which the orchestrator's fail-open try/except catches — so
    existing tests do not need to be updated unless they assert goal-loop behaviour.

    Mirrors StructuredOutputFakeModel from tests/unit/helpers.py so integration
    tests do not cross tier boundaries.
    """

    model = "fake-structured-model"

    def __init__(self, structured_responses: list[Any]) -> None:
        self._structured_responses = list(structured_responses)

    def with_structured_output(self, schema: Any) -> "_TypeAwareFakeStructuredInvoker":
        return _TypeAwareFakeStructuredInvoker(schema, self._structured_responses)

    def bind_tools(self, tools: Any) -> "_StructuredOutputFakeModel":
        return self

    async def ainvoke(self, messages: Any, **kwargs: Any) -> Any:
        if self._structured_responses:
            return self._structured_responses.pop(0)
        return None


class _MultiRoleModelRegistry:
    """ModelRegistry where each role maps to its own fake model.

    Mirrors MultiRoleModelRegistry from tests/unit/helpers.py.
    A 'default' key is used as fallback.
    """

    def __init__(self, role_models: dict[str, Any]) -> None:
        self._role_models = role_models

    def get(self, role: str) -> Any:
        return self._role_models.get(role) or self._role_models.get("default")


def make_stub_registry(*structured_responses: Any) -> "_MultiRoleModelRegistry":
    """Build a _MultiRoleModelRegistry whose 'orchestrator' model returns
    `structured_responses` in order when with_structured_output().ainvoke()
    is called.

    Typical call-order per graph execution:
      1. SessionIntent          (classify_intent node)
      2. AskUserDecision        (prepare_ask_user node — only for analytical intents)
      3. AgentRoute             (select_mode node — only for non-supply_chain intents)

    Example::
        registry = make_stub_registry(
            SessionIntent(category="chat", confidence=0.9, rationale="r"),
            AgentRoute(mode="direct_chat", rationale="ok"),
        )
    """
    model = _StructuredOutputFakeModel(list(structured_responses))
    return _MultiRoleModelRegistry({"orchestrator": model})


@pytest.fixture(scope="session")
def vcr_config() -> dict:  # type: ignore[type-arg]
    return VCR_CONFIG


@pytest.fixture(autouse=True)
def _set_ollama_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default LLM_PROVIDER to ollama so integration tests never hit the Anthropic API.

    Tests that explicitly exercise the anthropic code path must delenv LLM_PROVIDER.
    """
    monkeypatch.setenv("LLM_PROVIDER", "ollama")


def _api_is_up() -> bool:
    import httpx
    try:
        return httpx.get("http://localhost:8000/health", timeout=1).status_code == 200
    except Exception:
        return False


@pytest.fixture(autouse=True)
async def cleanup_test_sessions() -> AsyncGenerator[list[str], None]:
    """Collect session IDs created during the test; delete them all on teardown."""
    created: list[str] = []
    yield created
    if not _api_is_up():
        return
    import httpx
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        for sid in created:
            try:
                await client.delete(f"/api/v1/sessions/{sid}", timeout=5)
            except Exception:
                pass
