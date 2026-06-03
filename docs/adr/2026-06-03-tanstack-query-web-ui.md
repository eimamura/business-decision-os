# ADR: Adopt TanStack Query v5 as Web UI Server State Layer

**Date:** 2026-06-03  
**Status:** Accepted  
**Author:** bdos-orchestrator

---

## Context

All ten Web UI pages that communicate with the API use ad-hoc `useEffect + fetch` patterns
with no AbortController cleanup. This causes two concrete problems:

1. **React 18 Strict Mode double-fetch.** In development, every component mounts twice.
   Without a cleanup that aborts the first fetch, each page navigation triggers two identical
   API requests. This produces noisy logs, wasted server cycles, and masks race conditions.

2. **Scattered, inconsistent API communication.** Each page re-implements its own loading
   state, error state, and refetch logic. There is no server-state cache: the same data
   (e.g., sessions list) is fetched redundantly across components.

`@tanstack/react-query@^5.50.0` is already listed in `apps/web/package.json` but is not
configured or used — the package was added speculatively and never wired up.

---

## Candidates Considered

| Option | Summary | Rejected reason |
|---|---|---|
| A — AbortController per useEffect | Add `ctrl.abort()` cleanup to each effect | Fixes Strict Mode noise but does not address cache, consistency, or code scatter |
| B — SWR | Popular alternative; simpler API | Already have TanStack Query installed; migration cost with no added value |
| C — Zustand server slice | Use existing Zustand store for API state | Zustand is for UI/client state; forcing server state into it re-creates TanStack Query's problems manually |
| **D — TanStack Query v5 (chosen)** | Purpose-built server state, deduplication, automatic refetch, invalidation | — |

---

## Decision

Adopt **TanStack Query v5** as the server state management layer for the Web UI, following
this layered structure:

```
React Component
  ↓ import from
features/<domain>/hooks.ts   ← useQuery / useMutation wrappers
  ↓ calls
features/<domain>/api.ts     ← pure async functions, no React
  ↓ calls
lib/api.ts :: apiFetch()     ← common HTTP wrapper (auth headers, error handling)
  ↓
FastAPI
```

**SSE streaming** (`ChatStateContext`, `useChat`) is explicitly excluded — TanStack Query
is not designed for streaming. The existing Context + `useEffect` pattern for SSE remains
unchanged.

**Scope:** Web UI layer only (`apps/web/`). No changes to Python packages, public
interfaces, or database schema.

---

## Rationale

- **Eliminates Strict Mode double-fetch.** TanStack Query deduplicates concurrent requests
  for the same query key — the second Strict Mode mount finds the query already in-flight
  and does not issue a second HTTP request.
- **Centralised cache + invalidation.** `queryClient.invalidateQueries()` replaces manual
  state splicing after mutations. Approvals, jobs, and sessions lists stay consistent.
- **Consistent loading/error surface.** `isLoading`, `isError`, `error` from `useQuery`
  replace heterogeneous `useState` guards in every page.
- **No new dependency.** Package already installed; no `npm audit` concern.

---

## Trade-offs

| Concern | Mitigation |
|---|---|
| Migration surface is wide (10 pages) | Batched across 3 App Builder tasks; pages are independent |
| `QueryClientProvider` requires `"use client"` boundary | Wrap in a thin `apps/web/app/providers.tsx` Client Component; root layout stays Server Component |
| SSE streaming is excluded | Pattern already established in `ChatStateContext`; invalidation hook added on stream completion |

---

## Reversibility

Low risk of reverting: the `features/*/api.ts` functions remain pure async functions
independent of TanStack Query. If the library is replaced, only `features/*/hooks.ts`
needs rewriting; the API functions and page components are unaffected.

Re-evaluation triggers:
- TanStack Query v5 → v6 breaking changes
- Next.js App Router adds first-class mutation cache support that supersedes this pattern
