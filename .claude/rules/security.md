# Security Rules

Standards that apply across all layers of the stack.

## Secrets

- No hardcoded secrets, passwords, or API keys anywhere in source code
- Missing required env vars: raise `RuntimeError` at the call site — never silently degrade
- Never commit `.env` files; commit only `.env.example` with placeholder values
- Mask secrets in logs: log only a short prefix followed by `...`

## SQL / Data Access

- All database queries via ORM or parameterized statements — never build SQL with f-strings or string concatenation

## Input Validation

- All external input (HTTP request bodies, query params) validated by Pydantic v2 models at the API boundary
- Do not trust data that has bypassed the API layer

## HTTP / Network

- Do not widen CORS to `allow_origins=["*"]`
- Never redirect to a user-supplied URL without validating against an explicit allowlist
- Production must use HTTPS

## Authentication

- Never accept auth credentials in query parameters; use headers only
- Dev-only auth stubs must not be reachable in production

## API Error Responses

- Do not expose stack traces, SQL errors, or internal state in API error responses
- Use generic user-facing messages; log the full error server-side

## Dependencies

- Before adding a new package, confirm it has no known CVEs: `uv audit` (Python), `npm audit` (Node)
- Pin major versions; do not use `*` or unbounded ranges for security-sensitive packages

## Containers

- Run the application as a non-root user
- No `--privileged` containers
- Do not store secrets in image layers (`ENV SECRET=...`); inject at runtime via environment variables

## File Uploads (if implemented)

- Validate MIME type and file size server-side before processing
- Store uploaded files outside the web root
