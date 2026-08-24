# ADR: Local-Only Operational Routes

Date: 2026-08-24

## Background

The API currently registers `/api/v1/debug` and every `/api/v1/admin/*` route in all
environments. The debug response includes an API-key prefix, while admin routes expose
operational inspection, sample-data mutation, and session deletion capabilities. The
project remains a local/demo stack and full authentication is explicitly out of scope by
prior user decision, but safe defaults must not depend on the deployment operator remembering
that limitation.

## Candidates Considered

1. Leave the routes unconditional and document that deployments must remain local.
2. Add full authentication and role-based authorization now.
3. Register operational routes only in explicit development/test environments and revisit
   authenticated exposure when non-local deployment is approved.

## Decision

Choose candidate 3. `/api/v1/debug` and the `/api/v1/admin/*` router are registered only
when `APP_ENV` explicitly identifies development or test execution. An unset, production,
or otherwise unknown value is safe by default and does not expose these routes. The debug
response must never include an API key, prefix, hash, or other derived secret material.

Local Docker Compose continues to set `APP_ENV=dev`. Tests that exercise operational routes
must opt into an explicit test environment before importing the application. This ADR does
not add authentication or alter the existing product-agent public Python protocols.

## Rationale

Environment containment closes the immediate exposure without inventing an incomplete auth
scheme or contradicting the established deferral. Default-deny registration is structural:
production cannot accidentally expose handlers that were never mounted. Removing secret
material from diagnostics is required even in development because logs, screenshots, and
support transcripts can escape the local machine.

## Trade-offs

- Non-local deployments lose admin/settings/usage functionality until authenticated admin
  APIs are designed.
- Tests must control `APP_ENV` before application import, which makes environment assumptions
  explicit.
- Route absence returns the framework's normal 404 rather than a bespoke authorization error.

## Consequences

- `apps/api/main.py` owns conditional route registration using the existing `APP_ENV`
  convention.
- Local web features that consume admin routes continue to work under Compose.
- Production/default-safe verification must assert that operational route paths are absent.
- Future authenticated exposure requires a new ADR covering identity, roles, and route policy.

## Reversibility and Re-evaluation Triggers

The decision is reversible by registering the routes behind authenticated dependencies.
Re-evaluate when a non-local deployment is approved, an identity provider is selected, or
the user brings authentication back into scope.
