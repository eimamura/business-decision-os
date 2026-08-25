# ADR: Upgrade Tailwind CSS from v3 to v4

**Date:** 2026-06-14  
**Status:** Accepted  
**Phase:** P124

## Context

`apps/web` uses Tailwind CSS v3 (`^3.4.0`) with a JS config (`tailwind.config.js`) and the
standard PostCSS plugin. Tailwind CSS v4 (released 2025) rewrites the engine in Rust, ships
automatic content detection, and moves all theme configuration into CSS via `@theme`
directives — eliminating the JS config file entirely. It also splits the PostCSS plugin into
a separate `@tailwindcss/postcss` package and drops the `autoprefixer` dependency.

## Decision

Upgrade `tailwindcss` to `^4.0.0` and migrate all configuration to CSS.

## Migration Summary

| v3 | v4 |
|---|---|
| `tailwindcss: ^3.4.0` (PostCSS bundled) | `tailwindcss: ^4.0.0` + `@tailwindcss/postcss: ^4.0.0` |
| `autoprefixer` devDependency | Removed (built into v4) |
| `tailwind-merge: ^2.x` | `tailwind-merge: ^3.0.0` (v4-aware merge) |
| `postcss.config.js` plugins: `tailwindcss + autoprefixer` | `@tailwindcss/postcss` only |
| `@tailwind base/components/utilities` in CSS | `@import "tailwindcss"` |
| `tailwind.config.js` `darkMode: "class"` | `@custom-variant dark (&:where(.dark, .dark *))` in CSS |
| `theme.extend.colors` in JS | `@theme inline { --color-* }` in CSS |
| `theme.extend.fontFamily` in JS | `@theme inline { --font-family-* }` in CSS |
| Manual `content` glob | Automatic content detection (no config needed) |

## Consequences

- `tailwind.config.js` is deleted; all configuration lives in `globals.css`.
- `autoprefixer` is removed from devDependencies.
- `tailwind-merge` bumps from v2 to v3; public API is compatible — only class-detection internals changed for v4 class names.
- v4 auto-detects source files; no `content` glob maintenance.
- CSS variable-based design tokens (`--color-background`, etc.) continue to work via `@theme inline`.
