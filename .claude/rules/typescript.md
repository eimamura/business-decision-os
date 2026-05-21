# TypeScript Rules

## Compiler

- `strict: true` must be enabled — never weaken or override it
- `noEmit: true` — TypeScript is type-checking only; the framework handles compilation

## Types

- No `any`; use `unknown` and narrow with type guards or `instanceof`
- `interface` for object shapes that may be extended or merged
- `type` for unions, intersections, mapped types, and aliases
- Explicit return types on all exported functions and React components
- `null` vs `undefined`: prefer `undefined` for optional/absent values; `null` for explicitly empty

## Safety

- No non-null assertions (`!`) — use optional chaining (`?.`) or explicit null checks
- Use `readonly` on arrays (`readonly T[]`) and object properties that must not mutate
- Use `satisfies` to validate object literals against a type without widening the inferred type
- Enums: prefer string literal unions (`"pending" | "approved"`) or `as const` objects over `enum`

## Async

- Always `await` Promises; never leave a floating Promise
- Return type for fire-and-forget async functions: `Promise<void>`
- Wrap `fetch` / API calls in try/catch; never swallow errors silently

## Imports

- Use configured path aliases — no deep relative paths like `../../../`
- No barrel `index.ts` re-export files unless a package explicitly needs a stable public API
