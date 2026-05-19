# ADR-0003: Next.js for Web Frontend

**Date:** 2026-05-17  
**Status:** Accepted  
**Deciders:** Engineering Team

## Context

The frontend must support SSE-based real-time streaming for the Reasoning Panel and Approval Queue, render GFM Markdown (including KaTeX and Mermaid) for agent responses, display interactive trade-off visualizations (radar charts, parallel coordinates), and provide a multi-screen application (Chat, Scenario Comparison, Approval Queue, Audit Timeline, KPI Dashboard, Settings). The scope is too large for a lightweight tool like Streamlit or Gradio.

## Decision

Use **Next.js** (App Router) with TypeScript and `npm` workspaces. The UI component library is **shadcn/ui + Radix + Tailwind CSS**. State management uses **TanStack Query** for server state, **Zustand** for client state, and **React Hook Form + Zod** for form state. LLM streaming uses the **Vercel AI SDK** with the Anthropic Claude provider. Charts use **Recharts**.

## Rationale

- **SSE streaming:** Next.js App Router supports `ReadableStream` responses and the Vercel AI SDK provides a first-class `useChat`/streaming integration aligned with Anthropic's API.
- **React ecosystem:** The broad React ecosystem (shadcn, Radix, TanStack Query, Zustand, Recharts) provides all required UI primitives without requiring custom implementations.
- **Schema parity via codegen:** `packages/schemas-ts` generates Zod schemas from Pydantic source of truth. Next.js's TypeScript-first nature integrates naturally with the generated Zod types for runtime validation.
- **App Router RSC:** Server Components reduce client bundle size for static or data-fetching-heavy surfaces.
- **npm workspaces:** `apps/web` and `packages/schemas-ts` share a single `node_modules` under `npm workspaces`.

## Trade-offs

- **Heavier than Streamlit/Gradio:** Next.js has more setup and operational surface area than Python-native dashboarding tools. Justified by the final-form UI scope.
- **Multi-package surface area:** The chosen stack (shadcn + TanStack + Zustand + Vercel AI SDK + Recharts) is a larger dependency surface than a monolithic UI library. Each library is well-maintained and independently replaceable.
- **React complexity:** App Router SSR/RSC boundaries add mental overhead vs. a pure SPA. The tradeoff is better performance and native streaming support.

## Consequences

- `apps/web` is a Next.js App Router project under `npm workspaces`.
- All SSE events are typed via Zod schemas generated from `packages/schemas` (Pydantic). CI runs an equivalence check to prevent schema drift.
- Light theme only at launch; dark theme tokens are defined but not enabled. WCAG 2.1 AA accessibility is enforced.
- The Engineer Debug panel (Reasoning Panel + Tool Call Inspector) is built into end-user screens, toggled via `Cmd/Ctrl+.`, and never removed.
- GFM Markdown is rendered via `react-markdown + remark-gfm + rehype-sanitize`; KaTeX and Mermaid are lazy-loaded.
- Chat responses and UI labels are rendered in English.
