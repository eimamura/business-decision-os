# Next.js Rules

Standards for Next.js 13+ App Router.

## Server vs Client Components

- Server Components are the default — do NOT add `"use client"` unless the component uses browser APIs, React state (`useState`/`useReducer`), refs, or event handlers
- Push the `"use client"` boundary as low in the component tree as possible
- Data fetching belongs in Server Components; pass data down as props to Client Components
- `next/headers`, `cookies()`, and `headers()` are Server-Component-only

## File Conventions

- Use App Router file conventions: `page.tsx`, `layout.tsx`, `loading.tsx`, `error.tsx`, `not-found.tsx`
- `error.tsx` must be a Client Component (`"use client"`)
- API routes: `app/api/.../route.ts` with exported named handlers (`GET`, `POST`, `PATCH`, `DELETE`)

## Environment Variables

- Client-accessible vars: `NEXT_PUBLIC_` prefix required
- Server-only vars: no prefix; do not read them in Client Components

## Navigation and Assets

- Internal links: `<Link>` from `next/link` — never `<a href="...">` for same-app routes
- Images: `<Image>` from `next/image` with explicit `width`/`height` or `fill` — never bare `<img>`
- Fonts: `next/font`

## Metadata

- Export `metadata` (static) or `generateMetadata` (dynamic) from public-facing `page.tsx` files

## Styling

- Tailwind utility classes; no inline `style={{}}` except for truly dynamic values (e.g., CSS custom properties)

## State Management

- Local state: `useState` / `useReducer`
- No global state library without an ADR justifying it

## SSE

- Consume SSE streams in Client Components using `EventSource` or `ReadableStream` from `fetch`
