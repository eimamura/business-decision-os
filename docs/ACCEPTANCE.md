## Runtime Gate Rule

A phase cannot be considered runnable unless the local development environment can start successfully in detached mode.

Required runtime gate commands (executed in order):

```bash
make dev-up
make dev-smoke
make dev-down
```

The Test/Review agent must verify that:

- Docker Compose builds required services without error
- All containers start (api, web, db)
- API health endpoint returns HTTP 200
- Containers stop cleanly

If a port is already in use, the issue must be registered as a Dev Runtime Defect, not skipped.
Port conflicts can be resolved by setting `API_PORT` or `WEB_PORT` environment variables before the target:

```bash
API_PORT=8001 make dev-up
```

## Chat Runtime Smoke Gate

After any change to chat page components or session API routes, the following runtime smoke test must pass:

1. Create a new session via `POST /api/v1/sessions` — verify `session_id` is present in the response
2. Visit `/chat/{session_id}` in the browser — verify the URL contains a valid UUID (not the string `"undefined"`)
3. Send a message from the chat input — verify the request is `POST /api/v1/sessions/{session_id}/messages` with a valid UUID, not `undefined`
4. Verify the backend returns HTTP 200 (not 405 Method Not Allowed)
5. Verify the session sidebar highlights the active session correctly

Acceptance criteria violated if:
- Backend logs contain `GET /api/v1/sessions/undefined/messages`
- Backend logs contain `405 Method Not Allowed` on any session messages route
- Session ID `"undefined"` appears in any API request URL

Suspected area: `apps/web/app/chat/page.tsx` and `apps/web/app/chat/[sessionId]/page.tsx` — `Session` interface field alignment with backend (`session_id` not `id`).

## Build Gate Rule

A phase cannot be marked Done unless the following commands pass from the repository root:

```bash
make build
make test
make lint
make typecheck

If any command is unavailable, the Test/Review agent must explicitly report it as "not configured", not "passed".

The final review report must include the exact commands executed and their exit codes.

Tool Availability Rule

A quality gate is failed if the required tool is missing.

Examples:

ruff not found
pytest not found
mypy not found
npm not found
docker not found

Missing tools must not be reported as skipped or passed.

Defect Handling Rule

If any quality gate fails after a task or phase was marked Done, the issue must be registered as a Defect Task.

A Defect Task must include:

defect id
status
severity
reproduction command
observed error
expected result
suspected area
owner
acceptance criteria

The phase cannot be considered complete while any related Defect Task remains open.

Review Authority Rule

Implementation agents may fix issues, but they cannot mark quality gates as passed.

Only the Test/Review agent may confirm:

build passed
tests passed
lint passed
typecheck passed
acceptance criteria satisfied

Only the Orchestrator may update task status in docs/TASKS.md.

Final Review Report Rule

The final review report must include:

commands executed
working directory for each command
exit code for each command
pass/fail result
changed files
open defects
residual risks