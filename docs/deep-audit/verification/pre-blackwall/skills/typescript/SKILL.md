1: ---
2: name: typescript
3: description: TypeScript/JavaScript development. Use when working with .ts, .tsx, .js, .jsx, .mjs, .cjs files — type errors, lint, tests, Bun/Node runs.
4: ---
5: 
6: # TypeScript / JavaScript
7: 
8: - Runtime here is Bun-first (`bun`, `bunx`), Node 25 via nvm as fallback.
9:   `typescript-language-server` + `pyright`-style diagnostics come from the
10:   `typescript` LSP entry; prefer CLI feedback in the agent loop:
11:   `tsc --noEmit`, project-local `eslint`/`oxlint`, `bun test` / `vitest`.
12: - Bun workspaces resolve globals from `~/.bun/bin` (`tsc`, `tsserver`,
13:   `typescript-language-server` live there).
14: - React Native / Expo projects: never start Metro bundler speculatively;
15:   check `package.json` scripts and ask before long-running dev servers.
