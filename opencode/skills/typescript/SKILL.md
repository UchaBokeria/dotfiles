---
name: typescript
description: TypeScript/JavaScript development. Use when working with .ts, .tsx, .js, .jsx, .mjs, .cjs files — type errors, lint, tests, Bun/Node runs.
---

# TypeScript / JavaScript

- Runtime here is Bun-first (`bun`, `bunx`), Node 25 via nvm as fallback.
  `typescript-language-server` + `pyright`-style diagnostics come from the
  `typescript` LSP entry; prefer CLI feedback in the agent loop:
  `tsc --noEmit`, project-local `eslint`/`oxlint`, `bun test` / `vitest`.
- Bun workspaces resolve globals from `~/.bun/bin` (`tsc`, `tsserver`,
  `typescript-language-server` live there).
- React Native / Expo projects: never start Metro bundler speculatively;
  check `package.json` scripts and ask before long-running dev servers.
