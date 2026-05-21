# Python Rules

Standards for Python 3.11+ code.

## Imports and Module Structure

- Start every module with `from __future__ import annotations` (PEP 563 deferred evaluation)
- Import order: stdlib → third-party → local; isort/ruff `I` rule enforces this
- No star imports (`from x import *`)

## Type System

- Full type hints on every function signature; mypy strict mode must pass
- Use `X | None = None` for optional fields, not `Optional[X]`
- `Any` is forbidden unless unavoidable; add an inline comment explaining why
- Use `TypeAlias`, `TypeVar`, `ParamSpec`, `Protocol` from the `typing` module directly
- Pydantic v2 models: `model_config = ConfigDict(...)` — never inner `class Config`

## Async

- All I/O functions in the web layer must be `async def`
- Celery task functions (`@app.task`) are synchronous by design — do not make them `async def`
- No `time.sleep()` in async code; use `asyncio.sleep()`
- Use `contextlib.asynccontextmanager` for async resource management

## Error Handling

- Missing config (API keys, env vars): raise `RuntimeError` at the call site — no silent fallbacks, stubs, or no-ops
- Do not catch broad `Exception` unless re-raising or logging with full context

## Style

- Line length: 100 characters
- No `print()`; use `logging.getLogger(__name__)`
- No mutable default arguments; use `field(default_factory=...)` in Pydantic/dataclasses
- Prefer `match` statement over long `if/elif` chains for enum or literal dispatch
