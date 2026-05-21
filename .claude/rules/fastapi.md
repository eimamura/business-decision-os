# FastAPI Rules

## Routers

- Every router: `APIRouter(prefix="/api/v1/...", tags=["..."])`
- Every endpoint must declare `response_model` (Pydantic schema) or an explicit `Response` subtype
- All endpoints are `async def`
- Use `status.HTTP_200_OK`, `status.HTTP_201_CREATED`, etc. — never bare integer status codes

## Error Handling

- Client errors: `raise HTTPException(status_code=..., detail="...")`
- Never expose internal stack traces or implementation details in `detail`

## Dependency Injection

- DB sessions, auth context, config: always via `Depends()` — no module-level global state
- DB session pattern: inject `AsyncSession` through a dependency; close in `finally` or use `async with`

## Request / Response

- Request bodies: typed Pydantic `BaseModel` parameters
- Path and query params: typed function parameters with defaults where appropriate
- No business logic in router functions — delegate to a service or domain function

## Application Lifecycle

- Startup/shutdown: `@asynccontextmanager` lifespan passed to `FastAPI(lifespan=...)` — not deprecated `@app.on_event`

## Streaming / Background Work

- SSE endpoints: `StreamingResponse` with `media_type="text/event-stream"`
- Long-running work: dispatch to Celery; reserve `BackgroundTasks` for lightweight fire-and-forget (e.g., audit log writes)
