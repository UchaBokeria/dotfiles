1: ---
2: name: explore
3: description: Fast unfamiliar-codebase recon. Use when asked to find where something lives, how something works, or to map a repo before planning. Read-only, time-boxed.
4: ---
5: 
6: # Fast repo explorer
7: 
8: 1. **Structure first** (parallel): top-level listing, `README`/`AGENTS.md`/
9:    `CLAUDE.md`, `package.json`/`go.mod`/`pyproject.toml`/`Cargo.toml`,
10:    compose files. Two minutes, no deep reads.
11: 2. **Locate** (parallel sweeps): `glob` for filenames, `grep` for strings,
12:    `sg` (`ast-grep` skill) for structural patterns. Prefer all three over
13:    one — they catch different things.
14: 3. **Trace**: from entry points (routes, main, CLI) follow imports/calls
15:    2–3 hops max. LSP go-to-definition only if already warm.
16: 4. **Report**: a map, not a dump — directories + responsibilities, key files
17:    with one-line roles, entry points, open questions. Stop at the question
18:    asked; don't fix, don't refactor, don't plan unless asked.
19: 
20: Constraints: read-only (no edits, no installs, no servers). If the repo is
21: huge, sample by directory; say what was skipped.
