---
name: worktree
description: Isolated git worktree workflows. Use ONLY when asked for parallel streams, risky refactors, or reviewing a PR in isolation — never by default.
---

# Worktrees (on-demand only)

The `opencode-worktree` TUI is installed globally. Prefer plain git unless
parallel isolation is genuinely needed.

```bash
opencode-worktree                  # visual manager (needs a git repo)
git worktree add ../proj-<topic> -b <branch>   # manual, same result
git worktree list && git worktree remove --force ../proj-<topic>  # cleanup
```

## Rules
- One `COMPOSE_PROJECT_NAME` per worktree for compose projects; never stop
  shared services (see `docker` skill).
- Off the default branch from `dev` unless told otherwise; push branches,
  never commit directly to worktree checkouts of `dev`.
- Remove the worktree when merged. Stale worktrees rot fast — list and prune.
