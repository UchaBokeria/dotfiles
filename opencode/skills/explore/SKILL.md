---
name: explore
description: Fast unfamiliar-codebase recon. Use when asked to find where something lives, how something works, or to map a repo before planning. Read-only, time-boxed.
---

# Fast repo explorer

1. **Structure first** (parallel): top-level listing, `README`/`AGENTS.md`/
   `CLAUDE.md`, `package.json`/`go.mod`/`pyproject.toml`/`Cargo.toml`,
   compose files. Two minutes, no deep reads.
2. **Locate** (parallel sweeps): `glob` for filenames, `grep` for strings,
   `sg` (`ast-grep` skill) for structural patterns. Prefer all three over
   one — they catch different things.
3. **Trace**: from entry points (routes, main, CLI) follow imports/calls
   2–3 hops max. LSP go-to-definition only if already warm.
4. **Report**: a map, not a dump — directories + responsibilities, key files
   with one-line roles, entry points, open questions. Stop at the question
   asked; don't fix, don't refactor, don't plan unless asked.

Constraints: read-only (no edits, no installs, no servers). If the repo is
huge, sample by directory; say what was skipped.
